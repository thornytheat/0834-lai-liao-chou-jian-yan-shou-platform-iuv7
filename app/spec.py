COLUMNS = ('lot', 'samples', 'acceptance', 'defects', 'limit_bp')
KINDS = ('plan', 'producer', 'consumer', 'observed')
PROJECT = {'name': '来料抽检验收台', 'actor': '供应商质量专员', 'stages': [('intake', '样例采信'), ('prepare', '样本计划核对'), ('calculate', '接收概率复算'), ('policy', '批次放行'), ('balance', '运行对账')], 'chart': '抽检风险', 'mark': '来'}
