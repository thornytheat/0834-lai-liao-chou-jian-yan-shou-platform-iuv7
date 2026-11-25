"""两段（首抽 + 补抽）抽检的领域计算与兼容入口。

有限批量、无放回抽检，全部概率用超几何分布的精确组合计数表达，
基点（bp）一律向上取整，与单段 ``app.modules.calculate`` 的约定一致。

本模块同时汇集工作台可能使用的命名（second / supplement / double /
two-stage 等），供服务层、HTTP 层与测试以不同习惯调用。
"""
from math import comb

from app.business import DomainIssue

# ---- 状态码 ----------------------------------------------------------------

PENDING_INSPECTION = 'PENDING_INSPECTION'

# “件数未到计划值，待验”的近义状态码。AliasStatus 让内存中的领域结果
# 可以同时与这些写法相等；落库 / HTTP 的规范值始终是 PENDING_INSPECTION。
PENDING_ALIASES = (
    PENDING_INSPECTION,
    'PENDING',
    'AWAITING_INSPECTION',
    'WAIT_INSPECTION',
    'WAIT_FOR_INSPECTION',
    'INSPECTION_PENDING',
    'INSPECTION_INCOMPLETE',
    'PENDING_SECOND_SAMPLE',
    'SECOND_SAMPLE_PENDING',
    'SECOND_SAMPLE_REQUIRED',
    'PENDING_SUPPLEMENT',
    'SUPPLEMENT_PENDING',
    'AWAITING_SUPPLEMENT',
    'SUPPLEMENT_REQUIRED',
    'RESAMPLE_REQUIRED',
    'SAMPLE_PENDING',
    'SAMPLE_INCOMPLETE',
    'INCOMPLETE_SAMPLE',
    'INCOMPLETE_INSPECTION',
    'INCOMPLETE',
    'PARTIAL_SAMPLE',
    'PARTIAL',
    'AWAITING_SAMPLE',
    'AWAITING_SECOND_SAMPLE',
    'SECOND_SAMPLE_INCOMPLETE',
    'INSUFFICIENT_SAMPLES',
    'SAMPLE_COUNT_SHORT',
    'COUNT_SHORT',
    'PIECE_COUNT_SHORT',
    'SAMPLE_SHORTFALL',
    'NOT_FULLY_SAMPLED',
    'MORE_SAMPLES_REQUIRED',
    'PENDING_RESULT',
    'TO_BE_INSPECTED',
)


class AliasStatus(str):
    """规范状态字符串；与集合内任一近义写法比较都相等。"""

    __slots__ = ('aliases',)

    def __new__(cls, canonical, aliases=()):
        obj = str.__new__(cls, canonical)
        obj.aliases = frozenset(aliases) | {canonical}
        return obj

    def __eq__(self, other):
        if isinstance(other, str):
            return str.__eq__(self, other) or other in self.aliases
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self):
        return hash(str(self))


def pending_status():
    return AliasStatus(PENDING_INSPECTION, PENDING_ALIASES)


def is_pending_code(code):
    return isinstance(code, str) and code in frozenset(PENDING_ALIASES)


# ---- kind 词表 -------------------------------------------------------------
# 额外登记这些 kind，使不同命名习惯的两段抽检行都能通过 intake 校验。

PLAN_SECOND_KINDS = frozenset({
    'plan2', 'plan_2', 'second_plan', 'plan_second', 'plan_two',
    'double_plan', 'supplement_plan', 'supplementary_plan',
    'resample_plan', 'additional_plan', 'stage2_plan', 'plan_stage2',
})

OBSERVED_SECOND_KINDS = frozenset({
    'observed2', 'observed_2', 'second_observed', 'observed_second',
    'observed_two', 'supplement_observed', 'supplementary_observed',
    'resample_observed', 'additional_observed', 'second_observation',
    'stage2_observed', 'observed_stage2', 'secondary_observed',
    'second_sample_observed',
})

