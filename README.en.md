# CEO-Agent — Enterprise Cognitive Operating System

Multi-agent platform for executive operations with a **governed cognitive runtime**, built as an enterprise-grade Vertical Slice before scaling to the full suite (CEO, CFO, COO, CTO, CMO).

The goal is not merely to “have agents”, but to **enforce the architectural contract**: non-bypassable governance, deterministic replay, transactional outbox, real cognition via Agno, hardened gate validation, and an **operational console** so humans can run sessions without reading raw logs.

> **Languages:** [Español](README.md) · English

---

## What it solves

CEO-Agent coordinates executive decisions across specialized agents with:

- **Explicit manual orchestration** (`ManualOrchestrator`) as the primary path from day 1
- **Observable runtime** with a state machine (`RuntimeStateMachine`)
- **Governance** with immutable approvals, policy engine, and RBAC
- **Transactional persistence** (decision + side effect + outbox in a single TX)
- **Frozen/live replay** for audit and debugging
- **Deterministic layer** (4-tier preprocessor) before invoking the LLM
- **Real Agno integration** with `output_schema` and `StructuredAgentRunner`

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Runtime / API | Python 3.11+, FastAPI, Uvicorn |
| Operational console (MVP-1) | Jinja2 SSR, HTMX, Tailwind CSS |
| Agents | Agno |
| Contracts | Pydantic v2 |
| Auth | JWT (`python-jose`) + RBAC |
| Observability | OpenTelemetry + Prometheus (`/metrics`) |
| Persistence | PostgreSQL (asyncpg) + in-memory fallback |
| Cache | Redis (with in-memory fallback) |
| Local infra | Docker Compose (Postgres + Redis) |

**Out of MVP scope:** Neo4j, Kafka, Agno Teams as primary orchestrator, Temporal.

---

## Architecture

```text
Founder / API / Ops Console (HTMX)
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  4-tier Preprocessor (regex → embedding → LLM fallback)     │
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

### Design principle

```text
contracts → deterministic layer → cognition
```

The orchestrator **coordinates and governs**, but **does not replace cognition**. CEO/CTO run via Agno (`agent.arun`) with `output_schema` validated by `StructuredAgentRunner`.

---

## Project structure

```text
CEO-Agent/
├── agents/              # Agno factory + expanded delegation (CFO/COO/CMO)
├── api/
│   ├── auth.py          # JWT + RBAC
│   ├── main.py          # FastAPI endpoints + UI mount
│   ├── diagnostics.py # RRM-2 diagnostics API
│   ├── adaptive.py      # RRM-3 adaptive cognition API
│   └── sessions.py      # Session listing (MVP-1)
├── ui/                  # Operational SSR console (MVP-1)
│   ├── routes/          # Dashboard, sessions, replay, approvals…
│   ├── templates/       # Jinja2 + HTMX partials
│   ├── static/          # CSS, HTMX
│   └── services/        # UIQueryFacade, human_labels
├── core/
│   ├── orchestrator.py  # ManualOrchestrator (primary path)
│   ├── diagnostics.py # DiagnosticsService (read-only)
│   ├── session_summary_builder.py  # Human-readable narratives
│   ├── session_list.py  # Session index
│   ├── runtime.py       # RuntimeStateMachine + transitions
│   ├── agent_runner.py  # StructuredAgentRunner (Agno + retry)
│   ├── approval_service.py  # Immutable approval workflow
│   ├── policy.py        # Policy engine + crisis mode
│   ├── persistence.py   # Transactional outbox + Postgres
│   ├── replay.py        # Frozen/live replay
│   ├── session_lock.py  # Cross-worker advisory locks
│   ├── preprocessor.py  # 4-tier preprocessor
│   ├── context.py       # ContextWindowManager L1-L5
│   ├── timeline.py      # Executive timeline
│   ├── health.py        # Persisted agent health
│   └── mcp_security.py  # MCP allowlist / anti-SSRF
├── demo/                # Deterministic demo fixtures (MVP-1)
├── scripts/
│   ├── seed_demo.py     # Demo session seed
│   └── ci-local.sh
├── schemas/             # Pydantic contracts (runtime, approvals, world, etc.)
├── tools/
│   ├── router.py        # Tool router + policy gate
│   ├── registry.py      # Per-agent capabilities
│   ├── github/          # GitHub MCP + stub fallback
│   └── stubs/           # Business stubs (CFO/COO/CMO)
├── prompts/             # Agent constitutions (.md)
├── workers/
│   └── outbox_processor.py
├── tests/
│   ├── unit/
│   ├── gate/            # RRM milestones
│   ├── ui/              # MVP-1 console tests
│   └── vertical_slice/  # Gate tests + governance E2E
├── docs/
│   ├── RRM2.md
│   ├── RRM3.md
│   └── MVP1_DEMO.md     # Operational demo script
├── docker-compose.yml
├── main.py              # Uvicorn entry point
├── package.json         # Tailwind CLI (UI)
└── pyproject.toml
```

### Reference documentation

| Document | Content |
|----------|---------|
| `docs/MVP1_DEMO.md` | Operational console demo script (&lt;10 min) |
| `docs/RRM2.md` | Runtime Intelligence — diagnostics, spans, telemetry |
| `docs/RRM3.md` | Adaptive cognition — policy, stability, governance |
| `spec_mvp_ceo_agent_platform_v_1.md` | Platform MVP spec |
| `Guía de Arquitectura para Sistemas de Agentes Autónomos (Enterprise AI).md` | Enterprise patterns |
| `Guía de Entorno de Desarrollo para Sistemas de Agentes de IA (v1.0).md` | Development conventions |

---

## Agents

| Agent | Status | Role |
|-------|--------|------|
| **CEO** | Vertical Slice (active) | Executive analysis, delegation, prioritization |
| **CTO** | Vertical Slice (active) | Incidents, GitHub, repo health, deployment |
| **CFO** | Post-gate | Cashflow, runway |
| **COO** | Post-gate | Blockers, operational tasks |
| **CMO** | Post-gate | Analytics, campaigns |

CFO/COO/CMO agents are implemented in `agents/expanded.py` and activate after passing the Vertical Slice validation gate.

---

## Quick start

### 1. Infrastructure

```bash
cp .env.example .env
docker compose up -d
```

### 2. Dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### 3. Environment variables

In addition to `.env.example`, the hardened runtime uses:

```bash
# Auth (required in production)
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
AUTH_DISABLED=false          # true only for local dev/tests

