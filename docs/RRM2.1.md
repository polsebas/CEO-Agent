# SPEC-RRM2.1 — Intelligence Reliability Hardening

## Estado

| Campo | Valor |
|-------|-------|
| ID | `SPEC-RRM2.1` |
| Prerequisito | RRM-2 cerrado |
| **Estado** | **CERRADO** |
| Gate CI | `tests/gate/test_rrm21_*.py` |

## Objetivo

Corregir inconsistencias entre contrato observacional, semántica transaccional e instrumentación (OTel / spans / diagnostics) sin alterar el runtime determinista de RRM-1 / RRM-1.5.

## Fixes (P0 / P1)

| # | Fix | Artefacto |
|---|-----|-----------|
| 1 | Spans drenados también en outbox idempotente (Postgres + memory) | `core/transaction.py` |
| 2 | `ContextVar(default=None)` — sin listas/dicts compartidos por defecto | `core/spans.py` |
| 3 | Baseline-first: `replay_confidence` derivado post-baseline en `_complete_session_close` | `core/transaction.py`, `core/replay_validator.py` |
| 4 | Métricas OTel → `PrometheusMetricReader` + `collect()` en `/metrics` | `core/telemetry/otel.py`, `opentelemetry-exporter-prometheus` |
| 5 | Un solo persist de intelligence en `session.completed` | `core/transaction.py` |
| 6 | Health snapshot único por `(session_id, correlation_id)` | `core/intelligence_persist.py`, `replace_health` |
| 7 | `end_otel_span` al cerrar spans | `core/spans.py` |
| 8 | Spans `APPROVAL` en prepare/execute | `core/approval_service.py` |
| 9 | Degraded: `session.completed` + diagnostics + baseline | `core/orchestrator.py` `_escalate_degraded` |

## Gates

```bash
OTEL_SDK_DISABLED=true .venv/bin/python -m pytest tests/gate/test_rrm21_*.py tests/gate/test_rrm2_*.py -q
```

Tests con bridge Prometheus (`test_prometheus_bridge_*`) y `test_metrics_endpoint` habilitan OTel localmente vía `monkeypatch`.

## Criterio de cierre

Toda decisión, retry, replay, health y degradación deben ser **causalmente reconstruibles** vía spans + outbox + diagnostics, incluso bajo reintentos idempotentes y sesiones concurrentes.
