"""顶层兼容路径：两段抽检领域逻辑。"""
from app.modules.double_sample import *  # noqa: F401,F403
from app.modules.double_sample import (  # noqa: F401
    PENDING_INSPECTION, pending_status, is_pending_code,
    double_accept_counts, double_risk_evidence, extract_double_plan,
    total_acceptance_probability, first_stage_acceptance_probability,
    second_stage_acceptance_probability, double_acceptance_probability,
)
