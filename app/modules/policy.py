from app.business import decision


def policy(result):
    details = result['evidence']
    if not details['observed_passed']:
        reason = 'LOT_REJECTED'
    elif not details['producer_risk_passed']:
        reason = 'PRODUCER_RISK_LIMIT'
    else:
        reason = 'CONSUMER_RISK_LIMIT' if result['value']>result['expected'] else None
    return decision(result,reason,upper_bound=True)
