# CEO-Agent — Enterprise Cognitive Operating System

> **Idiomas:** Español · [English](README.en.md)

Plataforma multi-agente para operaciones ejecutivas con **runtime cognitivo gobernado**, diseñada como Vertical Slice enterprise-grade antes de escalar a la suite completa (CEO, CFO, COO, CTO, CMO).

El objetivo del proyecto no es solo “tener agentes”, sino **hacer cumplir el contrato arquitectónico**: governance no bypassable, replay determinístico, outbox transaccional, cognición real via Agno y validación gate endurecida.

---

## Qué resuelve

CEO-Agent coordina decisiones ejecutivas entre agentes especializados con:

- **Orquestación manual explícita** (`ManualOrchestrator`) como path primario desde el día 1
- **Runtime observable** con máquina de estados (`RuntimeStateMachine`)
- **Governance** con approvals inmutables, policy engine y RBAC
- **Persistencia transaccional** (decision + side effect + outbox en una TX)
- **Replay frozen/live** para auditoría y debugging
- **Capa determinística** (preprocessor 4-tier) antes de invocar LLM
- **Integración Agno real** con `output_schema` y `StructuredAgentRunner`

---

## Stack tecnológico

| Capa | Tecnología |
|------|------------|
| Runtime / API | Python 3.11+, FastAPI, Uvicorn |
| Agentes | Agno |
| Contratos | Pydantic v2 |
| Auth | JWT (`python-jose`) + RBAC |
| Persistencia | PostgreSQL (asyncpg) + fallback in-memory |
| Cache | Redis (con fallback in-memory) |
| Infra local | Docker Compose (Postgres + Redis) |

**Fuera de scope MVP:** Neo4j, Kafka, Agno Teams como orquestador primario, Temporal.

---

## Arquitectura

```text
Founder / API
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  Preprocessor 4-tier (regex → embedding → LLM fallback)     │
└───────────────────────────┬─────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
     Deterministic tools           ManualOrchestrator
     (router + policy)             (runtime + governance)
              │                           │
              │                           ├── RuntimeStateMachine
              │                           ├── PolicyEngine + Crisis
              │                           ├── ContextWindowManager L1-L5
              │                           ├── StructuredAgentRunner → Agno
              │                           └── Session locks (advisory)
              │                           │
              └─────────────┬─────────────┘
                            ▼
              ┌─────────────────────────────┐
              │  persist_execution_bundle   │
              │  decision + effect + outbox │
              └─────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
        Executive Timeline            Replay Engine
        (outbox + records)         (frozen / live)
```

### Principio de diseño

```text
contracts → deterministic layer → cognition
```

El orchestrator **coordina y gobierna**, pero **no reemplaza la cognición**. CEO/CTO ejecutan via Agno (`agent.arun`) con `output_schema` validado por `StructuredAgentRunner`.

---

## Estructura del proyecto

```text
CEO-Agent/
├── agents/              # Factory Agno + delegación expandida (CFO/COO/CMO)
├── api/
│   ├── auth.py          # JWT + RBAC
│   └── main.py          # Endpoints FastAPI
├── core/
│   ├── orchestrator.py  # ManualOrchestrator (path primario)
│   ├── runtime.py       # RuntimeStateMachine + transiciones
│   ├── agent_runner.py  # StructuredAgentRunner (Agno + retry)
│   ├── approval_service.py  # Workflow de approvals inmutable
│   ├── policy.py        # Policy engine + crisis mode
│   ├── persistence.py   # Outbox transaccional + Postgres
│   ├── replay.py        # Replay frozen/live
│   ├── session_lock.py  # Advisory locks cross-worker
│   ├── preprocessor.py  # Preprocessor 4-tier
│   ├── context.py       # ContextWindowManager L1-L5
│   ├── timeline.py      # Executive timeline
│   ├── health.py        # Agent health persistido
│   └── mcp_security.py  # Allowlist MCP / anti-SSRF
├── schemas/             # Contratos Pydantic (runtime, approvals, world, etc.)
├── tools/
│   ├── router.py        # Tool router + policy gate
│   ├── registry.py      # Capabilities por agente
│   ├── github/          # GitHub MCP + stub fallback
│   └── stubs/           # Stubs de negocio (CFO/COO/CMO)
├── prompts/             # Constituciones de agentes (.md)
├── workers/
│   └── outbox_processor.py
├── tests/
│   ├── unit/
│   └── vertical_slice/  # Gate tests + governance E2E
├── docker-compose.yml
├── main.py              # Entry point Uvicorn
└── pyproject.toml
```

### Documentación de referencia

| Documento | Contenido |
|-----------|-----------|
| `spec_mvp_ceo_agent_platform_v_1.md` | Spec MVP de la plataforma |
| `Guía de Arquitectura para Sistemas de Agentes Autónomos (Enterprise AI).md` | Patrones enterprise |
| `Guía de Entorno de Desarrollo para Sistemas de Agentes de IA (v1.0).md` | Convenciones de desarrollo |

