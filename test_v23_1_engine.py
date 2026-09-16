from __future__ import annotations
import numpy as np
import pandas as pd
from fovr_dual_engine_gate import dual_engine_gate
from fovr_portfolio_benchmarks import benchmark_portfolios
from fovr_report_validator import validate_report
from fovr_sleeves import balance_sheet_sleeve, combine_sleeves, dollar_neutral_weights, iv90_skew_sleeve, range_reversal_sleeve, claim_boundary

def _panel(n=8, t=40, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-02", periods=t)
    cols = [f"S{i}" for i in range(n)]
    close = pd.DataFrame(100 + rng.normal(0, 1, size=(t, n)).cumsum(axis=0), index=idx, columns=cols)
    return close, close + 1, close - 1

def test_sleeves_are_lagged_and_finite():
    close, high, low = _panel()
    b = balance_sheet_sleeve(close.pct_change())
    k = iv90_skew_sleeve(close * 0 + 0.25, close * 0 + 0.20)
    r = range_reversal_sleeve(close, high, low, lookback=10)
    combo = combine_sleeves({"balance_sheet": b, "iv90_skew": k, "range_reversal": r})
    assert combo.shape == close.shape
    assert combo.iloc[0].isna().all()
    w = dollar_neutral_weights(combo.iloc[15:].fillna(0), long_n=3, short_n=3, cap=0.2)
    assert abs(w.iloc[-1].sum()) < 1e-8

def test_claim_boundary_is_closed():
    assert claim_boundary()["live_edge_claimed"] is False

def test_dual_engine_pass_on_identical_books():
    dates = pd.bdate_range("2024-06-03", periods=40)
    daily = pd.DataFrame({"date": dates, "net_return": 0.001})
    pos = pd.DataFrame({"date": np.repeat(dates, 2), "symbol": ["A", "B"] * len(dates), "weight": [0.5, -0.5] * len(dates)})
    summary = {"cumulative_return": float((1.001 ** 40) - 1), "average_daily_turnover": 0.025}
    g = dual_engine_gate(daily, daily.copy(), pos, pos.copy(), summary, summary.copy())
    assert g["pass"], g

def test_report_validator_fail_closed():
    r = validate_report({"data_quality": "ok"})
    assert r["pass"] is False

def test_benchmarks_sum_to_one():
    idx = pd.bdate_range("2024-01-02", periods=80)
    r = pd.DataFrame(np.random.default_rng(1).normal(0, 0.01, size=(80, 4)), index=idx, columns=list("ABCD"))
    for name, w in benchmark_portfolios(r).items():
        assert abs(w.sum() - 1) < 1e-8, name
