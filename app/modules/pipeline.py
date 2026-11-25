from app.modules.grouping import case_groups
from app.modules.prepare import prepare
from app.modules.calculate import compute
from app.modules.policy import policy
from app.modules.reconcile import balance
from app.business import DomainIssue
from app.intake.service import inspect
from app.modules.double_sample import pending_status


def evaluate(rows, stage, overlay=None):
    case = {'case':rows[0]['case'],'records':[r['record'] for r in rows], 'status':'READY'}
    try:
        case['prep'], payload = prepare(rows, overlay)
        is_double = isinstance(payload, dict) and payload.get('double')
        if is_double:
            plan = payload['plan']
            summary = {
                'plan_type': 'double',
                'state': plan['state'],
                'pending': bool(plan.get('pending')),
                'complete': plan['complete'],
                'lot': payload['n'],
                'first_samples': plan['n1'], 'first_acceptance': plan['c1'],
                'second_samples': plan['n2'], 'second_acceptance': plan['c2'],
                'planned_second_samples': plan['n2'],
                'second_sample_count': plan['m2'],
                'actual_second_samples': plan['m2'],
                'first_defects': plan['d1'], 'second_defects': plan['d2'],
                'total_defects': plan['d1'] + plan['d2'],
                'observed_passed': plan['observed_passed'],
            }
            case['double_sample'] = summary
            case['two_stage'] = summary
            case['supplement'] = summary
        is_pending = is_double and payload['plan'].get('pending')
        if is_pending:
            # 件数未到计划值：即使只跑到 prepare 阶段也明确“待验”。
            plan = payload['plan']
            case['status'] = pending_status()
            case['pending'] = True
            case['progress'] = {
                'state': plan['state'],
                'first_samples': plan['m1'],
                'second_samples': plan['m2'],
                'planned_second_samples': plan['n2'],
                'total_defects_so_far': plan['d1'] + plan['d2'],
            }
        if stage >= 3:
            case['measure'] = compute(payload)
        if stage >= 4:
            verdict = policy(case['measure'], payload)
            case.update(verdict)
    except DomainIssue as error:
        case['status'] = error.code
    return case


def run(data, stage=5, overlays=None):
    intake = inspect(data)
    output = {'intake': {k:v for k,v in intake.items() if k!='rows'}}
    # 保留已采信行，供“补抽更正”后在同一运行上重算。
    output['_rows'] = intake['rows']
    if stage == 1:
        return output
    overlays = overlays or {}
    cases = [evaluate(rows, stage, overlays.get(code)) for code, rows in case_groups(intake['rows'])]
    output['cases'] = cases
    if stage >= 5:
        output['balance'] = balance(intake,cases)
    return output


def rebuild(report):
    """依据 report['_rows'] 与 report['overlays'] 重新评估并刷新对账。"""
    rows = report.get('_rows') or []
    overlays = report.get('overlays') or {}
    cases = [evaluate(group_rows, 5, overlays.get(code))
             for code, group_rows in case_groups(rows)]
    intake = dict(report.get('intake') or {})
    intake['rows'] = rows
    report['cases'] = cases
    report['balance'] = balance(intake, cases)
    return report
