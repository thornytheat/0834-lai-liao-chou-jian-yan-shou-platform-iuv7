import re

from app.business import DomainIssue
from app.intake.numeric import quantity
from app.spec import COLUMNS, KINDS

HEADER = ('record', 'case', 'kind', *COLUMNS, 'note')

# 规范列数；额外列只在“追加的全为数值列、最后一列为 note”时宽容解析，
# 以兼容两段抽检把第二样本参数加成列的写法。普通多列坏行仍判 COLUMN_COUNT。
BASE_WIDTH = len(HEADER)
HEAD_FIELDS = ('record', 'case', 'kind')


def _canonical(row):
    for key in ('record', 'case'):
        row[key] = row[key].strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,35}', row[key]):
            raise DomainIssue('BAD_IDENTIFIER')
    if row['kind'] not in KINDS:
        raise DomainIssue('UNKNOWN_KIND')
    for column in COLUMNS:
        row[column] = quantity(row[column])
    if len(row['note']) > 200:
        raise DomainIssue('NOTE_TOO_LONG')
    return row


def record(values):
    if len(values) == BASE_WIDTH:
        return _canonical(dict(zip(HEADER, values)))

    if len(values) < BASE_WIDTH:
        raise DomainIssue('COLUMN_COUNT')

    # 扩展列布局：前 8 列固定（标识 + 五个数值字段），随后是 1..k 个追加
    # 数值列，最后一列仍是 note。任一追加列不是数字则按列数异常隔离。
    core_raw = values[3:3 + len(COLUMNS)]
    extra_raw = values[3 + len(COLUMNS):-1]
    try:
        extra_numbers = [quantity(v) for v in extra_raw]
    except DomainIssue:
        raise DomainIssue('COLUMN_COUNT')

    row = dict(zip(HEADER[:3], values[:3]))
    row.update(dict(zip(COLUMNS, core_raw)))
    row['note'] = values[-1]
    row['ext_numbers'] = extra_numbers
    if extra_numbers:
        # 常见追加顺序：第二样本计划数 n2、第二接收数 c2、首抽拒收数 r1
        row['samples2'] = extra_numbers[0]
        if len(extra_numbers) >= 2:
            row['acceptance2'] = extra_numbers[1]
        if len(extra_numbers) >= 3:
            row['rejection1'] = extra_numbers[2]
    return _canonical(row)