# MCP security
ALLOWED_MCP_HOSTS=localhost,127.0.0.1,github-mcp.internal

# LLM (optional — without a key, deterministic fallback is used)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
GOOGLE_GEMINI_MODEL=gemini-3.5-flash
LLM_PROVIDER=auto                 # Google first, then Anthropic, then OpenAI

# Persistence
DATABASE_URL=postgresql://ceo:ceo@localhost:5432/ceo_agent
REDIS_URL=redis://localhost:6379/0
USE_IN_MEMORY_STORE=false    # true forces in-memory store (tests)

# GitHub MCP (optional — falls back to stub if unreachable)
GITHUB_MCP_URL=http://localhost:8001
GITHUB_REPO=owner/repo
```

### 4. Start the API

```bash
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

### 5. Operational console (MVP-1)

```bash
# Optional demo session seed
.venv/bin/python scripts/seed_demo.py

# Start API (same process serves JSON + UI)
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/login** and pick a role:

| Role | Demo use |
|------|----------|
| `operator` | Run founder requests, view sessions/replay |
| `reviewer` | Approve pending actions |
| `readonly` | Observe dashboard and diagnostics |

Full walkthrough: [`docs/MVP1_DEMO.md`](docs/MVP1_DEMO.md).

**Main screens:**

| Route | Description |
|-------|-------------|
| `/` | Dashboard — recent/degraded sessions, approvals |
| `/sessions` | List with search and filters |
| `/sessions/{id}?correlation_id=` | Detail + unified timeline (HTMX 5s refresh) |
| `/sessions/{id}/replay` | Replay inspector (frozen/live) |
| `/sessions/{id}/diagnostics` | Diagnostics + human summaries |
| `/sessions/{id}/adaptive` | Adaptive policy and stability |
| `/approvals` | Approval queue |
| `/sessions/new` | Founder request (operator) |

**CSS (optional):** rebuild Tailwind with `npm install && npm run build:css`.

The UI **does not HTTP-loopback to `/api/v1`** — it reads via `UIQueryFacade` → core services (`DiagnosticsService`, `policy_engine`, etc.).

---

## Authentication and RBAC

JSON endpoints require a JWT Bearer token. The UI console accepts an HttpOnly `ceo_token` cookie (via `/login`) or the same Bearer header.

Unless `AUTH_DISABLED=true` (dev/tests only).

### Roles (MVP-1)

| Role | Level | Execute / prepare | Approve | Observe |
|------|-------|-------------------|---------|---------|
| `readonly` | 0 | — | — | sessions, diagnostics, timeline, approvals (read) |
| `operator` | 1 | founder request, prepare, replay execute | — | sessions, diagnostics |
| `reviewer` | 2 | — | approve | sessions, diagnostics, approvals |
| `admin` | 3 | full operational | approve (level 2+) | + agents health |
| `founder` | 4 | all permissions | all | all |

**Operator / reviewer** separation enables human-in-the-loop demos: operators execute; reviewers approve.

### Permission matrix (API)

| Endpoint | Auth | Permission / role |
|----------|------|-------------------|
| `GET /health`, `GET /metrics` | No | — |
| `GET /api/v1/sessions` | Yes | `SESSION_READ` |
| `POST /api/v1/founder/request` | Yes | `FOUNDER_REQUEST` (operator+) |
| `POST /api/v1/actions/prepare` | Yes | `ACTION_PREPARE` (operator+) |
| `POST /api/v1/actions/approve/{id}` | Yes | `ACTION_APPROVE` (reviewer+) |
| `GET /api/v1/approvals` | Yes | `APPROVALS_READ` |
| `GET /api/v1/timeline` | Yes | `TIMELINE_READ` |
| `GET /api/v1/replay/{session_id}` | Yes | `REPLAY_EXECUTE` (operator+) |
| `GET /api/v1/sessions/{id}/diagnostics` | Yes | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/health` | Yes | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/spans` | Yes | `DIAGNOSTICS_READ` |
| `GET /api/v1/replay/{id}/analysis` | Yes | `DIAGNOSTICS_READ` |
| `GET /api/v1/sessions/{id}/adaptive-policy` | Yes | `DIAGNOSTICS_READ` |
| `GET /api/v1/replay/{id}/governance` | Yes | `DIAGNOSTICS_READ` |
| `GET /api/v1/agents/health` | Yes | `AGENTS_HEALTH` (admin+) |

HTML routes (`/`, `/sessions`, `/approvals`, …) enforce the same permissions via `UIQueryFacade`.

### Generate a test token

```python
from api.auth import create_test_token
from core.roles import UserRole