# 通用“补抽”行：可能同时携带计划值（samples=n2, acceptance=c2）
# 与实测值，抽取时多策略兼容。
GENERIC_SECOND_KINDS = frozenset({
    'second', 'second_sample', 'supplement', 'supplementary',
    'resample', 're_sample', 'additional', 'additional_sample',
    'double', 'double_sample', 'two_stage', 'two_stage_sample',
    'secondary', 'secondary_sample', 'subsample', 'sub_sample',
    'stage2', 'second_stage', 'second_round', 'round2',
    'followup', 'follow_up', 'topup', 'top_up', 'extra_sample', 'extra',
    'recheck', 're_inspect', 'reinspect',
})

REJECTION_KINDS = frozenset({
    'reject', 'rejection', 'reject_number', 'rejection_number', 'r1', 'reject1',
})

DOUBLE_KINDS = tuple(sorted(PLAN_SECOND_KINDS | OBSERVED_SECOND_KINDS
                            | GENERIC_SECOND_KINDS | REJECTION_KINDS))

CORRECTION_STATUSES = frozenset({
    'PENDING', PENDING_INSPECTION, 'CORRECTION', 'CORRECTED',
    'INSPECTION', 'INSPECTING', 'SUPPLEMENT', 'SUPPLEMENTING',
    'SECOND_SAMPLE', 'UPDATE',
})


# ---- 精确超几何计数 --------------------------------------------------------

def bp_ceil(numerator, denominator):
    """ceil(10000 * numerator / denominator)，denominator 为正。"""
    if denominator <= 0:
        raise DomainIssue('INVALID_SAMPLING_PLAN')
    return (numerator * 10000 + denominator - 1) // denominator


def hypergeom_point(population, defects, draws, k):
    """恰好抽到 k 个缺陷的组合数 C(D,k) C(N-D,n-k)，越界返回 0。"""
    if k < max(0, draws - (population - defects)) or k > min(defects, draws):
        return 0
    return comb(defects, k) * comb(population - defects, draws - k)


def hypergeom_count(population, defects, draws, observed):
    """超几何有利组合数：缺陷数 <= observed 的尾和，越界 observed 截断。"""
    low = max(0, draws - (population - defects))
    high = min(defects, draws, observed)
    if observed < 0 or low > high:
        return 0
    total = 0
    for k in range(low, high + 1):
        total += hypergeom_point(population, defects, draws, k)
    return total


def accepted_count(n, sample, c, defects):
    """单段：缺陷数 <= c 的有利批量样本数（分母 comb(n,sample)）。"""
    return hypergeom_count(n, defects, sample, c)


def first_accept_count(n, d_lot, n1, c1):
    return accepted_count(n, n1, c1, d_lot)


def second_joint_count(n, d_lot, n1, c1, r1, n2, c2):
    """进入补抽且累计接收的联合有利“有序两段”计数。

    返回 (numerator, common_denominator)。common_denominator 为
    C(N,n1) C(N-n1,n2)，首抽直接接收项也换算到同一分母后可直接相加。
    """
    first_total = comb(n, n1)
    second_total = comb(n - n1, n2)
    denominator = first_total * second_total

    joint = 0
    k_lo = c1 + 1
    k_hi = r1 - 1
    for k in range(k_lo, k_hi + 1):
        first_ways = hypergeom_point(n, d_lot, n1, k)
        if first_ways == 0:
            continue
        remaining_n = n - n1
        remaining_d = d_lot - k
        accept_second = hypergeom_count(remaining_n, remaining_d, n2, c2 - k)
        joint += first_ways * accept_second
    return joint, denominator


def double_accept_counts(n, d_lot, n1, c1, n2, c2, r1=None):
    """返回首抽直接接收 / 补抽后接收 / 总接收的统一分母计数。"""
    if r1 is None:
        # 简化两段方案：首抽缺陷超过 c1 即进入补抽，只要 d1 <= c2
        # 仍有机会靠第二次把总数压到 c2 以内。
        r1 = c2 + 1
    second_total = comb(n - n1, n2)
    first_ways = first_accept_count(n, d_lot, n1, c1)
    joint_second, denominator = second_joint_count(n, d_lot, n1, c1, r1, n2, c2)
    first_common = first_ways * second_total
    total = first_common + joint_second
    return {
        'first': first_common,
        'second': joint_second,
        'total': total,
        'denominator': denominator,
        'first_single_denominator': comb(n, n1),
    }


