# SPEC-RRM1.5 — Replay Integrity

## Estado

| Campo | Valor |
|-------|-------|
| ID | `SPEC-RRM1.5` |
| Nombre | RRM-1.5 — Replay Integrity |
| Prerequisito | RRM-1 + RRM1-REMEDIATION |
| **Estado** | **CERRADO** |
| Desbloquea | RRM-2 |
| Gate CI | `tests/gate/test_rrm15_replay_integrity.py`, `tests/gate/test_outbox_semantics.py`, job `postgres-integration` |

## Resumen de entregables

| Milestone | Estado | Artefacto |
|-----------|--------|-----------|
| M1 FrozenReplayExecutor | ✅ | `core/frozen_replay_executor.py` |
| M2 LiveToolReplayAdapter | ✅ | `core/live_replay_adapter.py` |
| M3 RuntimeState canonicalization | ✅ | SM + transiciones en executor |
| M4 Postgres integration gate | ✅ | `tests/integration/test_postgres_replay.py` |
| M5 Outbox semantics | ✅ | `tests/gate/test_outbox_semantics.py`, `tests/integration/test_postgres_outbox.py` |
| M6 prompt_hash completo | ✅ | `core/replay_validator.py` |

---

## Problema (resuelto)

El replay validaba snapshots, no ejecución. RRM-1.5 introdujo:

- **Frozen:** `FrozenReplayExecutor` reproduce transiciones SM + tool outputs congelados + routing CEO/CTO.
- **Live:** `LiveToolReplayAdapter` re-ejecuta tools en bundle copiado (sin mutar persistencia).
- **Baseline:** fingerprint + `orchestrator_version` en `replay_baselines`.

---

## Arquitectura

```mermaid
flowchart TB
    MO[ManualOrchestrator] --> PRT[persist_runtime_tx]
    PRT --> SB[(replay_snapshots + runtime_transitions)]
    PRT --> BL[(replay_baselines)]

    FRE[FrozenReplayExecutor] --> SB
    FRE --> BL

    LTA[LiveToolReplayAdapter] --> execute_tool
    LTA --> FRE
```

---

## Criterios de aceptación — Definition of Done

### Global

- [x] **AC-G1:** `pytest tests/gate/test_rrm15_replay_integrity.py tests/gate/test_outbox_semantics.py -q` — 0 failed, 0 skip pendientes de milestone
- [x] **AC-G2:** Sin `live_tool_mutator` ni mutación in-place de snapshots
- [x] **AC-G3:** `runtime_invariants.md` actualizado
- [x] **AC-G4:** `RRM1.md` — RRM-1.5 cerrado, RRM-2 desbloqueado
- [x] **AC-G5:** CI `postgres-integration` incluye replay + outbox Postgres

### Por milestone

| ID | Criterio | Gate |
|----|----------|------|
| AC-M1 | FrozenReplayExecutor único camino FROZEN | `test_frozen_executor_*`, `test_orchestrator_logic_change_breaks_frozen_replay` |
| AC-M2 | Live sin mutator | `test_live_replay_detects_*`, `test_replay_drift.py` |
| AC-M3 | `final_runtime_state` desde SM | `test_final_runtime_state_from_state_machine` |
| AC-M4 | Baseline + frozen en Postgres | `test_postgres_frozen_*`, `test_postgres_live_*` |
| AC-M5 | Outbox SKIP LOCKED + handler failure | `test_outbox_*`, `test_postgres_outbox_two_workers_*` |
| AC-M6 | `prompt_hash` 64 hex | `test_prompt_hash_is_full_sha256` |
| AC-M7 | Founder/approvals/experimental → `run_mutative_session` | auditoría en gate |

---

## Ejecutar gates

```bash
# Unit + gate (sin Postgres)
.venv/bin/python -m pytest tests/gate/test_rrm15_replay_integrity.py tests/gate/test_outbox_semantics.py tests/gate/test_replay_drift.py -q

# Postgres (local o CI)
DATABASE_URL=postgresql://ceo:ceo@localhost:5432/ceo_agent USE_IN_MEMORY_STORE=false \
  .venv/bin/python -m pytest tests/integration/test_postgres_replay.py tests/integration/test_postgres_outbox.py -q
```

---

## Referencias

- [RRM1.md](./RRM1.md)
- [runtime_invariants.md](./runtime_invariants.md)