token = create_test_token(user_id="operator-1", role=UserRole.OPERATOR)
# Header: Authorization: Bearer <token>
```

---

## API — Main endpoints

### `POST /api/v1/founder/request`

Founder input. The preprocessor decides whether to respond deterministically (tier 1/2) or trigger the full cognitive flow.

```json
{
  "message": "Analyze deployment anomaly and incident status",
  "session_id": "optional-uuid",
  "correlation_id": "optional-uuid"
}
```

**Cognitive response:** includes `session_id`, `correlation_id`, `runtime_state`, and `result` with CEO analysis + CTO delegation when applicable.

### `POST /api/v1/actions/prepare`

Creates an approval with an **immutable payload** (checksum + expiration).

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

Approves and executes the frozen payload. Re-validates policy, checksum, and expiration. **`skip_policy` is not allowed.**

### `GET /api/v1/sessions`

Operational session list (from `session_diagnostics`).

Query params: `limit`, `offset`, `status`, `health`, `has_pending_approvals`, `search`, `degraded_only`.

### `GET /api/v1/timeline?correlation_id=`

Executive timeline derived exclusively from `OutboxEvent` + `DecisionRecord` + `SideEffectRecord`.

### `GET /api/v1/replay/{session_id}?correlation_id=&mode=frozen|live`

- **frozen:** historical snapshots only (no real tools or current world state)
- **live:** re-execution against recent state

### `GET /api/v1/agents/health`

Per-agent health metrics (success rate, degraded mode, latency).

### Diagnostics & adaptive (RRM-2 / RRM-3)

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/sessions/{id}/diagnostics?correlation_id=` | Unified `SessionDiagnostics` snapshot |
| `GET /api/v1/sessions/{id}/health` | `RuntimeHealth` |
| `GET /api/v1/sessions/{id}/spans` | Execution span tree |
| `GET /api/v1/sessions/{id}/telemetry` | Cognitive telemetry |
| `GET /api/v1/replay/{id}/analysis?correlation_id=` | `ReplayAnalytics` (drift, confidence) |
| `GET /api/v1/sessions/{id}/adaptive-policy` | Adaptive policy snapshot |
| `GET /api/v1/sessions/{id}/stability` | Session stability events |
| `GET /api/v1/replay/{id}/governance` | Governance + replay analytics |
| `GET /api/v1/tools/reliability` | Tool reliability profiles |

See `docs/RRM2.md` and `docs/RRM3.md` for full contracts.

---

## Governance flow (approvals)

```text
Operator: FOUNDER REQUEST / PREPARE
  ↓
Persist ImmutableActionProposal (checksum + expires_at)
  ↓
Initial policy evaluation
  ↓
Reviewer: APPROVE
  ↓
Re-validate policy + checksum + expiration
  ↓
Execute frozen payload (no skip_policy)
  ↓
Persist SideEffectRecord + OutboxEvent (atomic TX)
```

In the UI console: operator at `/sessions/new` → reviewer at `/approvals`.

Key fields on `ImmutableActionProposal`:

- `id`, `correlation_id`, `action`, `parameters`
- `proposed_by`, `approval_level`
- `checksum` (SHA-256 of the payload)
- `expires_at`

---

## Runtime — States and transitions

Main states: `idle → perceiving → reasoning → waiting_tool → observing → completed`

