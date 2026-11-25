from flask import jsonify

LABELS = {
    'FILE_TOO_LARGE':'文件超过 256 KiB', 'FILE_EMPTY':'文件没有内容', 'FILE_BLANK':'文件只有空白',
    'HEADER_ONLY':'文件只有标题行', 'HEADER_MISMATCH':'列名与字段字典不一致', 'ENCODING_INVALID':'请使用 UTF-8 CSV',
    'CSV_MALFORMED':'CSV 引号或行格式异常', 'ROW_LIMIT':'文件超过 2000 行', 'FILE_REQUIRED':'请选择 CSV 文件',
    'RUN_NOT_FOUND':'批次不存在', 'REVIEW_FIELDS':'请填写 3 至 200 字复核意见', 'STALE_REVIEW':'批次已更新，请刷新',
    'RUN_FINALIZED':'批次已签发', 'UNRESOLVED_ISSUES':'存在待处理差异', 'SAMPLE_UNKNOWN':'样例不存在', 'STAGE_UNKNOWN':'处理阶段不存在',
    'CORRECTION_FIELDS':'补抽更正内容不完整', 'IDEMPOTENCY_CONFLICT':'相同幂等键对应不同请求',
    'RECEIPT_NOT_FOUND':'签发回执不存在',
}

NOT_FOUND = {'RUN_NOT_FOUND','SAMPLE_UNKNOWN','STAGE_UNKNOWN','RECEIPT_NOT_FOUND'}
CONFLICT = {'STALE_REVIEW','RUN_FINALIZED','UNRESOLVED_ISSUES','IDEMPOTENCY_CONFLICT'}


def response(error):
    code = error.code
    if code in NOT_FOUND:
        status = 404
    elif code in CONFLICT:
        status = 409
    elif code == 'FILE_TOO_LARGE':
        status = 413
    else:
        status = 422
    return jsonify(code=code,message=LABELS.get(code,code)),status
