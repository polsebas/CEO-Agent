# SPEC-RRM2 — Runtime Intelligence Layer

## Estado

| Campo | Valor |
|-------|-------|
| ID | `SPEC-RRM2` |
| Prerequisito | RRM-1 + RRM-1.5 |
| **Estado** | **CERRADO** |
| Seguimiento | [RRM2.1](RRM2.1.md) — reliability hardening (cerrado) |
| Gate CI | `tests/gate/test_rrm2_*.py`, `tests/gate/test_rrm21_*.py`, `tests/integration/test_postgres_spans.py`, `tests/integration/test_postgres_diagnostics.py` |

## Milestones

| Milestone | Estado | Artefacto |
|-----------|--------|-----------|
| Foundation | ✅ | schema, `PersistRuntimePayload`, `core/telemetry/otel.py`, in-memory parity |
| RRM2A Observability | ✅ | `schemas/spans.py`, `core/spans.py` |
| RRM2B Cognitive telemetry | ✅ | `CognitiveTelemetry`, `PromptLineage`, `core/cognition_metrics.py` |
| RRM2C Runtime health | ✅ | `core/runtime_health.py`, degraded mode hooks |
| RRM2D Context lifecycle | ✅ | `core/context_lifecycle.py`, ContextFingerprint v2 |
| RRM2E Diagnostics | ✅ | `core/diagnostics.py`, `api/diagnostics.py`, `/metrics` |

## Principio

La Runtime Intelligence Layer observa y diagnostica; **no** reemplaza `ManualOrchestrator` ni altera semántica transaccional/replay.

## APIs

| Endpoint | Permiso |
|----------|---------|
| `GET /api/v1/sessions/{id}/health` | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/spans` | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/telemetry` | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/context` | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/diagnostics` | `DIAGNOSTICS_READ` |
| `GET /api/v1/replay/{id}/analysis` | `DIAGNOSTICS_READ` |
| `GET /metrics` | público (Prometheus text) |

## OpenTelemetry y Prometheus

Contrato de runtime:

| Señal | Export | Config |
|-------|--------|--------|
| Métricas cognitivas / health | Scrape `GET /metrics` (texto Prometheus) | `TELEMETRY_ENABLED`, `OTEL_SDK_DISABLED` |
| Traces | OTLP HTTP (opcional) | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Métricas vía OTLP | **No soportado** | — |

```env
TELEMETRY_ENABLED=true
OTEL_SDK_DISABLED=false
OTEL_SERVICE_NAME=ceo-agent
OTEL_EXPORTER_OTLP_ENDPOINT=
```

- `TELEMETRY_ENABLED=false` o `OTEL_SDK_DISABLED=true`: el SDK no inicializa meter/tracer; `/metrics` puede responder vacío o solo defaults de `prometheus_client`.
- En pytest/CI: `OTEL_SDK_DISABLED=true` (salvo tests que habilitan OTel vía `monkeypatch`).

## Gates

```bash
OTEL_SDK_DISABLED=true .venv/bin/python -m pytest tests/gate/test_rrm2_*.py -q

DATABASE_URL=postgresql://ceo:ceo@localhost:5432/ceo_agent USE_IN_MEMORY_STORE=false \
  OTEL_SDK_DISABLED=true .venv/bin/python -m pytest tests/integration/test_postgres_spans.py tests/integration/test_postgres_diagnostics.py -q
```
