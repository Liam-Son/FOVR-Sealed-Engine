# Security policy

- No broker, vendor or SEC credentials may be committed to source control.
- Production secrets must be injected through a secret manager or runtime environment.
- Production data must declare a commercial-use license class.
- Live execution requires dedicated account isolation and the existing FOVR live acknowledgements.
- Immutable/hash-chained track-record logs should be copied to write-once or independently retained storage.
- Any failed data, external-validation, reconciliation, freshness, cost, borrow or model-health gate blocks new live orders.
