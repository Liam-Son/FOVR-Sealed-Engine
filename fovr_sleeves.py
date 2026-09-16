from __future__ import annotations
import numpy as np
import pandas as pd

SLEEVE_NAMES = ("balance_sheet", "iv90_skew", "range_reversal")

def lag(x, periods: int = 1):
    return x.shift(periods)

def zscore_cs(x: pd.DataFrame) -> pd.DataFrame:
    mu = x.mean(axis=1)
    sd = x.std(axis=1).replace(0, np.nan)
    return x.sub(mu, axis=0).div(sd, axis=0)

def balance_sheet_sleeve(current_ratio_delta: pd.DataFrame) -> pd.DataFrame:
    return zscore_cs(lag(current_ratio_delta))

def iv90_skew_sleeve(put_iv90: pd.DataFrame, call_iv90: pd.DataFrame) -> pd.DataFrame:
    return zscore_cs(lag(put_iv90 - call_iv90))

def range_reversal_sleeve(close, high, low, lookback: int = 20) -> pd.DataFrame:
    hh = high.rolling(lookback, min_periods=lookback).max()
    ll = low.rolling(lookback, min_periods=lookback).min()
    width = (hh - ll).replace(0, np.nan)
    loc = (close - ll) / width
    return zscore_cs(lag(1.0 - loc))

def combine_sleeves(sleeves: dict, weights: dict | None = None) -> pd.DataFrame:
    weights = weights or {k: 1.0 / len(sleeves) for k in sleeves}
    acc = None
    wsum = 0.0
    for name, frame in sleeves.items():
        w = float(weights.get(name, 0.0))
        acc = w * frame if acc is None else acc.add(w * frame, fill_value=0.0)
        wsum += w
    if acc is None or wsum == 0:
        raise ValueError("no sleeves")
    return acc / wsum

def dollar_neutral_weights(score: pd.DataFrame, long_n: int = 5, short_n: int = 5, cap: float = 0.03) -> pd.DataFrame:
    rows = []
    for dt, row in score.iterrows():
        s = row.dropna()
        w = pd.Series(0.0, index=score.columns)
        if len(s) < long_n + short_n:
            rows.append(w)
            continue
        longs = s.nlargest(long_n).index
        shorts = s.nsmallest(short_n).index
        if longs.size:
            w.loc[longs] = 1.0 / longs.size
        if shorts.size:
            w.loc[shorts] = -1.0 / shorts.size
        w = w.clip(-cap, cap)
        gp, gn = w[w > 0].sum(), -w[w < 0].sum()
        if gp > 0:
            w[w > 0] *= 0.5 / gp
        if gn > 0:
            w[w < 0] *= 0.5 / gn
        rows.append(w)
    return pd.DataFrame(rows, index=score.index)

def claim_boundary() -> dict:
    return {"software": "sleeve definitions + portfolio mapping", "live_edge_claimed": False}
