# CEO-Agent — Enterprise Cognitive Operating System

> **Idiomas:** Español · [English](README.en.md)

Plataforma multi-agente para operaciones ejecutivas con **runtime cognitivo gobernado**, diseñada como Vertical Slice enterprise-grade antes de escalar a la suite completa (CEO, CFO, COO, CTO, CMO).

El objetivo del proyecto no es solo “tener agentes”, sino **hacer cumplir el contrato arquitectónico**: governance no bypassable, replay determinístico, outbox transaccional, cognición real via Agno, validación gate endurecida y **consola operacional** para operar sesiones sin leer logs raw.

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
| Consola operacional (MVP-1) | Jinja2 SSR, HTMX, Tailwind CSS |
| Agentes | Agno |
| Contratos | Pydantic v2 |
| Auth | JWT (`python-jose`) + RBAC |
| Observabilidad | OpenTelemetry + Prometheus (`/metrics`) |
| Persistencia | PostgreSQL (asyncpg) + fallback in-memory |
| Cache | Redis (con fallback in-memory) |
| Infra local | Docker Compose (Postgres + Redis) |

**Fuera de scope MVP:** Neo4j, Kafka, Agno Teams como orquestador primario, Temporal.

---

## Arquitectura

```text
Founder / API / Consola Ops (HTMX)
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
              │                           ├── Adaptive cognition (RRM-3)
              │                           ├── ContextWindowManager L1-L5
              │                           ├── StructuredAgentRunner → Agno
              │                           └── Session locks (advisory)
              │                           │
              └─────────────┬─────────────┘
                            ▼
              ┌─────────────────────────────┐
              │  persist_runtime_tx         │
              │  decision + effect + outbox │
              └─────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
        Executive Timeline            Replay Engine
        Session diagnostics         (frozen / live)
        (UIQueryFacade → UI)
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
│   ├── main.py          # Endpoints FastAPI + mount UI
│   ├── diagnostics.py # RRM-2 diagnostics API
│   ├── adaptive.py      # RRM-3 adaptive cognition API
│   └── sessions.py      # Listado de sesiones (MVP-1)
├── ui/                  # Consola operacional SSR (MVP-1)
│   ├── routes/          # Dashboard, sessions, replay, approvals…
│   ├── templates/       # Jinja2 + partials HTMX
│   ├── static/          # CSS, HTMX
│   └── services/        # UIQueryFacade, human_labels
├── core/
│   ├── orchestrator.py  # ManualOrchestrator (path primario)
│   ├── diagnostics.py # DiagnosticsService (lectura)
│   ├── session_summary_builder.py  # Narrativas humanas para UI
│   ├── session_list.py  # Índice de sesiones
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
├── demo/                # Fixtures determinísticas para demos MVP-1
├── scripts/
│   ├── seed_demo.py     # Seed de sesiones demo
│   └── ci-local.sh
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
│   ├── gate/            # RRM milestones
│   ├── ui/              # Tests consola MVP-1
│   └── vertical_slice/  # Gate tests + governance E2E
├── docs/
│   ├── RRM2.md
│   ├── RRM3.md
│   └── MVP1_DEMO.md     # Guión demo operacional
├── docker-compose.yml
├── main.py              # Entry point Uvicorn
├── package.json         # Tailwind CLI (UI)
└── pyproject.toml
```

### Documentación de referencia

| Documento | Contenido |
|-----------|-----------|
| `docs/MVP1_DEMO.md` | Guión demo consola operacional (&lt;10 min) |
| `docs/RRM2.md` | Runtime Intelligence — diagnostics, spans, telemetry |
| `docs/RRM3.md` | Adaptive cognition — policy, stability, governance |
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

### 5. Consola operacional (MVP-1)

