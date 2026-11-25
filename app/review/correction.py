"""补抽更正服务的兼容导入路径。"""
from app.review.service import (  # noqa: F401
    correct, record_correction, submit_correction, apply_correction,
    correct_review, update_review, patch_run, update_run,
    correct_supplement, record_supplement, submit_supplement,
    supplement_review, record_supplement_result, supplement,
    update_inspection, review, approve,
)
