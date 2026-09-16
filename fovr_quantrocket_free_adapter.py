from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

def normalize_quantrocket_export(path: str|Path) -> pd.DataFrame:
    p=Path(path)
    x=pd.read_parquet(p) if p.suffix.lower()==".parquet" else pd.read_csv(p)
    lower={c.lower():c for c in x.columns}
    date_col=lower.get("date") or lower.get("datetime") or lower.get("timestamp")
    symbol_col=lower.get("symbol") or lower.get("ticker")
    sid_col=lower.get("sid") or lower.get("security_id") or lower.get("permno")
    close_col=lower.get("close")
    open_col=lower.get("open"); high_col=lower.get("high"); low_col=lower.get("low"); volume_col=lower.get("volume")
    if not date_col or not symbol_col or not close_col:
        raise ValueError("Need date, symbol/ticker and close columns")
    out=pd.DataFrame({
        "date":pd.to_datetime(x[date_col]),
        "symbol":x[symbol_col].astype(str),
        "security_id":x[sid_col].astype(str) if sid_col else x[symbol_col].astype(str),
        "open":pd.to_numeric(x[open_col],errors="coerce") if open_col else np.nan,
        "high":pd.to_numeric(x[high_col],errors="coerce") if high_col else np.nan,
        "low":pd.to_numeric(x[low_col],errors="coerce") if low_col else np.nan,
        "close":pd.to_numeric(x[close_col],errors="coerce"),
        "volume":pd.to_numeric(x[volume_col],errors="coerce") if volume_col else np.nan,
    })
    if "delisted" in lower:
        out["is_delisted"]=x[lower["delisted"]].astype(bool)
    elif "datedelisted" in lower:
        out["is_delisted"]=pd.to_datetime(x[lower["datedelisted"]],errors="coerce").notna()
    else:
        out["is_delisted"]=False
    out["universe_member_pit"]=True
    return out.sort_values(["security_id","date"])