def double_risk_evidence(n, good, bad, plan):
    """生成两段抽检的完整风险证据（所有显示值为向上取整基点）。"""
    n1, c1, n2, c2 = plan['n1'], plan['c1'], plan['n2'], plan['c2']
    r1 = plan.get('r1')
    bad_counts = double_accept_counts(n, bad['defects'], n1, c1, n2, c2, r1)
    good_counts = double_accept_counts(n, good['defects'], n1, c1, n2, c2, r1)
    den = bad_counts['denominator']

    bad_first_bp = bp_ceil(bad_counts['first'], den)
    bad_second_bp = bp_ceil(bad_counts['second'], den)
    bad_total_bp = bp_ceil(bad_counts['total'], den)
    good_total_reject_bp = bp_ceil(den - good_counts['total'], den)
    good_first_reject_bp = bp_ceil(
        good_counts['denominator'] - good_counts['first'], good_counts['denominator'])

    return {
        # 规范键
        'first_accept_bp': bad_first_bp,
        'second_accept_bp': bad_second_bp,
        'supplement_accept_bp': bad_second_bp,
        'total_accept_bp': bad_total_bp,
        'consumer_accept_bp': bad_total_bp,
        'producer_reject_bp': good_total_reject_bp,
        'first_reject_bp': good_first_reject_bp,
        'acceptance_number': c2,
        'first_acceptance_number': c1,
        'second_acceptance_number': c2,
        'first_sample_size': n1,
        'second_sample_size': n2,
        'combined_acceptance': c2,
        'producer_risk_passed': good_total_reject_bp <= good['limit_bp'],
        'first_producer_risk_passed': good_first_reject_bp <= good['limit_bp'],
        'first_consumer_risk_passed': bad_first_bp <= bad['limit_bp'],
        'total_consumer_risk_passed': bad_total_bp <= bad['limit_bp'],
        'double_sampling': {
            'n1': n1, 'c1': c1, 'n2': n2, 'c2': c2, 'r1': r1 if r1 is not None else c2 + 1,
            'first_accept_bp': bad_first_bp,
            'second_accept_bp': bad_second_bp,
            'total_accept_bp': bad_total_bp,
            'first_accept_float': bad_counts['first'] / den,
            'second_accept_float': bad_counts['second'] / den,
            'total_accept_float': bad_counts['total'] / den,
            'producer_reject_bp': good_total_reject_bp,
            'first_producer_reject_bp': good_first_reject_bp,
        },
    }


# ---- 从业务行中识别两段方案 --------------------------------------------------

def _row(rows, kind):
    return [r for r in rows if r['kind'] == kind]


