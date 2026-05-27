# RRM-1 — Runtime Reliability Milestone

## Runtime authority

- **ManualOrchestrator** is the sole runtime authority.
- **Agno** is an interchangeable cognition adapter — not part of the runtime core.

## RBAC (production)

| Role | Purpose |
|------|---------|
| `founder` | Maximum authority, L0–L4 approvals, crisis |
| `admin` | Operations, replay, L0–L2 approvals |
| `operator` | Prepare actions, founder requests, replay read |
| `readonly` | Timeline, approvals read-only |

JWT includes `scopes` aligned with `core/permissions.py`.

## Active agents

Only **CEO** and **CTO** are `ACTIVE` in `core/agent_registry.py`.  
CFO/COO/CMO live under `experimental/` and hard-fail if invoked.

## Determinism

Replay success is measured via `CanonicalReplayOutcome` + `core/canonical.py` — not raw serialized outputs.

## Invariants

See [runtime_invariants.md](./runtime_invariants.md).

## RRM1-REMEDIATION (Postgres-first)

| Milestone | Estado |
|-----------|--------|
| RRM1-R1 | Un solo `mutative_session` + `pg_try_advisory_xact_lock` en la misma conexión |
| RRM1-R2 | Approvals + audit en Postgres (`governance_store`) |
| RRM1-R3 | Frozen replay re-orquesta y compara baseline persistido |
| RRM1-R4 | Outbox: `SKIP LOCKED`, processed solo tras handler OK |
| RRM1-R5 | Founder determinístico vía `ManualOrchestrator` |
| RRM1-R6 | `structured_retry_traces` con `UNIQUE (correlation_id, session_id, agent_id, step_id)` |
| RRM1-R7 | Producción: Postgres SoT; in-memory solo con `use_in_memory_store` |
| RRM1-R8 | Gate en `tests/gate/`, contención en `tests/integration/` |

## RRM-1.5 — Replay Integrity ✅ CERRADO

Execution replay (frozen + live), baseline versionado, gates Postgres y outbox.

- Spec: [RRM1.5.md](./RRM1.5.md)
- Gates: `tests/gate/test_rrm15_replay_integrity.py`, `tests/gate/test_outbox_semantics.py`
- Postgres: `tests/integration/test_postgres_replay.py`, `tests/integration/test_postgres_outbox.py`

## RRM-2 (desbloqueado)

Embeddings sophistication, semantic cache tuning, advanced prompts, multi-agent delegation, timeline UI, OpenTelemetry.
