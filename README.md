# FOVR-Sealed-Engine

Public snapshot of **FOVR v23 Externally Sealed**.

FOVR = **Factor / Options / Value Research**: a US-equity market-neutral research-to-execution stack that combines

1. point-in-time balance-sheet trajectory,
2. reconstructed 90-day put/call IV skew,
3. liquid range reversal,

then residualizes factors, applies cost/borrow/liquidity gates, and can hand targets to NautilusTrader + IBKR.

This repository contains **every file from the v23 externally sealed bundle**: engines, HMAC/audit seals, LEAN challenger gate, production controls, tests, model card, risk register, and free-data reality notes.

## Not a live-profit claim

`VALIDATION_V23.json` reports **41/41** sealed-bundle regression tests. That is software integrity, not a track record. Free option history is short. Live trading stays blocked unless `FOVR_LIVE_ACK=I_ACCEPT_REAL_MONEY_RISK`.

## Layout

| Path | Role |
|------|------|
| `fovr_state_store.py` | SQLite audit chain, HMAC external seal |
| `fovr_dual_engine_gate.py` | Native vs LEAN agreement gate |
| `fovr_lean_challenger.py` | LEAN-side challenger |
| `fovr_production_controls.py` | Live/paper/dry gates |
| `fovr_api_service.py` | API surface |
| `fovr_portfolio_benchmarks.py` | Portfolio benchmarks |
| `fovr_quantrocket_free_adapter.py` | Free QuantRocket survivorship slice |
| `test_v19_*.py` … `test_v23_*.py` | Adversarial + seal tests |
| `MODEL_CARD.md` | Model card |
| `FREE_ONLY_REALITY.md` | What free data cannot fake |
| `VALIDATION_V23.json` | Sealed test ledger |

## License / secrets

See `OPEN_SOURCE_NOTICE.md` and `SECURITY.md`. Do not commit broker keys. HMAC keys belong in a secret manager, not SQLite.

Bundle date: 2026-09-15.
The original sealed README is `docs/BUNDLE_README.md`.