```bash
# Seed de sesiones demo (opcional)
.venv/bin/python scripts/seed_demo.py

# Levantar API (misma instancia sirve JSON + UI)
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abrir **http://localhost:8000/login** y elegir rol:

| Rol | Uso en demo |
|-----|-------------|
| `operator` | Ejecutar founder requests, ver sesiones/replay |
| `reviewer` | Aprobar acciones pendientes |
| `readonly` | Observar dashboard y diagnostics |

Guión completo: [`docs/MVP1_DEMO.md`](docs/MVP1_DEMO.md).

**Pantallas principales:**

| Ruta | Descripción |
|------|-------------|
| `/` | Dashboard — sesiones recientes, degradadas, approvals |
| `/sessions` | Listado con búsqueda y filtros |
| `/sessions/{id}?correlation_id=` | Detalle + timeline unificada (HTMX refresh 5s) |
| `/sessions/{id}/replay` | Replay inspector (frozen/live) |
| `/sessions/{id}/diagnostics` | Diagnostics + human summaries |
| `/sessions/{id}/adaptive` | Adaptive policy y stability |
| `/approvals` | Cola de aprobaciones |
| `/sessions/new` | Founder request (operator) |

**CSS (opcional):** rebuild Tailwind con `npm install && npm run build:css`.

La UI **no llama HTTP a `/api/v1` internamente** — lee via `UIQueryFacade` → servicios core (`DiagnosticsService`, `policy_engine`, etc.).

---

## Autenticación y RBAC

Endpoints JSON requieren JWT Bearer. La consola UI acepta cookie `ceo_token` (login en `/login`) o el mismo header Bearer.

Salvo que `AUTH_DISABLED=true` (solo dev/tests).

### Roles (MVP-1)

| Rol | Nivel | Ejecutar / preparar | Aprobar | Observar |
|-----|-------|---------------------|---------|----------|
| `readonly` | 0 | — | — | sessions, diagnostics, timeline, approvals (lectura) |
| `operator` | 1 | founder request, prepare, replay execute | — | sessions, diagnostics |
| `reviewer` | 2 | — | approve | sessions, diagnostics, approvals |
| `admin` | 3 | full operativo | approve (nivel 2+) | + agents health |
| `founder` | 4 | todos los permisos | todos | todos |

Separación **operator / reviewer** para demos human-in-the-loop: el operador ejecuta; el revisor aprueba.

### Matriz de permisos (API)

| Endpoint | Auth | Permiso / rol |
|----------|------|---------------|
| `GET /health`, `GET /metrics` | No | — |
| `GET /api/v1/sessions` | Sí | `SESSION_READ` |
| `POST /api/v1/founder/request` | Sí | `FOUNDER_REQUEST` (operator+) |
| `POST /api/v1/actions/prepare` | Sí | `ACTION_PREPARE` (operator+) |
| `POST /api/v1/actions/approve/{id}` | Sí | `ACTION_APPROVE` (reviewer+) |
| `GET /api/v1/approvals` | Sí | `APPROVALS_READ` |
| `GET /api/v1/timeline` | Sí | `TIMELINE_READ` |
| `GET /api/v1/replay/{session_id}` | Sí | `REPLAY_EXECUTE` (operator+) |
| `GET /api/v1/sessions/{id}/diagnostics` | Sí | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/health` | Sí | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/spans` | Sí | `DIAGNOSTICS_READ` |
| `GET /api/v1/replay/{id}/analysis` | Sí | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/adaptive-policy` | Sí | `DIAGNOSTICS_READ` |
| `GET /api/v1/replay/{id}/governance` | Sí | `DIAGNOSTICS_READ` |
| `GET /api/v1/agents/health` | Sí | `AGENTS_HEALTH` (admin+) |

Rutas HTML (`/`, `/sessions`, `/approvals`, …) usan los mismos permisos vía `UIQueryFacade`.

### Generar token de prueba

