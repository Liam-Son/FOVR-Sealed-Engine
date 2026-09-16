# FOVR-Sealed-Engine

Public **v23.1** snapshot of FOVR (Factor / Options / Value Research).

Three lagged sleeves, then dollar-neutral mapping:

1. point-in-time balance-sheet trajectory  
2. reconstructed 90-day put/call IV skew  
3. range reversal  

Plus a hash-chained SQLite audit store, native-vs-LEAN dual-engine gate, HMAC seals, and fail-closed production env checks.

## Not a live-profit claim

Sealed-bundle software tests passing ≠ a track record. Free option history is short. Live orders stay blocked without `FOVR_LIVE_ACK=I_ACCEPT_REAL_MONEY_RISK` and commercial data license + HMAC keys.

## Run

```bash
pip install -r requirements.txt
python -m pytest test_v23_external_seal.py test_v23_1_engine.py -q
```

## Core modules

| File | Role |
|------|------|
| `fovr_sleeves.py` | Lagged sleeve definitions + dollar-neutral weights |
| `fovr_state_store.py` | Run/order/position audit chain + external HMAC seal |
| `fovr_dual_engine_gate.py` | Native vs LEAN agreement |
| `fovr_lean_challenger.py` | Frozen-input LEAN runner |
| `fovr_production_controls.py` | Prod env / license / key gates |
| `fovr_portfolio_benchmarks.py` | EW / inv-vol / min-var |

See `MODEL_CARD.md`, `FREE_ONLY_REALITY.md`, `VALIDATION_V23.json`, `BUNDLE_SHA256.txt`.
