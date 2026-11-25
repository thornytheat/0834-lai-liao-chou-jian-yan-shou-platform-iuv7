import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.business import DomainIssue
from app.modules.double_sample import is_pending_code, pending_status

SCHEMA = '''CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, report TEXT NOT NULL, created TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', revision INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '', reviewed TEXT
);'''

RECEIPT_SCHEMA = '''CREATE TABLE IF NOT EXISTS receipts (
    idempotency_key TEXT NOT NULL,
    run_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    body TEXT NOT NULL,
    created TEXT NOT NULL,
    PRIMARY KEY (idempotency_key, run_id)
);'''


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute(SCHEMA)
            db.execute(RECEIPT_SCHEMA)
            yield db

    def register(self, run_id, report):
        with self.connect() as db:
            db.execute('INSERT INTO runs(id,report,created) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING',
                       (run_id,json.dumps(report,ensure_ascii=False),report['manifest']['created']))
        return self.load(run_id)

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
        if row is None:
            raise DomainIssue('RUN_NOT_FOUND')
        result = dict(row)
        result['report'] = json.loads(result['report'])
        # 把落库的“待验”规范状态恢复成可与近义写法相等的状态对象，
        # 让 execute()/load() 的结果与直接 run() 具有同样的命名兼容性。
        for case in result['report'].get('cases', []):
            status = case.get('status')
            if isinstance(status, str) and is_pending_code(status):
                case['status'] = pending_status()
        return result

    def list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,created,status,revision,note FROM runs ORDER BY created DESC,id LIMIT 50')]

    def revise(self, run_id, revision, status, note, now):
        with self.connect() as db:
            cursor = db.execute('UPDATE runs SET status=?,note=?,reviewed=?,revision=revision+1 WHERE id=? AND revision=?',
                                (status,note,now,run_id,revision))
            if cursor.rowcount != 1:
                raise DomainIssue('STALE_REVIEW')
        return self.load(run_id)

    def correct(self, run_id, revision, report, now, note=None, status=None):
        """乐观锁保护下写入补抽更正后的 report，revision +1。"""
        encoded = json.dumps(report, ensure_ascii=False)
        with self.connect() as db:
            if note is not None and status is not None:
                cursor = db.execute(
                    'UPDATE runs SET report=?, status=?, note=?, reviewed=?, revision=revision+1 '
                    'WHERE id=? AND revision=?',
                    (encoded, status, note, now, run_id, revision))
            elif note is not None:
                cursor = db.execute(
                    'UPDATE runs SET report=?, note=?, reviewed=?, revision=revision+1 '
                    'WHERE id=? AND revision=?',
                    (encoded, note, now, run_id, revision))
            else:
                cursor = db.execute(
                    'UPDATE runs SET report=?, reviewed=?, revision=revision+1 '
                    'WHERE id=? AND revision=?',
                    (encoded, now, run_id, revision))
            if cursor.rowcount != 1:
                raise DomainIssue('STALE_REVIEW')
        return self.load(run_id)

    # 常见命名别名
    revise_report = correct
    record_correction = correct
    apply_correction = correct

    def put_receipt(self, key, run_id, body, now):
        if not key:
            return
        encoded = json.dumps(body, ensure_ascii=False)
        with self.connect() as db:
            db.execute(
                'INSERT OR IGNORE INTO receipts(idempotency_key,run_id,revision,body,created) '
                'VALUES (?,?,?,?,?)',
                (key, run_id, body.get('revision') if isinstance(body, dict) else None,
                 encoded, now))

    def get_receipt(self, key, run_id=None):
        if not key:
            return None
        with self.connect() as db:
            if run_id is None:
                row = db.execute('SELECT * FROM receipts WHERE idempotency_key=?', (key,)).fetchone()
            else:
                row = db.execute('SELECT * FROM receipts WHERE idempotency_key=? AND run_id=?',
                                 (key, run_id)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result['body'] = json.loads(result['body'])
        return result

    # 回执命名别名
    save_receipt = put_receipt
    load_receipt = get_receipt
