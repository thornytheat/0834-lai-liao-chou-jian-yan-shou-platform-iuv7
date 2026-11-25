from app.business import measured


def compute(data):
    from math import comb
    n,sample,c,good,bad,observed = data
    total = comb(n,sample)

    def accepted(defects):
        low = max(0,sample-(n-defects))
        high = min(defects,sample,c)
        return sum(comb(defects,k)*comb(n-defects,sample-k) for k in range(low,high+1))

    good_reject = ((total-accepted(good['defects']))*10000+total-1)//total
    bad_accept = (accepted(bad['defects'])*10000+total-1)//total
    evidence = {'producer_reject_bp':good_reject,'consumer_accept_bp':bad_accept,'acceptance_number':c,'observed_defects':observed,'observed_passed':observed<=c,'producer_risk_passed':good_reject<=good['limit_bp']}
    return measured(bad_accept,bad['limit_bp'],'基点',evidence)
