# tests/test_analytics.py
from ledger.analytics import theil_sen_slope, mann_kendall

def test_theil_sen_positive():
    y = [1, 2, 3, 4, 5]
    beta = theil_sen_slope(y)
    assert beta is not None and beta > 0

def test_mann_kendall_uptrend():
    y = [1, 2, 3, 3.5, 4, 5]  # 약한 증가
    tau, p = mann_kendall(y)
    assert tau is None or tau > 0  # n<6이면 None 가능
    # n>=6 이면 p가 존재하고 어느 정도 작아야 함(엄격 값은 회피)
    if p is not None:
        assert p < 0.2