```python
from api.auth import create_test_token
from core.roles import UserRole

token = create_test_token(user_id="operator-1", role=UserRole.OPERATOR)
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

### `GET /api/v1/sessions`

Listado operacional de sesiones (desde `session_diagnostics`).

Query params: `limit`, `offset`, `status`, `health`, `has_pending_approvals`, `search`, `degraded_only`.

### `GET /api/v1/timeline?correlation_id=`

Timeline ejecutivo derivado exclusivamente de `OutboxEvent` + `DecisionRecord` + `SideEffectRecord`.

### `GET /api/v1/replay/{session_id}?correlation_id=&mode=frozen|live`

- **frozen:** solo snapshots históricos (sin tools reales ni world state actual)
- **live:** re-ejecución contra estado reciente

### `GET /api/v1/agents/health`

Métricas de salud por agente (success rate, degraded mode, latencia).

### Diagnostics & adaptive (RRM-2 / RRM-3)

| Endpoint | Descripción |
|----------|-------------|
| `GET /api/v1/sessions/{id}/diagnostics?correlation_id=` | Snapshot unificado `SessionDiagnostics` |
| `GET /api/v1/sessions/{id}/health` | `RuntimeHealth` |
| `GET /api/v1/sessions/{id}/spans` | Árbol de execution spans |
| `GET /api/v1/sessions/{id}/telemetry` | Cognitive telemetry |
| `GET /api/v1/replay/{id}/analysis?correlation_id=` | `ReplayAnalytics` (drift, confidence) |
| `GET /api/v1/sessions/{id}/adaptive-policy` | Adaptive policy snapshot |
| `GET /api/v1/sessions/{id}/stability` | Session stability events |
| `GET /api/v1/replay/{id}/governance` | Governance + replay analytics |
| `GET /api/v1/tools/reliability` | Tool reliability profiles |

Ver `docs/RRM2.md` y `docs/RRM3.md` para contratos completos.

---

## Flujo de governance (approvals)

```text
Operator: FOUNDER REQUEST / PREPARE
  ↓
Persist ImmutableActionProposal (checksum + expires_at)
  ↓
Policy evaluation inicial
  ↓
Reviewer: APPROVE
  ↓
Re-validación policy + checksum + expiración
  ↓
Execute frozen payload (sin skip_policy)
  ↓
Persist SideEffectRecord + OutboxEvent (TX atómica)
```

En la consola UI: operator en `/sessions/new` → reviewer en `/approvals`.

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

**Antes de cada commit/PR** (mismo alcance que CI en `.github/workflows/rrm1-gate.yml`):

```bash
pip install -e ".[dev]"
OTEL_SDK_DISABLED=true ./scripts/ci-local.sh
```

Con Postgres local (`docker compose up -d db`):

```bash
export DATABASE_URL=postgresql://ceo:ceo@localhost:5432/ceo_agent
export USE_IN_MEMORY_STORE=false
OTEL_SDK_DISABLED=true ./scripts/ci-local.sh
```

Ver también `AGENTS.md` para reglas de agentes.

| Suite | Qué valida |
|-------|------------|
| `tests/unit/` | Runtime, context, preprocessor, session summaries |
| `tests/gate/` | Replay, outbox, RRM-1..3 milestones |
| `tests/ui/` | Consola MVP-1 (dashboard, timeline, replay, export) |
| `tests/governance/` | Matriz RBAC operator/reviewer |
| `tests/vertical_slice/` | Gate VS + governance E2E |
| `tests/integration/test_postgres_*` | Postgres (job CI `postgres-integration`) |

Tests en memoria usan `USE_IN_MEMORY_STORE=true` y `AUTH_DISABLED=true` via `conftest.py`.

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
| Done (RRM-3) | Adaptive cognition, tool reliability, session stability |
| Done (MVP-1) | Consola operacional SSR/HTMX, human summaries, demo seed |
| Should Have | Replay diff visualization en UI |
| Should Have | Approval cryptographic signing |
| Should Have | Tests multi-worker reales (Postgres + procesos) |
| Could Have | SSE live updates en timeline |
| Could Have | Temporal integration |
| Could Have | Kafka migration |

---

## Desarrollo

### Convenciones

- Contratos Pydantic en `schemas/` — no duplicar tipos en runtime
- Side effects siempre via router + policy
- Timeline y replay nunca desde memoria de runtime
- Orchestrator coordina; Agno piensa
- UI lee via `UIQueryFacade` — **sin HTTP loopback** a `/api/v1` desde `ui/`
- Mutaciones UI → `ManualOrchestrator` / `approval_service` (misma autoridad que API)

### Lint / typecheck

El proyecto usa `pytest` como gate principal. Correr **siempre** antes de cada PR:

```bash
OTEL_SDK_DISABLED=true ./scripts/ci-local.sh
```

---

## Licencia

Proyecto privado / en desarrollo. Consultar repositorio para términos aplicables.
