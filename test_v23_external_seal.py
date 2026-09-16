from pathlib import Path
import tempfile, json, os
from fovr_state_store import FOVRStateStore, GENESIS, record_hash, canonical
from fovr_production_controls import validate_environment

def test_signed_audit_detects_full_reseal():
    with tempfile.TemporaryDirectory() as td:
        db=FOVRStateStore(Path(td)/"x.db")
        db.start_run("r","FOVR","23","research",{})
        db.record_order("o","r","A","BUY",1,"NEW")
        db.complete_run("r",signing_key="secret")
        assert db.verify_audit_chain("r",signing_key="secret",require_seal=True)["pass"]
        rows=db.conn.execute("""SELECT event_id,event_type,created_at_utc,payload_json FROM audit_events WHERE run_id='r' ORDER BY event_id""").fetchall()
        prev=GENESIS
        for eid,etype,ts,pj in rows:
            if etype=="ORDER_RECORDED":
                payload=json.loads(pj); payload["quantity"]=999.0; pj=canonical(payload)
            rh=record_hash("r",etype,ts,pj,prev)
            db.conn.execute("UPDATE audit_events SET payload_json=?,prev_hash=?,record_hash=? WHERE event_id=?",(pj,prev,rh,eid))
            prev=rh
        db.conn.execute("UPDATE strategy_runs SET audit_head_hash=? WHERE run_id='r'",(prev,))
        db.conn.commit()
        r=db.verify_audit_chain("r",signing_key="secret",require_seal=True)
        assert not r["pass"] and r["reason"]=="audit_seal_invalid"
        db.close()

def test_wrong_audit_key_fails():
    with tempfile.TemporaryDirectory() as td:
        db=FOVRStateStore(Path(td)/"x.db")
        db.start_run("r","FOVR","23","research",{})
        db.complete_run("r",signing_key="secret")
        r=db.verify_audit_chain("r",signing_key="wrong",require_seal=True)
        assert not r["pass"] and r["reason"]=="audit_seal_invalid"
        db.close()

def test_prod_requires_both_external_keys():
    keys=("FOVR_ENV","FOVR_DATA_LICENSE_MODE","FOVR_LOG_DIR","FOVR_MANIFEST_HMAC_KEY","FOVR_AUDIT_HMAC_KEY")
    old={k:os.environ.get(k) for k in keys}
    try:
        os.environ["FOVR_ENV"]="prod"; os.environ["FOVR_DATA_LICENSE_MODE"]="commercial"; os.environ["FOVR_LOG_DIR"]="./logs"
        os.environ.pop("FOVR_MANIFEST_HMAC_KEY",None); os.environ.pop("FOVR_AUDIT_HMAC_KEY",None)
        r=validate_environment()
        assert not r["pass"]
        os.environ["FOVR_MANIFEST_HMAC_KEY"]="m"; os.environ["FOVR_AUDIT_HMAC_KEY"]="a"
        assert validate_environment()["pass"]
    finally:
        for k,v in old.items():
            if v is None: os.environ.pop(k,None)
            else: os.environ[k]=v

if __name__=="__main__":
    tests=[v for k,v in list(globals().items()) if k.startswith("test_") and callable(v)]
    fails=[]
    for fn in tests:
        try: fn(); print("PASS ",fn.__name__)
        except Exception as e: fails.append((fn.__name__,repr(e))); print("FAIL ",fn.__name__,repr(e))
    if fails: raise SystemExit(fails)
    print(f"\nALL V23 TESTS PASSED ({len(tests)}/{len(tests)})")
