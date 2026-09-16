import numpy as np, pandas as pd
def equal_weight(cols): return pd.Series(1/len(cols),index=cols,dtype=float) if cols else pd.Series(dtype=float)
def inverse_volatility_weights(r,lookback=63):
    v=r.tail(lookback).std(ddof=1).replace(0,np.nan); w=(1/v).replace([np.inf,-np.inf],np.nan).fillna(0)
    return w/w.sum() if w.sum()>0 else equal_weight(list(r.columns))
def minimum_variance_weights(r,lookback=126,ridge=1e-5):
    x=r.tail(lookback); cols=list(x.columns)
    if not cols: return pd.Series(dtype=float)
    c=x.cov().fillna(0).to_numpy()+ridge*np.eye(len(cols)); inv=np.linalg.pinv(c); o=np.ones(len(cols))
    d=float(o@inv@o); w=(inv@o)/d if abs(d)>1e-12 else o/len(cols); w=np.maximum(w,0); w=w/w.sum()
    return pd.Series(w,index=cols)
def benchmark_portfolios(r): return {"equal_weight":equal_weight(list(r.columns)),"inverse_volatility":inverse_volatility_weights(r),"minimum_variance":minimum_variance_weights(r)}
def ex_ante_vol(w,r):
    cols=[c for c in w.index if c in r.columns]; a=w[cols].to_numpy(); c=r[cols].cov().fillna(0).to_numpy()*252
    return float(np.sqrt(max(a@c@a,0))) if cols else 0.0
