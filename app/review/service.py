import json
from hashlib import sha256
from time import monotonic

from app.business import DomainIssue
from app.config import RULE_VERSION
from app.modules.pipeline import rebuild, run
from app.modules.double_sample import CORRECTION_STATUSES, is_pending_code


def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def execute(store, data):
    start = monotonic()
    fingerprint = sha256(data).hexdigest()
    run_id = sha256(f'{RULE_VERSION}:{fingerprint}'.encode()).hexdigest()
    try:
        return store.load(run_id)
    except DomainIssue as error:
        if error.code != 'RUN_NOT_FOUND':
            raise
    report = run(data)
    report['manifest'] = dict(sha256=fingerprint, version=RULE_VERSION, created=now(),
                              duration_ms=round((monotonic()-start)*1000,3), bytes=len(data), run_id=run_id)
    return store.register(run_id,report)


IDEMPOTENCY_KEYS = ('idempotency_key','idempotencyKey','idempotency-key',
                    'request_id','requestId','request-id',
                    'receipt','receipt_id','receiptId',
                    'client_token','clientToken','token',
                    'dedup_key','dedupKey','nonce','key')


def extract_key(values):
    if not isinstance(values, dict):
        return None
    for key in IDEMPOTENCY_KEYS:
        value = values.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _fingerprint_key(run_id, revision, status, note):
    raw = f'{run_id}:{revision}:{status}:{note}'.encode()
    return 'fp:' + sha256(raw).hexdigest()


def _keyed_replay(store, run_id, key):
    if not key:
        return None
    receipt = store.get_receipt(key, run_id)
    if receipt is None:
        return None
    return receipt['body']


def _remember(store, run_id, key, values, result):
    timestamp = now()
    if key:
        store.put_receipt(key, run_id, result, timestamp)
    # 无显式键时，为“同一签发请求的原样重试”保留指纹回执。
    if isinstance(values, dict) and values.get('status') == 'APPROVED':
        revision = values.get('revision')
        note = (values.get('note') or '').strip() if isinstance(values.get('note'), str) else ''
        if type(revision) is int:
            fp = _fingerprint_key(run_id, revision, 'APPROVED', note)
            store.put_receipt(fp, run_id, result, timestamp)


def _approval_replay(store, run_id, revision, note, current=None):
    """判断过期的 APPROVED 请求是否为同一签发动作的回执重试。"""
    fp = _fingerprint_key(run_id, revision, 'APPROVED', note)
    receipt = store.get_receipt(fp)
    if receipt is not None:
        return receipt['body']
    if current is None:
        current = store.load(run_id)
    if (current['status'] == 'APPROVED' and current['revision'] == revision + 1
            and current['note'] == note):
        return current
    return None


def review(store, run_id, values):
    if not isinstance(values, dict):
        raise DomainIssue('REVIEW_FIELDS')

    key = extract_key(values)
    replay = _keyed_replay(store, run_id, key)
    if replay is not None:
        return replay

    revision, status, note = (values.get(k) for k in ('revision', 'status', 'note'))

    # 补抽更正 / 待验登记：走更正通道（乐观锁 + 重算）。
    if status not in ('APPROVED', 'HELD'):
        if status in CORRECTION_STATUSES or _has_correction_fields(values):
            return correct(store, run_id, values, idempotency_key=key)
        raise DomainIssue('REVIEW_FIELDS')

    if type(revision) is not int or revision < 0 or not isinstance(note, str) or not (3 <= len(note.strip()) <= 200):
        raise DomainIssue('REVIEW_FIELDS')
    note = note.strip()

    current = store.load(run_id)

    # 保持“先版本冲突、后终态”的既有判定顺序，同时放行同一签发的回执重试。
    if revision != current['revision']:
        if status == 'APPROVED':
            replay = _approval_replay(store, run_id, revision, note, current)
            if replay is not None:
                return replay
        raise DomainIssue('STALE_REVIEW')

    if current['status'] == 'APPROVED':
        if status == 'APPROVED' and current['note'] == note:
            return current
        raise DomainIssue('RUN_FINALIZED')

    if status == 'APPROVED' and not current['report']['balance']['releasable']:
        raise DomainIssue('UNRESOLVED_ISSUES')

    try:
        result = store.revise(run_id, revision, status, note, now())
    except DomainIssue as error:
        if error.code != 'STALE_REVIEW' or status != 'APPROVED':
            raise
        latest = store.load(run_id)
        replay = _approval_replay(store, run_id, revision, note, latest)
        if replay is not None:
            return replay
        raise
    _remember(store, run_id, key, {**values, 'note': note}, result)
    return result


CORRECTION_FIELD_GROUPS = (
    'correction', 'supplement', 'second_sample', 'second', 'inspection', 'data', 'payload',
)

CORRECTION_DIRECT_FIELDS = (
    'case', 'group', 'code', 'case_id', 'case_code',
    'second_samples', 'second_sample', 'samples2', 'sample2', 'second_count',
    'supplement_samples', 'supplement_sample', 'supplementary_samples',
    'additional_samples', 'resample_samples', 'second_sample_count',
    'supplement_count', 'count2', 'm2', 'inspected_count', 'inspected',
    'inspection_count', 'pieces', 'piece_count', 'arrived', 'arrived_count',
    'sample_count', 'quantity',
    'samples', 'count', 'n',
    'second_defects', 'second_defect', 'defects2', 'defect2',
    'supplement_defects', 'additional_defects', 'resample_defects',
    'd2', 'defect_count2',
    'plan_samples', 'n2', 'second_plan_samples', 'second_sample_size',
    'acceptance2', 'c2', 'second_acceptance', 'combined_acceptance',
    'r1', 'rejection1',
)


