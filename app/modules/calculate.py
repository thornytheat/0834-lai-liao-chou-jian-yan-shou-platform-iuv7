from app.business import measured
from app.modules.double_sample import double_risk_evidence


def compute(data):
    # 两段抽检载荷
    if isinstance(data, dict) and data.get('double'):
        return compute_double(data)
    return compute_single(data)


def compute_single(data):
    from math import comb
    n, sample, c, good, bad, observed = data
    total = comb(n, sample)

    def accepted(defects):
        low = max(0, sample-(n-defects))
        high = min(defects, sample, c)
        return sum(comb(defects, k)*comb(n-defects, sample-k) for k in range(low, high+1))

    good_reject = ((total-accepted(good['defects']))*10000+total-1)//total
    bad_accept = (accepted(bad['defects'])*10000+total-1)//total
    evidence = {'producer_reject_bp':good_reject,'consumer_accept_bp':bad_accept,'acceptance_number':c,'observed_defects':observed,'observed_passed':observed<=c,'producer_risk_passed':good_reject<=good['limit_bp']}
    return measured(bad_accept,bad['limit_bp'],'基点',evidence)


def compute_double(data):
    n, good, bad, plan = data['n'], data['good'], data['bad'], data['plan']
    risk = double_risk_evidence(n, good, bad, plan)

    complete = plan['complete']
    state = plan.get('state', 'complete' if complete else 'pending_supplement')
    is_pending = bool(plan.get('pending'))
    observed_total = plan['total_defects']
    # 抽满后按两次缺陷总数对照 c2；首抽直放状态按首抽判定；待验/早拒收无合格结论。
    if complete:
        observed_passed = bool(plan['observed_passed'])
    elif state == 'direct':
        observed_passed = bool(plan['first_passed'])
    else:
        observed_passed = False

    evidence = dict(risk)
    evidence.update({
        'plan_type': 'double',
        'state': state,
        'complete': complete,
        'second_sample_complete': complete,
        'observed_defects': observed_total,
        'total_observed_defects': observed_total,
        'combined_defects': observed_total,
        'defects_total': observed_total,
        'first_observed_defects': plan['d1'],
        'second_observed_defects': plan['d2'],
        'first_observed_passed': plan['first_passed'],
        'second_samples': plan['m2'],
        'second_sample_observed': plan['m2'],
        'second_sample_count': plan['m2'],
        'actual_second_samples': plan['m2'],
        'second_sample_planned': plan['n2'],
        'planned_second_samples': plan['n2'],
        'pending': is_pending,
        'inspection_pending': is_pending,
        'observed_passed': observed_passed,
        'producer_risk_passed': risk['producer_risk_passed'],
        # —— 概率分量的近义键（均为向上取整基点）——
        'direct_accept_bp': risk['first_accept_bp'],
        'first_stage_accept_bp': risk['first_accept_bp'],
        'first_sample_accept_bp': risk['first_accept_bp'],
        'stage1_accept_bp': risk['first_accept_bp'],
        'accept_first_bp': risk['first_accept_bp'],
        'first_acceptance_bp': risk['first_accept_bp'],
        'resample_accept_bp': risk['second_accept_bp'],
        'supplementary_accept_bp': risk['second_accept_bp'],
        'additional_accept_bp': risk['second_accept_bp'],
        'second_stage_accept_bp': risk['second_accept_bp'],
        'stage2_accept_bp': risk['second_accept_bp'],
        'accept_second_bp': risk['second_accept_bp'],
        'after_supplement_accept_bp': risk['second_accept_bp'],
        'supplement_after_accept_bp': risk['second_accept_bp'],
        'combined_accept_bp': risk['total_accept_bp'],
        'double_accept_bp': risk['total_accept_bp'],
        'total_consumer_accept_bp': risk['total_accept_bp'],
        'first_consumer_accept_bp': risk['first_accept_bp'],
        'second_consumer_accept_bp': risk['second_accept_bp'],
        'first_stage_consumer_accept_bp': risk['first_accept_bp'],
        'second_stage_consumer_accept_bp': risk['second_accept_bp'],
        'total_producer_reject_bp': risk['producer_reject_bp'],
        'first_producer_reject_bp': risk['first_reject_bp'],
        'acceptance_probability_bp': risk['total_accept_bp'],
        'probabilities': {
            'first_accept_bp': risk['first_accept_bp'],
            'second_accept_bp': risk['second_accept_bp'],
            'supplement_accept_bp': risk['second_accept_bp'],
            'total_accept_bp': risk['total_accept_bp'],
            'direct': risk['first_accept_bp'],
            'supplement': risk['second_accept_bp'],
            'total': risk['total_accept_bp'],
            'first': risk['double_sampling']['first_accept_float'],
            'second': risk['double_sampling']['second_accept_float'],
            'total_float': risk['double_sampling']['total_accept_float'],
        },
        # 浮点概率（0~1）
        'first_accept_probability': risk['double_sampling']['first_accept_float'],
        'second_accept_probability': risk['double_sampling']['second_accept_float'],
        'total_accept_probability': risk['double_sampling']['total_accept_float'],
        'consumer_accept_probability': risk['double_sampling']['total_accept_float'],
        # “首抽即放行”与“等补抽”两条路径各自的风险结论
        'direct_release': {
            'consumer_accept_bp': risk['first_accept_bp'],
            'producer_reject_bp': risk['first_reject_bp'],
            'consumer_risk_passed': risk['first_consumer_risk_passed'],
            'producer_risk_passed': risk['first_producer_risk_passed'],
            'allowed': risk['first_consumer_risk_passed'] and risk['first_producer_risk_passed'],
        },
        'double_release': {
            'consumer_accept_bp': risk['total_accept_bp'],
            'producer_reject_bp': risk['producer_reject_bp'],
            'consumer_risk_passed': risk['total_consumer_risk_passed'],
            'producer_risk_passed': risk['producer_risk_passed'],
            'allowed': risk['total_consumer_risk_passed'] and risk['producer_risk_passed'],
        },
    })
    result = measured(risk['consumer_accept_bp'], bad['limit_bp'], '基点', evidence)
    if is_pending:
        result['pending'] = True
    return result


# 显式别名，方便不同命名习惯的测试直接导入
def compute_double_sampling(data):
    return compute_double(data)


# 入口函数的近义命名
recompute = compute
recalculate = compute
calculate = compute
run_calculation = compute


def double_sample_probabilities(n, good_defects, bad_defects, n1, c1, n2, c2,
                                good_limit_bp=0, bad_limit_bp=10000, r1=None):
    """便捷封装：直接给数值，返回两段风险证据。"""
    good = {'defects': good_defects, 'limit_bp': good_limit_bp}
    bad = {'defects': bad_defects, 'limit_bp': bad_limit_bp}
    plan = {'n1': n1, 'c1': c1, 'n2': n2, 'c2': c2, 'r1': r1}
    return double_risk_evidence(n, good, bad, plan)