---

## Agentes

| Agente | Estado | Rol |
|--------|--------|-----|
| **CEO** | Vertical Slice (activo) | Análisis ejecutivo, delegación, priorización |
| **CTO** | Vertical Slice (activo) | Incidentes, GitHub, salud de repos, deployment |
| **CFO** | Post-gate | Cashflow, runway |
| **COO** | Post-gate | Blockers, tareas operativas |
| **CMO** | Post-gate | Analytics, campañas |

Los agentes CFO/COO/CMO están implementados en `agents/expanded.py` y se activan después de pasar el gate de validación del Vertical Slice.

---

## Quick start

### 1. Infraestructura

```bash
cp .env.example .env
docker compose up -d
```

### 2. Dependencias

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### 3. Variables de entorno

Además de las variables en `.env.example`, el runtime hardened usa:

```bash
# Auth (obligatorio en producción)
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
AUTH_DISABLED=false          # true solo en dev/tests locales

# MCP security
ALLOWED_MCP_HOSTS=localhost,127.0.0.1,github-mcp.internal

# LLM (opcional — sin key usa fallback determinístico)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
GOOGLE_GEMINI_MODEL=gemini-3.5-flash
LLM_PROVIDER=auto                 # prioriza Google, luego Anthropic, luego OpenAI

# Persistencia
DATABASE_URL=postgresql://ceo:ceo@localhost:5432/ceo_agent
REDIS_URL=redis://localhost:6379/0
USE_IN_MEMORY_STORE=false    # true fuerza store en memoria (tests)

# GitHub MCP (opcional — cae a stub si no responde)
GITHUB_MCP_URL=http://localhost:8001
GITHUB_REPO=owner/repo
```

### 4. Levantar la API

```bash
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

---

## Autenticación y RBAC

Todos los endpoints mutativos requieren JWT Bearer salvo que `AUTH_DISABLED=true`.

### Roles

| Rol | Nivel | Uso típico |
|-----|-------|------------|
| `readonly` | 0 | Timeline, lectura |
| `operator` | 1 | Operaciones de bajo riesgo |
| `admin` | 2 | Replay, health de agentes |
| `founder` | 3 | Requests ejecutivos, prepare/approve |

### Matriz de permisos

| Endpoint | Auth | Rol mínimo |
|----------|------|------------|
| `GET /health` | No | — |
| `POST /api/v1/founder/request` | Sí | `founder` |
| `POST /api/v1/actions/prepare` | Sí | `founder` |
| `POST /api/v1/actions/approve/{id}` | Sí | `founder` |
| `GET /api/v1/approvals` | Sí | `readonly` |
| `GET /api/v1/timeline` | Sí | `readonly` |
| `GET /api/v1/replay/{session_id}` | Sí | `admin` |
| `GET /api/v1/agents/health` | Sí | `admin` |

### Generar token de prueba

```python
from api.auth import create_test_token, UserRole
token = create_test_token(user_id="founder-1", role=UserRole.FOUNDER)
# Header: Authorization: Bearer <token>
```

---

## API — Endpoints principales

### `POST /api/v1/founder/request`

Entrada del founder. El preprocessor decide si responde de forma determinística (tier 1/2) o dispara el flujo cognitivo completo.

```json
{
  "message": "Analyze deployment anomaly and incident status",
  "session_id": "optional-uuid",
  "correlation_id": "optional-uuid"
}
```

**Respuesta cognitiva:** incluye `session_id`, `correlation_id`, `runtime_state`, y `result` con análisis CEO + delegación CTO si aplica.

### `POST /api/v1/actions/prepare`

Crea un approval con **payload inmutable** (checksum + expiración).

```json
{
  "correlation_id": "corr-123",
  "action": "create_initiative",
  "parameters": {"name": "Q2 initiative"},
  "agent": "ceo",
  "side_effect_level": "EXECUTE_SAFE",
  "impact_summary": "Create initiative",
  "approval_level": 2
}
```

### `POST /api/v1/actions/approve/{approval_id}`

Aprueba y ejecuta el payload congelado. Re-valida policy, checksum y expiración. **No permite `skip_policy`.**

### `GET /api/v1/timeline?correlation_id=`

Timeline ejecutivo derivado exclusivamente de `OutboxEvent` + `DecisionRecord` + `SideEffectRecord`.

### `GET /api/v1/replay/{session_id}?correlation_id=&mode=frozen|live`

- **frozen:** solo snapshots históricos (sin tools reales ni world state actual)
- **live:** re-ejecución contra estado reciente

### `GET /api/v1/agents/health`

Métricas de salud por agente (success rate, degraded mode, latencia).

---

## Flujo de governance (approvals)

```text
PREPARE
  ↓
Persist ImmutableActionProposal (checksum + expires_at)
  ↓
Policy evaluation inicial
  ↓
APPROVE (founder)
  ↓
Re-validación policy + checksum + expiración
  ↓