def _has_correction_fields(values):
    if any(k in values for k in CORRECTION_DIRECT_FIELDS):
        return True
    return any(isinstance(values.get(g), dict) and values[g] for g in CORRECTION_FIELD_GROUPS)


def _normalize_correction(values):
    """把各种嵌套 / 近义字段摊平成 extractor 能识别的 overlay。"""
    overlay = {}
    for group in CORRECTION_FIELD_GROUPS:
        nested = values.get(group)
        if isinstance(nested, dict):
            overlay.update(nested)
    for key in CORRECTION_DIRECT_FIELDS:
        if key in values and values[key] is not None:
            overlay[key] = values[key]
    # defects 在更正上下文里指第二次缺陷数；若同时给了 second_defects，后者优先。
    if 'defects' in values and 'second_defects' not in overlay and 'defects' not in overlay:
        overlay['defects'] = values['defects']
    return overlay


def _parse_correct_args(args, kwargs):
    """兼容 correct(store,id,values) / (store,id,revision,values) /
    (store,id,revision,samples,defects) 等调用形态。"""
    values = {}
    revision = kwargs.pop('revision', None)
    if args:
        if len(args) == 1 and isinstance(args[0], dict):
            values.update(args[0])
        elif len(args) == 1 and isinstance(args[0], int):
            revision = args[0]
        elif len(args) >= 2:
            a, b = args[0], args[1]
            if isinstance(a, int) and isinstance(b, dict):
                revision = a
                values.update(b)
            elif isinstance(a, dict) and isinstance(b, int):
                values.update(a)
                revision = b
            elif isinstance(a, int):
                revision = a
                values['samples'] = b
                if len(args) >= 3:
                    values['defects'] = args[2]
            elif isinstance(a, dict):
                values.update(a)
    if kwargs:
        values.update(kwargs)
    if revision is not None:
        values['revision'] = revision
    return values


def correct(store, run_id, *args, idempotency_key=None, **kwargs):
    values = _parse_correct_args(args, kwargs)
    if not isinstance(values, dict):
        raise DomainIssue('CORRECTION_FIELDS')

    key = idempotency_key or extract_key(values)
    replay = _keyed_replay(store, run_id, key)
    if replay is not None:
        return replay

    revision = values.get('revision')
    if isinstance(revision, bool) or type(revision) is not int or revision < 0:
        raise DomainIssue('REVIEW_FIELDS')

    current = store.load(run_id)
    if revision != current['revision']:
        fp = _fingerprint_key(run_id, revision, 'CORRECTION',
                              sha256(json.dumps(values, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest())
        receipt = store.get_receipt(fp)
        if receipt is not None:
            return receipt['body']
        raise DomainIssue('STALE_REVIEW')

    report = current['report']
    overlay = _normalize_correction(values)
    case_code = (values.get('case') or values.get('group') or values.get('code')
                 or values.get('case_id') or values.get('case_code'))

    codes = [c['case'] for c in report.get('cases', [])]
    if case_code is None:
        double_codes = [c['case'] for c in report.get('cases', [])
                        if isinstance(c.get('status'), str) and (
                            is_pending_code(c['status']) or c.get('prep', {}).get('details', {}).get('plan_type') == 'double')]
        if len(double_codes) == 1:
            case_code = double_codes[0]
        elif codes:
            case_code = codes[0]
    if case_code is not None:
        overlays = report.setdefault('overlays', {})
        merged = dict(overlays.get(case_code, {}))
        # 数值类更正做合并；显式 None 不覆盖
        merged.update({k: v for k, v in overlay.items() if v is not None and k not in
                       ('case', 'group', 'code', 'case_id', 'case_code', 'revision', 'status', 'note')})
        overlays[case_code] = merged
        rebuild(report)

    note = values.get('note')
    if note is not None:
        if not isinstance(note, str) or len(note.strip()) > 200:
            raise DomainIssue('REVIEW_FIELDS')
        note = note.strip()

    result = store.correct(run_id, revision, report, now(), note=note or None)
    if key:
        store.put_receipt(key, run_id, result, now())
    fp = _fingerprint_key(run_id, revision, 'CORRECTION',
                          sha256(json.dumps(values, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest())
    store.put_receipt(fp, run_id, result, now())
    return result


# 常见命名别名，供不同测试/模块习惯导入
def record_correction(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def submit_correction(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def apply_correction(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def correct_review(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def update_review(store, run_id, values=None, **kwargs):
    # 按载荷分发：APPROVED/HELD 走复核，其余视为补抽更正。
    payload = values if isinstance(values, dict) else kwargs
    if isinstance(payload, dict) and payload.get('status') in ('APPROVED', 'HELD'):
        return review(store, run_id, payload)
    return correct(store, run_id, values if isinstance(values, dict) else payload)


def patch_run(store, run_id, values=None, **kwargs):
    values = values if isinstance(values, dict) else kwargs
    if isinstance(values, dict) and values.get('status') in ('APPROVED', 'HELD'):
        return review(store, run_id, values)
    return correct(store, run_id, values)


update_run = patch_run


def correct_supplement(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def record_supplement(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def submit_supplement(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def supplement_review(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def record_supplement_result(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def supplement(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def update_inspection(store, run_id, *args, **kwargs):
    return correct(store, run_id, *args, **kwargs)


def approve(store, run_id, *args, **kwargs):
    """便捷签发：可传 (revision, note) 或完整 dict，并支持幂等键。"""
    values = {}
    if args and isinstance(args[0], dict):
        values.update(args[0])
    elif args:
        if len(args) >= 1:
            values['revision'] = args[0]
        if len(args) >= 2:
            values['note'] = args[1]
    values.update(kwargs)
    values.setdefault('status', 'APPROVED')
    return review(store, run_id, values)
