from app.modules.double_sample import DOUBLE_KINDS, PENDING_INSPECTION

COLUMNS = ('lot', 'samples', 'acceptance', 'defects', 'limit_bp')
# 前四个为基础词表，顺序保持不变（测试以 KINDS[0] 构造 plan 行）。
KINDS = ('plan', 'producer', 'consumer', 'observed', *DOUBLE_KINDS)
PENDING_STATUS = PENDING_INSPECTION
PROJECT = {'name': '来料抽检验收台', 'actor': '供应商质量专员', 'stages': [('intake', '样例采信'), ('prepare', '样本计划核对'), ('calculate', '接收概率复算'), ('policy', '批次放行'), ('balance', '运行对账')], 'chart': '抽检风险', 'mark': '来'}
