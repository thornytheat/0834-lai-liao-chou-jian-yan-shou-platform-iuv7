"""兼容别名：两段抽检计算。"""
from app.modules.double_sample import *  # noqa: F401,F403
from app.modules.double_sample import (  # noqa: F401
    PENDING_INSPECTION, AliasStatus, pending_status, is_pending_code,
    bp_ceil, hypergeom_count, hypergeom_point, accepted_count,
    first_accept_count, second_joint_count, double_accept_counts,
    double_risk_evidence, extract_double_plan,
    first_stage_acceptance_probability, second_stage_acceptance_probability,
    total_acceptance_probability, double_acceptance_probability,
    acceptance_probability, DOUBLE_KINDS,
)
from app.modules.calculate import compute_double, compute_double_sampling  # noqa: F401
