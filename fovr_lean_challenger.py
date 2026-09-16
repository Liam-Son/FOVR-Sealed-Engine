from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import subprocess, json, pandas as pd, numpy as np, hashlib, hmac, os, uuid

@dataclass(frozen=True)
class LeanRunConfig:
    enabled: bool=False
    image: str="quantconnect/lean:latest"
    project_dir: str="lean_challenger"
    timeout_seconds: int=1800
    require_signed_manifest: bool=False
    strict_result_consistency: bool=True

EXPECTED_FILES=("daily_returns.csv","positions.csv","orders.csv","summary.json")
INPUT_MANIFEST="input_manifest.json"
OUTPUT_PROVENANCE="provenance.json"

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):
            h.update(c)
    return h.hexdigest()

def _manifest_core(directory, run_nonce):
    d=Path(directory)
    files={}
    for p in sorted(d.rglob("*")):
        if p.is_file() and p.name != INPUT_MANIFEST:
            files[str(p.relative_to(d)).replace("\\","/")]={"sha256":sha256_file(p),"bytes":p.stat().st_size}
    return {"schema_version":2,"run_nonce":run_nonce,"files":files}

def _hash_core(core):
    return hashlib.sha256(json.dumps(core,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def _sign_hash(manifest_hash, key):
    return hmac.new(key.encode(),manifest_hash.encode(),hashlib.sha256).hexdigest()

def freeze_input_manifest(input_dir, signing_key=None):
    d=Path(input_dir)
    run_nonce=uuid.uuid4().hex
    core=_manifest_core(d,run_nonce)
    mh=_hash_core(core)
    m={**core,"manifest_hash":mh}
    key=signing_key or os.getenv("FOVR_MANIFEST_HMAC_KEY")
    if key:
        m["hmac_sha256"]=_sign_hash(mh,key)
    (d/INPUT_MANIFEST).write_text(json.dumps(m,indent=2),encoding="utf-8")
    return m

def verify_input_manifest(input_dir, signing_key=None, require_signature=False):
    d=Path(input_dir); p=d/INPUT_MANIFEST
    if not p.exists():
        return {"pass":False,"reason":"missing_input_manifest"}
    try:
        stored=json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"pass":False,"reason":"invalid_manifest_json","error":repr(e)}
    for k in ("schema_version","run_nonce","files","manifest_hash"):
        if k not in stored:
            return {"pass":False,"reason":"manifest_missing_field","field":k}
    core={"schema_version":stored["schema_version"],"run_nonce":stored["run_nonce"],"files":stored["files"]}
    stored_core_hash=_hash_core(core)
    if stored_core_hash != stored["manifest_hash"]:
        return {"pass":False,"reason":"manifest_self_hash_mismatch"}
    actual_hash=_hash_core(_manifest_core(d,stored["run_nonce"]))
    if actual_hash != stored["manifest_hash"]:
        return {"pass":False,"reason":"input_files_changed"}
    key=signing_key or os.getenv("FOVR_MANIFEST_HMAC_KEY")
    sig=stored.get("hmac_sha256")
    if require_signature and not sig:
        return {"pass":False,"reason":"manifest_signature_required"}
    if sig:
        if not key:
            return {"pass":False,"reason":"manifest_signature_key_unavailable"}
        if not hmac.compare_digest(sig,_sign_hash(stored["manifest_hash"],key)):
            return {"pass":False,"reason":"manifest_signature_invalid"}
    return {"pass":True,"manifest_hash":stored["manifest_hash"],"run_nonce":stored["run_nonce"],"signed":bool(sig)}

def environment_status(cfg=LeanRunConfig()):
    try:
        ok=subprocess.run(["docker","--version"],capture_output=True,timeout=10).returncode==0
    except Exception:
        ok=False
    return {"enabled":cfg.enabled,"docker_available":ok,"project_dir_exists":Path(cfg.project_dir).exists(),
            "ready":bool(cfg.enabled and ok and Path(cfg.project_dir).exists())}

def _recompute_cumulative_return(daily):
    r=pd.to_numeric(daily["net_return"],errors="coerce")
    if r.isna().any() or not np.isfinite(r).all():
        raise ValueError("non-finite daily returns")
    return float((1.0+r).prod()-1.0)

def _recompute_average_turnover(positions):
    x=positions.copy()
    x["date"]=pd.to_datetime(x["date"],errors="coerce")
    x["weight"]=pd.to_numeric(x["weight"],errors="coerce")
    if x["date"].isna().any() or x["weight"].isna().any() or not np.isfinite(x["weight"]).all():
        raise ValueError("invalid positions")
    if x.duplicated(["date","symbol"]).any():
        raise ValueError("duplicate position keys")
    piv=x.pivot(index="date",columns="symbol",values="weight").fillna(0.0).sort_index()
    prev=piv.shift(1).fillna(0.0)
    turn=(piv-prev).abs().sum(axis=1)
    return float(turn.mean()) if len(turn) else 0.0

def validate_result_contract(output_dir, expected_input_manifest_hash=None, expected_run_nonce=None,
                             strict_consistency=True, metric_tolerance=1e-8):
    d=Path(output_dir)
    missing=[f for f in EXPECTED_FILES if not (d/f).exists()]
    if missing:
        return {"pass":False,"reason":"missing_files","missing":missing}
    try:
        daily=pd.read_csv(d/"daily_returns.csv"); pos=pd.read_csv(d/"positions.csv"); orders=pd.read_csv(d/"orders.csv")
        summary=json.loads((d/"summary.json").read_text(encoding="utf-8"))
    except Exception as e:
        return {"pass":False,"reason":"parse_error","error":repr(e)}
    req={"daily_returns.csv":{"date","net_return"},"positions.csv":{"date","symbol","weight"},"orders.csv":{"date","symbol","side"}}
    frames={"daily_returns.csv":daily,"positions.csv":pos,"orders.csv":orders}
    miss={k:sorted(v-set(frames[k].columns)) for k,v in req.items() if v-set(frames[k].columns)}
    if miss:
        return {"pass":False,"reason":"schema_error","missing_columns":miss}
    if daily.empty or pos.empty:
        return {"pass":False,"reason":"empty_core_results"}
    for k in ("cumulative_return","average_daily_turnover"):
        if k not in summary:
            return {"pass":False,"reason":"summary_missing_metric","metric":k}
    provenance={}
    if expected_input_manifest_hash is not None or expected_run_nonce is not None:
        pp=d/OUTPUT_PROVENANCE
        if not pp.exists():
            return {"pass":False,"reason":"missing_output_provenance"}
        provenance=json.loads(pp.read_text(encoding="utf-8"))
        if expected_input_manifest_hash is not None and provenance.get("input_manifest_hash") != expected_input_manifest_hash:
            return {"pass":False,"reason":"input_manifest_hash_mismatch"}
        if expected_run_nonce is not None and provenance.get("run_nonce") != expected_run_nonce:
            return {"pass":False,"reason":"run_nonce_mismatch"}
    consistency={}
    if strict_consistency:
        cr=_recompute_cumulative_return(daily)
        tr=_recompute_average_turnover(pos)
        scr=float(summary["cumulative_return"]); strn=float(summary["average_daily_turnover"])
        consistency={"cumulative_return":{"reported":scr,"recomputed":cr},"average_daily_turnover":{"reported":strn,"recomputed":tr}}
        if abs(scr-cr)>metric_tolerance:
            return {"pass":False,"reason":"summary_cumulative_return_mismatch","consistency":consistency}
        if abs(strn-tr)>metric_tolerance:
            return {"pass":False,"reason":"summary_turnover_mismatch","consistency":consistency}
    files={f:sha256_file(d/f) for f in EXPECTED_FILES}
    return {"pass":True,"files":files,"provenance":provenance,"consistency":consistency}

def run_lean_challenger(frozen_input_dir,output_dir,cfg=LeanRunConfig()):
    inp=Path(frozen_input_dir); out=Path(output_dir)
    chk=verify_input_manifest(inp,require_signature=cfg.require_signed_manifest)
    if not chk["pass"]:
        return {"pass":False,"status":"INPUT_MANIFEST_INVALID","input_manifest":chk}
    env=environment_status(cfg)
    if not env["ready"]:
        return {"pass":False,"status":"LEAN_NOT_READY","environment":env}
    out.mkdir(parents=True,exist_ok=True)
    try:
        p=subprocess.run(["docker","run","--rm","-v",f"{inp.resolve()}:/fovr-input:ro","-v",f"{out.resolve()}:/fovr-output",cfg.image],
                         capture_output=True,text=True,timeout=cfg.timeout_seconds)
    except subprocess.TimeoutExpired:
        return {"pass":False,"status":"LEAN_TIMEOUT"}
    if p.returncode!=0:
        return {"pass":False,"status":"LEAN_EXECUTION_FAILED","returncode":p.returncode}
    c=validate_result_contract(out,chk["manifest_hash"],chk["run_nonce"],strict_consistency=cfg.strict_result_consistency)
    return {"pass":c["pass"],"status":"PASS" if c["pass"] else "LEAN_RESULT_INVALID","contract":c}
