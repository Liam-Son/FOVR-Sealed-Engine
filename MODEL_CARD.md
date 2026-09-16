# FOVR Model Card — v11 / v23 sealed

## Purpose
US-equity market-neutral systematic strategy combining:
1. point-in-time balance-sheet improvement;
2. 90-day put/call implied-volatility skew;
3. liquid intraday range reversal.

## Primary use
Research, paper trading, and controlled live pilot through NautilusTrader + IBKR.

## Decision frequency
Daily, after end-of-day data is available.

## Known model risks
- IV reconstruction differs from proprietary vendor fields.
- free option history is materially shorter than licensed backtest history.
- point-in-time fundamentals require filing/effective-date discipline.
- short availability and borrow rates are non-stationary.
- execution cost can dominate at small capital.

## Required validation before production promotion
- independent point-in-time replication
- no leakage flags
- walk-forward stability
- bootstrap confidence interval
