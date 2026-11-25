from app.business import DomainIssue, prepared, single


def prepare(rows):
    plan = single(rows,'plan')
    good = single(rows,'producer')
    bad = single(rows,'consumer')
    observed = single(rows,'observed')
    n, sample, c = plan['lot'],plan['samples'],plan['acceptance']
    if not 0 < sample <= n <= 10000 or sample>500 or not 0 <= c < sample or not 0 <= good['defects'] < bad['defects'] <= n:
        raise DomainIssue('INVALID_SAMPLING_PLAN')
    if observed['samples']!=sample or observed['defects']>sample or max(good['limit_bp'],bad['limit_bp'])>10000:
        raise DomainIssue('INVALID_OBSERVATION')
    return prepared(sample,{'lot':n,'acceptance':c},(n,sample,c,good,bad,observed['defects']))