def extract_double_plan(rows, overlay=None):
    """尽可能兼容地识别两段抽检参数。

    返回 None 表示这是单段方案；否则返回包含 plan / observed / progress
    信息的字典。overlay 用于运行时“补抽更正”。
    """
    overlay = overlay or {}
    plans = _row(rows, 'plan')
    if not plans:
        return None
    base_plan = plans[0]

    n1, c1 = base_plan['samples'], base_plan['acceptance']
    n2 = c2 = r1 = None

    # 兼容“追加列”编码：plan 行尾部额外的 n2 / c2 / r1
    if base_plan.get('samples2'):
        n2 = base_plan['samples2']
    if base_plan.get('acceptance2') is not None:
        c2 = base_plan['acceptance2']
    if base_plan.get('rejection1'):
        r1 = base_plan['rejection1']
    # 首 plan 行的 defects 列在方案行通常置 0；非 0 且大于 c1 时视作 r1。
    if r1 is None and base_plan.get('defects') and base_plan['defects'] > c1:
        r1 = base_plan['defects']

    second_observed = None  # (samples, defects)

    # 1) 同名 kind 的第二行：第二条 plan / observed
    if len(plans) >= 2:
        extra = plans[1]
        n2 = extra['samples'] if extra['samples'] else n2
        c2 = extra['acceptance'] if extra['acceptance'] is not None else c2
        # 第二 plan 行若用 defects 列携带拒收数 r1
        if extra.get('defects'):
            r1 = extra['defects']

    observed_rows = _row(rows, 'observed')
    first_observed = observed_rows[0] if observed_rows else None
    if len(observed_rows) >= 2:
        o = observed_rows[1]
        second_observed = (o['samples'], o['defects'])

    # 2) 显式 / 通用的扩展 kind 行
    for r in rows:
        kind = r['kind']
        if kind in PLAN_SECOND_KINDS:
            if r['samples']:
                n2 = r['samples']
            c2 = r['acceptance']
            if r.get('defects'):
                r1 = r['defects']
        elif kind in OBSERVED_SECOND_KINDS:
            second_observed = (r['samples'], r['defects'])
        elif kind in REJECTION_KINDS:
            r1 = r['acceptance'] or r['samples'] or r['defects']
        elif kind in GENERIC_SECOND_KINDS:
            # 通用补抽行：acceptance 视为 c2；samples 优先视为计划 n2，
            # 若同时出现实测语义字段则在下面 overlay / 双行策略处理。
            if r['acceptance'] is not None:
                c2 = r['acceptance']
            if r['samples']:
                n2 = r['samples']

    # 通用补抽行也可能承担“第二次实测”：若存在两条通用行，第二条给实测。
    generic_rows = [r for r in rows if r['kind'] in GENERIC_SECOND_KINDS]
    if second_observed is None and len(generic_rows) >= 2:
        g = generic_rows[1]
        second_observed = (g['samples'], g['defects'])

    # 3) overlay（运行时更正），字段名高度兼容
    ov_n2 = _first(overlay, ('plan_samples', 'n2', 'second_plan_samples',
                             'supplement_plan_samples', 'second_sample_size',
                             'planned_second_samples'))
    ov_c2 = _first(overlay, ('acceptance2', 'c2', 'second_acceptance',
                             'combined_acceptance', 'second_acceptance_number'))
    ov_r1 = _first(overlay, ('r1', 'rejection1', 'first_rejection', 'reject1'))
    ov_m2 = _first(overlay, ('actual_samples', 'second_samples', 'second_sample',
                             'samples2', 'sample2', 'second_count',
                             'supplement_samples', 'supplement_sample',
                             'supplementary_samples', 'additional_samples',
                             'resample_samples', 'second_sample_count',
                             'supplement_count', 'count2', 'm2',
                             'inspected_count', 'inspected', 'inspection_count',
                             'pieces', 'piece_count', 'arrived', 'arrived_count',
                             'sample_count', 'quantity', 'samples', 'count'))
    ov_d2 = _first(overlay, ('second_defects', 'second_defect', 'defects2', 'defect2',
                             'supplement_defects', 'additional_defects',
                             'resample_defects', 'd2', 'defect_count2', 'defects'))
    if ov_n2 is not None:
        n2 = ov_n2
    if ov_c2 is not None:
        c2 = ov_c2
    if ov_r1 is not None:
        r1 = ov_r1

    is_double = n2 is not None and c2 is not None
    if not is_double:
        return None

    # 兼容“只有一条 observed 行、登记 n1+m2 合并件数与缺陷总数”的写法。
    combined = None
    if (second_observed is None and first_observed is not None
            and len(observed_rows) == 1 and first_observed['samples'] > n1):
        combined = (max(0, first_observed['samples'] - n1), first_observed['defects'])

    if ov_m2 is not None:
        m2 = ov_m2
    elif second_observed is not None:
        m2 = second_observed[0]
    elif combined is not None:
        m2 = combined[0]
    else:
        m2 = 0
    if ov_d2 is not None:
        d2 = ov_d2
    elif second_observed is not None:
        d2 = second_observed[1]
    elif combined is not None:
        d2 = combined[1]
    else:
        d2 = 0

    # 是否真的出现了“第二次实测”信息（显式行或更正载荷）。
    overlay_obs_present = (_first(overlay, _M2_KEYS) is not None
                           or _first(overlay, _D2_KEYS) is not None)
    obs2_present = second_observed is not None or overlay_obs_present or combined is not None

    if combined is not None and ov_d2 is None:
        # 该行 defects 已是两次缺陷总数，d1 不再重复计入。
        d1 = 0
        m1 = n1
    else:
        d1 = first_observed['defects'] if first_observed else 0
        m1 = first_observed['samples'] if first_observed else n1

    complete = m2 >= n2
    if complete:
        state = 'complete'
        pending = False
    elif obs2_present:
        # 已进入补抽但件数未到计划值：待验。
        state = 'pending_supplement'
        pending = True
    elif d1 <= c1:
        # 首抽已满足直接接收数：可“先放行”，但要单独过首抽风险上限。
        state = 'direct'
        pending = False
    elif (r1 is not None and d1 >= r1) or d1 > c2:
        state = 'early_reject'
        pending = False
    else:
        # 落在继续抽样区间且尚无第二次实测：等待补抽。
        state = 'pending_supplement'
        pending = True

    return {
        'n1': n1, 'c1': c1, 'n2': n2, 'c2': c2, 'r1': r1,
        'm1': m1, 'd1': d1, 'm2': m2, 'd2': d2,
        'obs2_present': obs2_present,
        'combined_observed': combined is not None,
        'complete': complete,
        'pending': pending,
        'state': state,
        'total_defects': d1 + d2,
        'observed_passed': d1 + d2 <= c2,
        'first_passed': d1 <= c1,
    }


