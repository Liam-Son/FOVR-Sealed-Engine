from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class DualEngineTolerance:
    daily_return_abs: float=1e-6
    cumulative_return_abs: float=1e-4
    turnover_abs: float=1e-4
    position_weight_abs: float=1e-4
    min_overlap_days: int=30
    min_position_rows: int=1
    require_same_position_keys: bool=True
    require_same_daily_keys: bool=True
    require_position_dates_cover_daily_dates: bool=True

def _req(df,cols,name):
    m=set(cols)-set(df.columns)
    return None if not m else {"pass":False,"reason":f"{name}_missing_columns","missing":sorted(m)}

def _norm_daily(x,name):
    e=_req(x,{"date","net_return"},name)
    if e: return None,e
    z=x.copy(); z["date"]=pd.to_datetime(z["date"],errors="coerce"); z["net_return"]=pd.to_numeric(z["net_return"],errors="coerce")
    if z["date"].isna().any(): return None,{"pass":False,"reason":"invalid_daily_dates","side":name}
    if z["date"].duplicated().any(): return None,{"pass":False,"reason":"duplicate_daily_dates","side":name}
    if not np.isfinite(z["net_return"]).all(): return None,{"pass":False,"reason":"non_finite_daily_returns","side":name}
    return z.sort_values("date"),None

def _norm_pos(x,name):
    e=_req(x,{"date","symbol","weight"},name)
    if e: return None,e
    z=x.copy(); z["date"]=pd.to_datetime(z["date"],errors="coerce"); z["symbol"]=z["symbol"].astype(str); z["weight"]=pd.to_numeric(z["weight"],errors="coerce")
    if z["date"].isna().any(): return None,{"pass":False,"reason":"invalid_position_dates","side":name}
    if z.duplicated(["date","symbol"]).any(): return None,{"pass":False,"reason":"duplicate_position_keys","side":name}
    if not np.isfinite(z["weight"]).all(): return None,{"pass":False,"reason":"non_finite_position_weights","side":name}
    return z,None

def compare_daily(n,l,tol):
    n,e=_norm_daily(n,"native")
    if e: return e
    l,e=_norm_daily(l,"lean")
    if e: return e
    nk=set(n.date); lk=set(l.date)
    if tol.require_same_daily_keys and nk!=lk:
        return {"pass":False,"reason":"daily_key_mismatch","native_only":len(nk-lk),"lean_only":len(lk-nk)}
    z=n.merge(l,on="date",suffixes=("_native","_lean"))
    if len(z)<tol.min_overlap_days: return {"pass":False,"reason":"insufficient_daily_overlap","overlap":len(z)}
    d=(z.net_return_native-z.net_return_lean).abs()
    return {"pass":bool((d<=tol.daily_return_abs).all()),"overlap":len(z),"max_abs_diff":float(d.max())}

def compare_positions(n,l,tol):
    n,e=_norm_pos(n,"native")
    if e: return e
    l,e=_norm_pos(l,"lean")
    if e: return e
    if len(n)<tol.min_position_rows or len(l)<tol.min_position_rows: return {"pass":False,"reason":"insufficient_position_rows"}
    nk=set(zip(n.date,n.symbol)); lk=set(zip(l.date,l.symbol))
    if tol.require_same_position_keys and nk!=lk:
        return {"pass":False,"reason":"position_key_mismatch","native_only":len(nk-lk),"lean_only":len(lk-nk)}
    z=n.merge(l,on=["date","symbol"],how="outer",suffixes=("_native","_lean")).fillna({"weight_native":0,"weight_lean":0})
    d=(z.weight_native-z.weight_lean).abs()
    return {"pass":bool((d<=tol.position_weight_abs).all()),"rows":len(z),"max_abs_diff":float(d.max())}

def compare_summary(a,b,tol):
    c={}
    for k,eps in (("cumulative_return",tol.cumulative_return_abs),("average_daily_turnover",tol.turnover_abs)):
        try: x=float(a[k]); y=float(b[k])
        except Exception: c[k]={"pass":False,"reason":"missing_or_non_numeric"}; continue
        if not np.isfinite(x) or not np.isfinite(y): c[k]={"pass":False,"reason":"non_finite_metric"}; continue
        d=abs(x-y); c[k]={"pass":d<=eps,"abs_diff":d}
    return {"pass":all(v["pass"] for v in c.values()),"checks":c}

def _intra_engine_alignment(daily,positions,name,tol):
    d,e=_norm_daily(daily,name+"_daily")
    if e: return e
    p,e=_norm_pos(positions,name+"_positions")
    if e: return e
    dd=set(d.date); pdays=set(p.date)
    if tol.require_position_dates_cover_daily_dates and dd!=pdays:
        return {"pass":False,"reason":"daily_position_date_mismatch","side":name,"daily_only":len(dd-pdays),"position_only":len(pdays-dd)}
    return {"pass":True,"days":len(dd)}

def dual_engine_gate(nd,ld,np_,lp,ns,ls,tol=DualEngineTolerance()):
    checks={"native_alignment":_intra_engine_alignment(nd,np_,"native",tol),
            "lean_alignment":_intra_engine_alignment(ld,lp,"lean",tol),
            "daily_returns":compare_daily(nd,ld,tol),
            "positions":compare_positions(np_,lp,tol),
            "summary":compare_summary(ns,ls,tol)}
    return {"pass":all(v.get("pass",False) for v in checks.values()),"checks":checks,
            "failed":[k for k,v in checks.items() if not v.get("pass",False)],"tolerance":asdict(tol)}
