from app.business import decision
from app.modules.double_sample import pending_status, PENDING_INSPECTION

PENDING_STATUS = PENDING_INSPECTION
AWAITING_INSPECTION = PENDING_INSPECTION


def policy(result, payload=None, mode=None):
    details = result['evidence']
    state = details.get('state')

    # 显式指定按“首抽直放”口径判定（供接口/测试选择先放行方案）。
    if mode in ('first', 'direct', 'first_sample'):
        return _direct_policy(result, details)

    # 已进入补抽但件数未到计划值：待验，不下接收/拒收结论。
    if details.get('pending') or result.get('pending') or state == 'pending_supplement':
        out = decision(result, None, upper_bound=True)
        out['status'] = pending_status()
        return out

    if state == 'early_reject' or not details['observed_passed']:
        reason = 'LOT_REJECTED'
    elif state == 'direct':
        # 首抽即放行：按首抽单独的供需风险上限判断。
        return _direct_policy(result, details)
    elif not details['producer_risk_passed']:
        reason = 'PRODUCER_RISK_LIMIT'
    else:
        reason = 'CONSUMER_RISK_LIMIT' if result['value'] > result['expected'] else None
    return decision(result, reason, upper_bound=True)


def _direct_policy(result, details):
    first_value = details.get('first_accept_bp', result['value'])
    scoped = {'value': first_value, 'expected': result['expected']}
    if not details.get('first_observed_passed', details.get('observed_passed')):
        reason = 'LOT_REJECTED'
    elif not details.get('first_producer_risk_passed', details.get('producer_risk_passed')):
        reason = 'PRODUCER_RISK_LIMIT'
    elif not details.get('first_consumer_risk_passed', first_value <= result['expected']):
        reason = 'CONSUMER_RISK_LIMIT'
    else:
        reason = None
    verdict = decision(scoped, reason, upper_bound=True)
    verdict['mode'] = 'direct'
    return verdict