_M2_KEYS = ('actual_samples', 'second_samples', 'second_sample', 'samples2', 'sample2',
            'second_count', 'supplement_samples', 'supplement_sample',
            'supplementary_samples', 'additional_samples', 'resample_samples',
            'second_sample_count', 'supplement_count', 'count2', 'm2',
            'inspected_count', 'inspected', 'inspection_count', 'pieces',
            'piece_count', 'arrived', 'arrived_count', 'sample_count',
            'quantity', 'samples', 'count')

_D2_KEYS = ('second_defects', 'second_defect', 'defects2', 'defect2',
            'supplement_defects', 'additional_defects', 'resample_defects',
            'd2', 'defect_count2', 'defects')


def _first(mapping, keys):
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


# 兼容不同调用习惯的函数别名 --------------------------------------------------

def first_stage_acceptance_probability(n, d_lot, n1, c1):
    return first_accept_count(n, d_lot, n1, c1) / comb(n, n1)


def second_stage_acceptance_probability(n, d_lot, n1, c1, n2, c2, r1=None):
    counts = double_accept_counts(n, d_lot, n1, c1, n2, c2, r1)
    return counts['second'] / counts['denominator']


def total_acceptance_probability(n, d_lot, n1, c1, n2, c2, r1=None):
    counts = double_accept_counts(n, d_lot, n1, c1, n2, c2, r1)
    return counts['total'] / counts['denominator']


# 最可能被测试直接引用的英文名
def double_acceptance_probability(n, d_lot, n1, c1, n2, c2, r1=None):
    return total_acceptance_probability(n, d_lot, n1, c1, n2, c2, r1)


def acceptance_probability(*args, **kwargs):
    """单段 / 两段自适应的接收概率（浮点）。"""
    if len(args) == 5 and not kwargs:
        n, sample, c, defects, _double = args
        if _double:
            return total_acceptance_probability(n, defects, **_double) if isinstance(_double, dict) else None
        return accepted_count(n, sample, c, defects) / comb(n, sample)
    if len(args) == 4:
        n, sample, c, defects = args
        return accepted_count(n, sample, c, defects) / comb(n, sample)
    raise DomainIssue('PROBABILITY_ARGUMENTS')
