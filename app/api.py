from flask import Blueprint, Response, current_app, jsonify, request

from app.business import DomainIssue
from app.evidence.render import artifact
from app.inputs import read_input
from app.modules.pipeline import run
from app.review.service import approve, correct, execute, extract_key, review

api = Blueprint('api',__name__,url_prefix='/api')
STAGES = {'intake':1,'prepare':2,'calculate':3,'policy':4,'balance':5}


def _json_body():
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return payload
    # 兼容 form-data / x-www-form-urlencoded 以及查询串传参。
    if request.form:
        return {key: _coerce_form(value) for key, value in request.form.items()}
    if request.args:
        return {key: _coerce_form(value) for key, value in request.args.items()}
    return payload


def _coerce_form(value):
    """表单值都是字符串；尽量还原 revision/件数/缺陷数等整数。"""
    if isinstance(value, str) and value.lstrip('-').isdigit():
        try:
            return int(value)
        except ValueError:
            return value
    return value


def _with_header_key(payload):
    """把标准幂等头并入请求体（不覆盖体中显式键）。"""
    if not isinstance(payload, dict):
        return payload
    if not extract_key(payload):
        header_key = (request.headers.get('Idempotency-Key')
                      or request.headers.get('X-Idempotency-Key')
                      or request.headers.get('X-Request-Id'))
        if header_key:
            payload = dict(payload)
            payload['idempotency_key'] = header_key
    return payload


@api.post('/stages/<stage>')
def preview(stage):
    if stage not in STAGES:
        raise DomainIssue('STAGE_UNKNOWN')
    return jsonify(run(read_input(),STAGES[stage]))


@api.route('/runs',methods=['GET','POST'])
def runs():
    store = current_app.extensions['runs']
    if request.method == 'GET':
        return jsonify(items=store.list())
    return jsonify(execute(store,read_input()))


@api.route('/runs/<run_id>', methods=['GET','PATCH'])
def batch(run_id):
    store = current_app.extensions['runs']
    if request.method == 'GET':
        return jsonify(store.load(run_id))
    payload = _with_header_key(_json_body())
    return jsonify(review(store,run_id,payload))


def _correction_response(run_id):
    store = current_app.extensions['runs']
    payload = _with_header_key(_json_body())
    return jsonify(correct(store, run_id, payload or {}))


@api.route('/runs/<run_id>/correction', methods=['POST','PATCH','PUT'])
def correction_route(run_id):
    return _correction_response(run_id)


@api.route('/runs/<run_id>/supplement', methods=['POST','PATCH','PUT'])
def supplement_route(run_id):
    return _correction_response(run_id)


@api.route('/runs/<run_id>/inspection', methods=['POST','PATCH','PUT'])
def inspection_route(run_id):
    return _correction_response(run_id)


@api.post('/runs/<run_id>/approve')
def approve_route(run_id):
    store = current_app.extensions['runs']
    payload = _with_header_key(_json_body() or {})
    if not isinstance(payload, dict):
        raise DomainIssue('REVIEW_FIELDS')
    payload.setdefault('status', 'APPROVED')
    return jsonify(review(store, run_id, payload))


@api.get('/runs/<run_id>/receipt')
def receipt_route(run_id):
    store = current_app.extensions['runs']
    key = request.args.get('key') or request.headers.get('Idempotency-Key')
    receipt = store.get_receipt(key) if key else None
    if receipt is None or receipt['run_id'] != run_id:
        raise DomainIssue('RECEIPT_NOT_FOUND')
    return jsonify(receipt['body'])


@api.get('/runs/<run_id>/evidence')
def export(run_id):
    report = current_app.extensions['runs'].load(run_id)
    return Response(artifact(report),mimetype='application/json', headers={
        'Content-Disposition':f'attachment; filename="review-{report["id"][:12]}.json"',
        'Cache-Control':'no-store',
    })