Also: `waiting_approval`, `executing`, `replanning`, `escalated`, `failed`

Explicit transitions in `schemas/runtime.py` (`VALID_TRANSITIONS`). Notable post-hardening transition:

```text
PERCEIVING → ESCALATED   (degraded mode / early escalation)
```

### Crisis mode

`PolicyEngine` detects crises (infrastructure, financial, etc.) and applies overrides:

- Approval level delta
- Routing priority
- **Context expansion** (extra L3/L4 layers via `ContextWindowManager`)

### Session isolation

Locks via `pg_advisory_xact_lock(hashtext(session_id))` in Postgres, with in-process fallback for dev/tests.

---

## Cognition — Agno + StructuredRetry

```text
StructuredAgentRunner.run()
  ↓
agent.arun(prompt, output_schema=CEOResponse|CTOResponse)
  ↓
parse_structured_response()  (repair + retry cap)
  ↓
deterministic fallback if no LLM model is configured
```

- Without an LLM API key: runtime continues with deterministic structured responses
- With an API key: real cognition via Agno
- Global retry cap in `schemas/responses/base.py` (`MAX_STRUCTURED_RETRIES_GLOBAL`)

---

## Persistence

### Transactional Outbox

`persist_execution_bundle()` writes in **a single transaction**:

1. `DecisionRecord` (optional)
2. `SideEffectRecord` (optional)
3. `OutboxEvent`

### Postgres tables (auto-created)

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

## Tools and MCP

The router (`tools/router.py`) normalizes all invocations to `ToolResult` and applies:

- Per-agent permissions (`tools/registry.py`)
- Policy gate by `side_effect_level`
- Redis cache for read-only tools
- 3s MCP timeout with stub fallback

### GitHub MCP

`tools/github/client.py` attempts real MCP and falls back to stub. URLs are validated against an allowlist (`core/mcp_security.py`) to prevent SSRF.

---

## Tests

**Before every commit/PR** (same scope as CI in `.github/workflows/rrm1-gate.yml`):

```bash
pip install -e ".[dev]"
OTEL_SDK_DISABLED=true ./scripts/ci-local.sh
```

With local Postgres (`docker compose up -d db`):

```bash
export DATABASE_URL=postgresql://ceo:ceo@localhost:5432/ceo_agent
export USE_IN_MEMORY_STORE=false
OTEL_SDK_DISABLED=true ./scripts/ci-local.sh
```

| Suite | Validates |
|-------|-----------|
| `tests/unit/` | Runtime, context, preprocessor, session summaries |
| `tests/gate/` | Replay, outbox, RRM-1..3 milestones |
| `tests/ui/` | MVP-1 console (dashboard, timeline, replay, export) |
| `tests/governance/` | Operator/reviewer RBAC matrix |
| `tests/vertical_slice/` | VS gate + governance E2E |
| `tests/integration/test_postgres_*` | Postgres integration |

Tests use `USE_IN_MEMORY_STORE=true` and `AUTH_DISABLED=true` via `conftest.py`.

---

## Vertical Slice approval criteria

The VS is considered production-grade when:

| Area | Criterion |
|------|-----------|
| **Runtime** | 0 `InvalidStateTransition` under load; 0 session leakage multi-worker |
| **Replay** | 100% deterministic in frozen mode |
| **Governance** | 0 approval bypasses; authenticated endpoints; immutable payloads |
| **Persistence** | 0 dual-write; 100% outbox atomicity |
| **Cognition** | Agno executed; StructuredRetry end-to-end; `output_schema` enforced |

---

## Roadmap (post-hardening)

| Priority | Item |
|----------|------|
| Done (RRM-2) | OpenTelemetry traces (OTLP) + Prometheus metrics at `/metrics` |
| Done (RRM-3) | Adaptive cognition, tool reliability, session stability |
| Done (MVP-1) | Operational SSR/HTMX console, human summaries, demo seed |
| Should Have | Replay diff visualization in UI |
| Should Have | Approval cryptographic signing |
| Should Have | Real multi-worker tests (Postgres + processes) |
| Could Have | SSE live timeline updates |
| Could Have | Temporal integration |
| Could Have | Kafka migration |

---

## Development

### Conventions

- Pydantic contracts in `schemas/` — do not duplicate types in runtime
- Side effects always via router + policy
- Timeline and replay never from runtime memory
- Orchestrator coordinates; Agno thinks
- UI reads via `UIQueryFacade` — **no HTTP loopback** to `/api/v1` from `ui/`
- UI mutations → `ManualOrchestrator` / `approval_service` (same authority as API)

### Lint / typecheck

The project uses `pytest` as the primary gate. Run tests before every PR:

```bash
OTEL_SDK_DISABLED=true ./scripts/ci-local.sh
```

---

## License

Private / in-development project. Refer to the repository for applicable terms.
