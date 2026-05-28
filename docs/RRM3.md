# SPEC-RRM3 — Adaptive Cognition Runtime

## Estado

| Campo | Valor |
|-------|-------|
| ID | `SPEC-RRM3` |
| Prerequisito | RRM-2 + RRM-2.1 |
| **Estado** | **IMPLEMENTADO** (C2 diferido) |
| C2 opcional | Diferido (summarization avanzada, decay multi-layer) |

## Invariante §1

```text
same AdaptiveSignals → same AdaptivePolicy
```

Verificado en `tests/gate/test_rrm3_adaptive_policy.py`.

## Principio

```text
Cognition becomes adaptive, orchestration remains authoritative.
```

- `AdaptivePolicyEngine` deriva política (sin LLM/embeddings).
- `ManualOrchestrator` ejecuta budget, delegación, retries.
- Recompute de policy solo en **boundaries** (inicio sesión, post-retry cluster, `session.completed` con `force=True`, anomalía).
- `approval_escalation_bias` se aplica vía `core/adaptive_context` en `policy_engine.evaluate()`.

## Milestones

| Milestone | Artefacto |
|-----------|-----------|
| RRM3-A | `core/adaptive_policy.py`, gates adaptive policy |
| RRM3-B | `core/tool_reliability.py`, hysteresis ENTER=0.70 EXIT=0.82 |
| RRM3-C1 | `core/context_priority.py`, bounded growth |
| RRM3-D | `core/session_stability.py`, retry storms |
| RRM3-E | `core/adaptive_governance.py`, solo escalación governance |

## Tool hysteresis

```python
ENTER_DEGRADED_THRESHOLD = 0.70
EXIT_DEGRADED_THRESHOLD = 0.82
```

## Governance (RRM3-E)

- Permitido: endurecer approvals (`approval_escalation_bias >= 0`).
- Prohibido: relajar approvals automáticamente por replay estable.

## APIs

| Endpoint | Permiso |
|----------|---------|
| `GET /api/v1/sessions/{id}/adaptive-policy` | `DIAGNOSTICS_READ` |
| `GET /api/v1/tools/reliability` | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/stability` | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/context-intelligence` | `DIAGNOSTICS_READ` |
| `GET /api/v1/replay/{id}/governance` | `DIAGNOSTICS_READ` |

## Gates

```bash
OTEL_SDK_DISABLED=true .venv/bin/python -m pytest tests/gate/test_rrm3_*.py -q
```

## Post-RRM-3

RRM-4 = Operational Scale (queues, workers, tenancy).
