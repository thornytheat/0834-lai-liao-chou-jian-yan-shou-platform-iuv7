from app.business import DomainIssue, by_kind, prepared, single
from app.modules.double_sample import extract_double_plan


def prepare(rows, overlay=None):
    plan_rows = by_kind(rows, 'plan')
    if len(plan_rows) < 1:
        # 保持 single() 的错误码约定
        single(rows, 'plan')
    plan = plan_rows[0]
    good = single(rows, 'producer')
    bad = single(rows, 'consumer')
    observed_rows = by_kind(rows, 'observed')
    observed = observed_rows[0] if observed_rows else None
    if observed is None:
        raise DomainIssue('EXPECTED_ONE_OBSERVED')

    n, sample, c = plan['lot'], plan['samples'], plan['acceptance']
    if not 0 < sample <= n <= 10000 or sample > 500 or not 0 <= c < sample or not 0 <= good['defects'] < bad['defects'] <= n:
        raise DomainIssue('INVALID_SAMPLING_PLAN')
    if max(good['limit_bp'], bad['limit_bp']) > 10000:
        raise DomainIssue('INVALID_OBSERVATION')

    double = extract_double_plan(rows, overlay)

    if double is None:
        # 单段方案：实测件数必须恰好等于计划样本数。
        if observed['samples'] != sample or observed['defects'] > sample:
            raise DomainIssue('INVALID_OBSERVATION')
        return prepared(sample, {'lot': n, 'acceptance': c},
                        (n, sample, c, good, bad, observed['defects']))

    n2, c2 = double['n2'], double['c2']
    if (not 0 < n2 or sample + n2 > n or n2 > 500
            or c2 < 0 or c2 >= sample + n2):
        raise DomainIssue('INVALID_SAMPLING_PLAN')
    if double['combined_observed']:
        if double['total_defects'] > double['m1'] + double['m2']:
            raise DomainIssue('INVALID_OBSERVATION')
    elif (double['d1'] > double['m1'] or double['d2'] > double['m2']):
        raise DomainIssue('INVALID_OBSERVATION')
    if double['m1'] < 0 or double['m2'] < 0 or double['d1'] < 0 or double['d2'] < 0:
        raise DomainIssue('INVALID_OBSERVATION')

    details = {
        'lot': n, 'acceptance': c,
        'plan_type': 'double',
        'first_sample': sample, 'first_acceptance': c,
        'second_sample': n2, 'second_acceptance': c2,
        'total_sample': sample + n2,
        'second_samples': n2, 'second_acceptance_number': c2,
        'complete': double['complete'],
        'state': double['state'],
        'total_defects': double['total_defects'],
    }
    payload = {
        'double': True, 'n': n, 'good': good, 'bad': bad,
        'plan': double, 'first_observed_defects': double['d1'],
    }
    return prepared(sample, details, payload)
