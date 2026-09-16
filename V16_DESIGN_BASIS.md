# v16 External Evidence / Design Basis

- SEC Companyfacts API: filing/effective dates; never backfill future filings into prior signals.
- CRSP-class inactive securities and delisting returns are the production-grade survivorship standard.
- Cboe Option EOD Summary is the licensed options class production adapters should target.
- FINRA short-sale volume is not short interest or borrow availability.
- NautilusTrader ExecutionAlgorithm / TWAP plus FOVR POV policy.
