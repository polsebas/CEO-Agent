# Runtime Invariants (non-negotiable)

These rules govern all production runtime changes. PRs that violate them are rejected.

- **ManualOrchestrator** is the only runtime authority.
- **Agno** never mutates state (world, runtime, side effects, approvals). It is an interchangeable cognition adapter.
- **All mutations** require policy evaluation. There is no `skip_policy` bypass.
- **All mutative requests** require `pg_try_advisory_xact_lock(hashtext(session_id))` inside a Postgres transaction (fail fast on contention).
- **Replay snapshots** are transactionally persisted in the same TX as decision/outbox/world updates.
- **Postgres** is the only source of truth in production (no dual-write to in-memory lists).
- **Runtime determinism** is measured through `CanonicalReplayOutcome` fingerprints via `canonical_json` / `stable_hash`.
- **Structured retries** are owned by the runtime (`StructuredRetryTrace`). Agno internal retries must be disabled or bounded.
- **Tool parameters and bindings** are hashed via `canonical_json` (stable key ordering, volatile fields stripped).

See also: [RRM1.md](./RRM1.md), `core/canonical.py`.
