# Changelog

## 23.1.1 — 2026-09-16

Tested the sealed suite. 4 adversarial cases were still green when they should fail closed.

- Default `strict_consistency=True` on LEAN result contracts.
- Summary must match recomputed cumulative return and turnover.
- Manifest hashes include a per-run nonce (identical bytes cannot replay).
- Full DB reseal test now signs with an external HMAC key.

Result: **63/63 PASS** locally.
