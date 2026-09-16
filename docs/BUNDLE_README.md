# FOVR v7 — NautilusTrader + IBKR

This is the execution layer for the user's FOVR research signal.

See repository root README for the v23 sealed-engine map.

Safety modes: `dry` (no execution client), `paper` (IB paper), `live` (requires FOVR_LIVE_ACK=I_ACCEPT_REAL_MONEY_RISK). Shorting also requires FOVR_SHORT_ACK=ALLOW and --allow-shorts.

Pilot defaults (not a profitability claim): 20% gross, 5 long + 5 short, 3% name cap, 5% order cap, 25 bps limit pad, 100 bps spread gate, max 12 orders per rebalance.