Execute frozen payload (sin skip_policy)
  ↓
Persist SideEffectRecord + OutboxEvent (TX atómica)
```

Campos clave de `ImmutableActionProposal`:

- `id`, `correlation_id`, `action`, `parameters`
- `proposed_by`, `approval_level`
- `checksum` (SHA-256 del payload)
- `expires_at`

---

## Runtime — Estados y transiciones

Estados principales: `idle → perceiving → reasoning → waiting_tool → observing → completed`

También: `waiting_approval`, `executing`, `replanning`, `escalated`, `failed`

Transiciones explícitas en `schemas/runtime.py` (`VALID_TRANSITIONS`). Ejemplo relevante post-hardening:

```text
PERCEIVING → ESCALATED   (degraded mode / escalación temprana)
```

### Crisis mode

El `PolicyEngine` detecta crisis (infraestructura, financiera, etc.) y aplica overrides:

- Delta de approval level
- Routing priority
- **Context expansion** (capas L3/L4 extra via `ContextWindowManager`)

### Session isolation

Locks via `pg_advisory_xact_lock(hashtext(session_id))` en Postgres, con fallback in-process para dev/tests.

---

## Cognición — Agno + StructuredRetry

```text
StructuredAgentRunner.run()
  ↓
agent.arun(prompt, output_schema=CEOResponse|CTOResponse)
  ↓
parse_structured_response()  (repair + retry cap)
  ↓
fallback determinístico si no hay modelo LLM
```

- Sin API key de LLM: el runtime sigue funcionando con respuestas estructuradas determinísticas
- Con API key: cognición real via Agno
- Retry global capado en `schemas/responses/base.py` (`MAX_STRUCTURED_RETRIES_GLOBAL`)

---

## Persistencia

### Transactional Outbox

`persist_execution_bundle()` escribe en **una sola transacción**:

1. `DecisionRecord` (opcional)
2. `SideEffectRecord` (opcional)
3. `OutboxEvent`

### Tablas Postgres (auto-creadas)

- `outbox_events`
- `decision_records`
- `side_effect_records`
- `world_state_snapshots`
- `replay_snapshots`
- `agent_health`

### Outbox worker

```bash
.venv/bin/python -c "
import asyncio
from workers.outbox_processor import run_outbox_worker
asyncio.run(run_outbox_worker())
"
```

---

## Tools y MCP

El router (`tools/router.py`) normaliza todas las invocaciones a `ToolResult` y aplica:

- Permisos por agente (`tools/registry.py`)
- Policy gate por `side_effect_level`
- Cache Redis para tools read-only
- Timeout MCP 3s con stub fallback

### GitHub MCP

`tools/github/client.py` intenta MCP real y cae a stub. URLs validadas contra allowlist (`core/mcp_security.py`) para prevenir SSRF.

---

## Tests

```bash
.venv/bin/pytest tests/ -v
```

| Suite | Qué valida |
|-------|------------|
| `tests/unit/` | Runtime, context, preprocessor, structured retry |
| `tests/vertical_slice/test_gate.py` | Gate VS: orchestration, replay, timeline, approvals, concurrency |
| `tests/vertical_slice/test_governance_hardening.py` | Auth 401, RBAC 403, expiry, checksum tamper, transiciones |

Tests usan `USE_IN_MEMORY_STORE=true` y `AUTH_DISABLED=true` via `conftest.py`.

**Estado actual:** 30 tests passing.

---

## Criterios de aprobación del Vertical Slice

El VS se considera production-grade cuando:

| Área | Criterio |
|------|----------|
| **Runtime** | 0 `InvalidStateTransition` bajo carga; 0 session leakage multi-worker |
| **Replay** | 100% determinístico en modo frozen |
| **Governance** | 0 bypasses de approval; endpoints autenticados; payloads inmutables |
| **Persistencia** | 0 dual-write; 100% atomicidad outbox |
| **Cognición** | Agno ejecutado; StructuredRetry end-to-end; `output_schema` enforced |

---

## Roadmap (post-hardening)

| Prioridad | Item |
|-----------|------|
| Done (RRM-2) | OpenTelemetry traces (OTLP) + métricas Prometheus en `/metrics` |
| Should Have | Replay diff visualization |
| Should Have | Approval cryptographic signing |
| Should Have | Tests multi-worker reales (Postgres + procesos) |
| Could Have | Temporal integration |
| Could Have | Kafka migration |
| Could Have | Agno Team comparison benchmark |

---

## Desarrollo

### Convenciones

- Contratos Pydantic en `schemas/` — no duplicar tipos en runtime
- Side effects siempre via router + policy
- Timeline y replay nunca desde memoria de runtime
- Orchestrator coordina; Agno piensa

### Lint / typecheck

El proyecto usa `pytest` como gate principal. Correr tests antes de cada PR:

```bash
.venv/bin/pytest tests/ -q --cache-clear
```

---

## Licencia

Proyecto privado / en desarrollo. Consultar repositorio para términos aplicables.
