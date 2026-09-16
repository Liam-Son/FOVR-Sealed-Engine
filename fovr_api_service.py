from __future__ import annotations
import asyncio
from fovr_state_store import FOVRStateStore
try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    FASTAPI_AVAILABLE=True
except Exception:
    FASTAPI_AVAILABLE=False

def health_payload():
    return {"service":"FOVR","version":"19","status":"ok",
            "components":["state_store","native_backtest","lean_challenger","gs_quant_validation","evidence_gate"]}

if FASTAPI_AVAILABLE:
    app=FastAPI(title="FOVR Institutional Service",version="19")
    class RunStart(BaseModel):
        run_id:str; strategy_id:str="FOVR"; version:str="19"; mode:str="research"; metadata:dict={}
    @app.get("/health")
    async def health(): return health_payload()
    @app.post("/runs/start")
    async def start_run(req:RunStart):
        def work():
            db=FOVRStateStore()
            try: db.start_run(req.run_id,req.strategy_id,req.version,req.mode,req.metadata)
            finally: db.close()
        await asyncio.to_thread(work); return {"ok":True,"run_id":req.run_id}
else:
    app=None
