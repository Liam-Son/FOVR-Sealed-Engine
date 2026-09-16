from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import sqlite3, json, hashlib, hmac, os

GENESIS="0"*64

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS strategy_runs(
 run_id TEXT PRIMARY KEY,
 strategy_id TEXT NOT NULL,
 version TEXT NOT NULL,
 mode TEXT NOT NULL,
 status TEXT NOT NULL,
 started_at_utc TEXT NOT NULL,
 completed_at_utc TEXT,
 metadata_json TEXT NOT NULL,
 audit_head_hash TEXT NOT NULL DEFAULT '',
 audit_count INTEGER NOT NULL DEFAULT 0,
 audit_seal_hmac TEXT,
 audit_seal_version INTEGER
);

CREATE TABLE IF NOT EXISTS orders(
 order_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL,
 symbol TEXT NOT NULL,
 side TEXT NOT NULL,
 quantity REAL NOT NULL,
 status TEXT NOT NULL,
 created_at_utc TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES strategy_runs(run_id)
);

CREATE TABLE IF NOT EXISTS positions(
 run_id TEXT NOT NULL,
 symbol TEXT NOT NULL,
 quantity REAL NOT NULL,
 market_value REAL,
 updated_at_utc TEXT NOT NULL,
 PRIMARY KEY(run_id,symbol),
 FOREIGN KEY(run_id) REFERENCES strategy_runs(run_id)
);

CREATE TABLE IF NOT EXISTS audit_events(
 event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 run_id TEXT NOT NULL,
 event_type TEXT NOT NULL,
 created_at_utc TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 prev_hash TEXT NOT NULL,
 record_hash TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES strategy_runs(run_id)
);
"""

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def canonical(payload):
    return json.dumps(payload,sort_keys=True,separators=(",",":"))

def record_hash(run_id,event_type,created_at_utc,payload_json,prev_hash):
    return hashlib.sha256("|".join([run_id,event_type,created_at_utc,payload_json,prev_hash]).encode()).hexdigest()

def _seal_message(run_id,status,completed_at_utc,audit_head_hash,audit_count,version=1):
    return canonical({
        "version":version,
        "run_id":run_id,
        "status":status,
        "completed_at_utc":completed_at_utc,
        "audit_head_hash":audit_head_hash,
        "audit_count":int(audit_count),
    })

def _seal_hmac(message,key):
    return hmac.new(key.encode(),message.encode(),hashlib.sha256).hexdigest()

class FOVRStateStore:
    def __init__(self,path="data/fovr_state.db"):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        cols={r[1] for r in self.conn.execute("PRAGMA table_info(strategy_runs)").fetchall()}
        additions={
            "audit_head_hash":"TEXT NOT NULL DEFAULT ''",
            "audit_count":"INTEGER NOT NULL DEFAULT 0",
            "audit_seal_hmac":"TEXT",
            "audit_seal_version":"INTEGER",
        }
        for c,decl in additions.items():
            if c not in cols:
                self.conn.execute(f"ALTER TABLE strategy_runs ADD COLUMN {c} {decl}")

    def close(self): self.conn.close()
    def _run_exists(self,run_id):
        return self.conn.execute("SELECT 1 FROM strategy_runs WHERE run_id=?",(run_id,)).fetchone() is not None

    def audit(self,run_id,event_type,payload):
        if not self._run_exists(run_id): raise KeyError(f"unknown run_id {run_id}")
        head,count=self.conn.execute("SELECT audit_head_hash,audit_count FROM strategy_runs WHERE run_id=?",(run_id,)).fetchone()
        prev=head if count and head else GENESIS
        ts=utcnow(); pj=canonical(payload); rh=record_hash(run_id,event_type,ts,pj,prev)
        with self.conn:
            self.conn.execute("""INSERT INTO audit_events(run_id,event_type,created_at_utc,payload_json,prev_hash,record_hash)
                                 VALUES(?,?,?,?,?,?)""",(run_id,event_type,ts,pj,prev,rh))
            self.conn.execute("""UPDATE strategy_runs
                                 SET audit_head_hash=?,audit_count=?,audit_seal_hmac=NULL,audit_seal_version=NULL
                                 WHERE run_id=?""",(rh,int(count)+1,run_id))
        return rh

    def start_run(self,run_id,strategy_id,version,mode,metadata=None):
        m=metadata or {}
        with self.conn:
            self.conn.execute("""INSERT INTO strategy_runs
                (run_id,strategy_id,version,mode,status,started_at_utc,completed_at_utc,
                 metadata_json,audit_head_hash,audit_count,audit_seal_hmac,audit_seal_version)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id,strategy_id,version,mode,"RUNNING",utcnow(),None,canonical(m),"",0,None,None))
        self.audit(run_id,"RUN_STARTED",{"strategy_id":strategy_id,"version":version,"mode":mode,"metadata":m})

    def seal_run(self,run_id,signing_key=None):
        key=signing_key or os.getenv("FOVR_AUDIT_HMAC_KEY")
        if not key:
            raise ValueError("audit signing key unavailable")
        row=self.conn.execute("""SELECT status,completed_at_utc,audit_head_hash,audit_count
                                 FROM strategy_runs WHERE run_id=?""",(run_id,)).fetchone()
        if row is None: raise KeyError(f"unknown run_id {run_id}")
        status,completed,head,count=row
        if status=="RUNNING" or completed is None:
            raise ValueError("only completed runs may be sealed")
        version=1
        sig=_seal_hmac(_seal_message(run_id,status,completed,head,count,version),key)
        with self.conn:
            self.conn.execute("UPDATE strategy_runs SET audit_seal_hmac=?,audit_seal_version=? WHERE run_id=?",
                              (sig,version,run_id))
        return sig

    def complete_run(self,run_id,status="COMPLETED",signing_key=None):
        if not self._run_exists(run_id): raise KeyError(f"unknown run_id {run_id}")
        with self.conn:
            self.conn.execute("UPDATE strategy_runs SET status=?,completed_at_utc=? WHERE run_id=?",(status,utcnow(),run_id))
        self.audit(run_id,"RUN_COMPLETED",{"status":status})
        key=signing_key or os.getenv("FOVR_AUDIT_HMAC_KEY")
        if key:
            self.seal_run(run_id,key)

    def record_order(self,order_id,run_id,symbol,side,quantity,status,payload=None):
        if not self._run_exists(run_id): raise KeyError(f"unknown run_id {run_id}")
        with self.conn:
            self.conn.execute("""INSERT INTO orders(order_id,run_id,symbol,side,quantity,status,created_at_utc,payload_json)
                                 VALUES(?,?,?,?,?,?,?,?)""",
                              (order_id,run_id,symbol,side,float(quantity),status,utcnow(),canonical(payload or {})))
        self.audit(run_id,"ORDER_RECORDED",{"order_id":order_id,"symbol":symbol,"side":side,"quantity":float(quantity),"status":status})

    def upsert_position(self,run_id,symbol,quantity,market_value=None):
        if not self._run_exists(run_id): raise KeyError(f"unknown run_id {run_id}")
        with self.conn:
            self.conn.execute("""INSERT INTO positions(run_id,symbol,quantity,market_value,updated_at_utc)
                                 VALUES(?,?,?,?,?)
                                 ON CONFLICT(run_id,symbol) DO UPDATE SET
                                  quantity=excluded.quantity,market_value=excluded.market_value,
                                  updated_at_utc=excluded.updated_at_utc""",
                              (run_id,symbol,float(quantity),market_value,utcnow()))

    def get_run(self,run_id):
        r=self.conn.execute("""SELECT run_id,strategy_id,version,mode,status,started_at_utc,completed_at_utc,
                               metadata_json,audit_head_hash,audit_count,audit_seal_hmac,audit_seal_version
                               FROM strategy_runs WHERE run_id=?""",(run_id,)).fetchone()
        if not r: return None
        return {"run_id":r[0],"strategy_id":r[1],"version":r[2],"mode":r[3],"status":r[4],
                "started_at_utc":r[5],"completed_at_utc":r[6],"metadata":json.loads(r[7]),
                "audit_head_hash":r[8],"audit_count":r[9],"audit_seal_hmac":r[10],"audit_seal_version":r[11]}

    def list_audit(self,run_id):
        rows=self.conn.execute("""SELECT event_id,event_type,created_at_utc,payload_json,prev_hash,record_hash
                                  FROM audit_events WHERE run_id=? ORDER BY event_id""",(run_id,)).fetchall()
        return [{"event_id":r[0],"event_type":r[1],"created_at_utc":r[2],"payload":json.loads(r[3]),
                 "prev_hash":r[4],"record_hash":r[5]} for r in rows]

    def verify_audit_chain(self,run_id,signing_key=None,require_seal=False):
        run=self.conn.execute("""SELECT status,completed_at_utc,audit_head_hash,audit_count,
                                 audit_seal_hmac,audit_seal_version
                                 FROM strategy_runs WHERE run_id=?""",(run_id,)).fetchone()
        if run is None: return {"pass":False,"reason":"unknown_run"}
        status,completed,anchored_head,anchored_count,seal,seal_version=run
        rows=self.conn.execute("""SELECT event_id,event_type,created_at_utc,payload_json,prev_hash,record_hash
                                  FROM audit_events WHERE run_id=? ORDER BY event_id""",(run_id,)).fetchall()
        if not rows: return {"pass":False,"reason":"no_audit_events","records":0}
        if len(rows)!=int(anchored_count):
            return {"pass":False,"reason":"audit_count_mismatch","anchored_count":int(anchored_count),"actual_count":len(rows)}
        prev=GENESIS
        for i,(eid,etype,ts,pj,ph,rh) in enumerate(rows):
            if ph!=prev: return {"pass":False,"reason":"prev_hash_mismatch","event_id":eid}
            if record_hash(run_id,etype,ts,pj,ph)!=rh: return {"pass":False,"reason":"record_hash_mismatch","event_id":eid}
            prev=rh
        if rows[0][1]!="RUN_STARTED": return {"pass":False,"reason":"missing_run_started"}
        if anchored_head!=prev: return {"pass":False,"reason":"audit_head_mismatch"}
        last_event=rows[-1][1]
        if status=="RUNNING":
            if completed is not None or last_event=="RUN_COMPLETED":
                return {"pass":False,"reason":"run_state_audit_mismatch"}
        else:
            if completed is None or last_event!="RUN_COMPLETED":
                return {"pass":False,"reason":"missing_terminal_run_event"}
        key=signing_key or os.getenv("FOVR_AUDIT_HMAC_KEY")
        if require_seal and not seal:
            return {"pass":False,"reason":"audit_seal_required"}
        if seal:
            if not key: return {"pass":False,"reason":"audit_seal_key_unavailable"}
            version=int(seal_version or 1)
            expected=_seal_hmac(_seal_message(run_id,status,completed,anchored_head,anchored_count,version),key)
            if not hmac.compare_digest(seal,expected):
                return {"pass":False,"reason":"audit_seal_invalid"}
        return {"pass":True,"records":len(rows),"last_hash":prev,"anchored_count":int(anchored_count),"sealed":bool(seal)}
