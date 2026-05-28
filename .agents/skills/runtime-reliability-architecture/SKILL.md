---
name: runtime-reliability-architecture
description: >-
  Architectural operating system for CEO-Agent — deterministic transactional
  replay-aware runtime authority, governance, replay, and intelligence
  invariants. Use when changing core/, orchestrator, persist_runtime_tx,
  replay, governance, session diagnostics, RRM milestones, or any mutative
  runtime path. Mandatory pre-check before architectural changes.
---

# Runtime Reliability & Intelligence — Architectural Skill Alignment

## Purpose

This document defines the architectural principles, runtime invariants, implementation philosophy, and engineering heuristics that every coding agent, contributor, or autonomous implementation workflow MUST follow when operating on the CEO-Agent runtime.

The goal is alignment.

This is not a feature spec.
This is the architectural operating system of the project.

---

# 1. Core Architectural Thesis

The system is NOT:

* a chatbot
* an LLM wrapper
* an agent playground
* a prompt orchestration demo

The system IS:

> A deterministic, transactional, replay-aware runtime for operational AI execution.

LLMs are cognition providers.
The runtime is the authority.

This distinction is absolute.

---

# 2. Runtime Authority Model

## Source of Truth

The ONLY runtime authority is:

* ManualOrchestrator
* RuntimeStateMachine
* persist_runtime_tx
* governance/policy layer
* advisory lock boundary
* replay baseline + canonical outcome

Everything else is secondary.

---

## Cognition Adapters

Agno and future cognition frameworks are:

* interchangeable
* non-authoritative
* non-persistent
* non-governing

They may:

* reason
* summarize
* synthesize
* classify
* propose

They may NEVER:

* mutate runtime state directly
* bypass policy
* persist authoritative state
* execute tools outside orchestrator control
* define replay truth
* define governance truth

---

# 3. Determinism Philosophy

Determinism is a first-class architectural requirement.

The runtime MUST always prefer:

* replayability
* auditability
* transactional consistency
* causal traceability

over:

* raw creativity
* emergent autonomy
* probabilistic orchestration
* hidden memory

---

## Golden Rule

If a behavior cannot be:

* replayed
* diagnosed
* traced
* versioned
* bounded

then it does NOT belong in the runtime core.

---

# 4. Replay Philosophy

Replay is NOT:

* “rerun the LLM and hope”
* snapshot comparison only
* serialization hashing

Replay IS:

> Integrity verification of persisted execution semantics.

The authoritative replay primitives are:

* CanonicalReplayOutcome
* Runtime transitions
* Tool sequence
* Decision sequence
* Side effects
* Approvals
* Prompt lineage
* Replay baselines

---

## Frozen Replay

Frozen replay validates:

* runtime transition integrity
* execution routing integrity
* orchestration version compatibility
* persisted execution semantics

Frozen replay does NOT require:

* re-running cognition
* re-running policy
* re-running live tools

---

## Live Replay

Live replay exists ONLY to:

* detect drift
* compare runtime behavior
* measure divergence

It MUST NEVER mutate authoritative snapshots.

---

# 5. Transactional Runtime Rules

Every mutative runtime operation MUST:

1. Acquire pg_advisory_xact_lock
2. Execute inside ONE authoritative transaction
3. Persist through persist_runtime_tx
4. Produce replay-compatible artifacts
5. Preserve idempotency semantics

---

## Forbidden Patterns

### NEVER

* write directly to memory stores in production paths
* bypass runtime transaction boundaries
* create hidden persistence side effects
* mutate state outside orchestrator
* use dual-write runtime logic
* create background mutations outside replay visibility

---

# 6. Governance Philosophy

Governance is runtime infrastructure.

NOT UI.
NOT metadata.
NOT optional.

Approvals, policy, RBAC, escalation, and side-effect levels are part of the execution engine itself.

---

## Governance Requirements

All production mutative flows MUST pass:

JWT → PermissionMatrix → PolicyEngine → ApprovalBinding → Runtime TX

No exceptions.

---

# 7. Context Engineering Philosophy

Context is treated as:

> A bounded operational resource.

NOT an infinite memory stream.

---

## Context Requirements

Context systems MUST support:

* deterministic reconstruction
* fingerprinting
* provenance tracking
* lifecycle management
* bounded compression
* replay compatibility

---

## Forbidden Context Patterns

### NEVER

* hidden memory
* opaque vector recalls in runtime-critical flows
* non-versioned summarization
* mutation without provenance
* context expansion without budget accounting

---

# 8. Runtime Intelligence Layer Philosophy

Observability is NOT logging.

Runtime Intelligence exists to:

* explain execution
* diagnose degradation
* measure cognition quality
* identify anomalies
* enforce operational boundaries

The intelligence layer is observational.

It MUST NOT:

* silently alter execution semantics
* mutate runtime authority
* bypass orchestrator decisions

---

# 9. Health Engine Philosophy

Runtime health is:

> An operational signal system.

It is NOT autonomous governance.

Health engines may:

* activate degraded mode
* reduce cognition budgets
* suppress retries
* force deterministic fallbacks
* escalate approvals

They may NOT:

* invent actions
* override governance
* bypass replay constraints

---

# 10. Adaptive Orchestration Philosophy (RRM-3 Direction)

Future runtime evolution should focus on:

* adaptive orchestration
* cognition quality
* operational reasoning stability
* context prioritization
* replay-aware intelligence
* tool trust scoring
* health-driven execution strategies

NOT infrastructure complexity.

---

## Explicit Anti-Goals Before RRM-4

Do NOT prematurely introduce:

* Kafka
* Temporal
* swarm agents
* distributed orchestration
* microservice fragmentation
* autonomous loops
* uncontrolled delegation graphs
* multi-tenant complexity

until cognition/runtime behavior is operationally stable.

---

# 11. Scaling Philosophy

Scale is NOT the next problem.

Correctness precedes scale.

Replayability precedes distribution.

Operational intelligence precedes infrastructure expansion.

The runtime should remain:

* centrally understandable
* causally traceable
* replay-verifiable

for as long as possible.

---

# 12. Testing Philosophy

Passing tests are NOT success.

The true success condition is:

> A complex session can be reproduced, diagnosed, audited, and reasoned about under concurrency without state corruption.

---

## Required Testing Layers

### Unit

* deterministic
* isolated
* explicit in-memory

### Integration

* Postgres
* advisory locks
* transactional replay
* outbox semantics

### Gate

* replay integrity
* session diagnostics
* runtime degradation
* concurrency correctness
* deterministic outcomes

---

# 13. Engineering Heuristics

## Prefer

* explicit state
* immutable artifacts
* append-only models
* deterministic identifiers
* canonical serialization
* replay-aware persistence
* operational traceability

---

## Avoid

* hidden globals
* magical orchestration
* framework-driven runtime logic
* implicit retries
* side effects outside TX
* uncontrolled async fanout
* non-versioned cognition behavior

---

# 14. Runtime Design Priorities

Priority order for architectural decisions:

1. Runtime correctness
2. Replay integrity
3. Governance integrity
4. Deterministic behavior
5. Diagnostics quality
6. Operational intelligence
7. Cognition quality
8. Performance
9. Horizontal scale
10. Feature breadth

---

# 15. Definition of Architectural Success

The runtime succeeds when:

* sessions are reproducible
* cognition is observable
* failures are diagnosable
* orchestration is explainable
* governance is enforceable
* degraded execution remains safe
* replay remains trustworthy
* operational behavior is stable under load

NOT when:

* the model sounds smart
* agents appear autonomous
* more frameworks are added
* prompts become more complex

---

# 16. Mandatory Rules for Coding Agents

Every coding agent operating on this repository MUST:

* preserve orchestrator authority
* preserve replay determinism
* preserve transactional integrity
* preserve governance boundaries
* preserve observability consistency
* avoid introducing hidden runtime state
* avoid bypassing persist_runtime_tx
* avoid adding non-replayable cognition paths

---

## Pre-commit CI gate (mandatory)

**Do not create a git commit** until local CI passes. This mirrors `.github/workflows/rrm1-gate.yml`.

```bash
pip install -e ".[dev]"
OTEL_SDK_DISABLED=true ./scripts/ci-local.sh
```

* `pytest tests/ -q` is **not** a substitute — use `scripts/ci-local.sh` (exact CI test paths).
* While debugging, a narrow pytest path is allowed; **before commit**, run the full script.
* Changes to persistence, replay, outbox, or `tests/integration/test_postgres_*` require the postgres job: `DATABASE_URL=postgresql://ceo:ceo@localhost:5432/ceo_agent USE_IN_MEMORY_STORE=false` (see `AGENTS.md`).
* On failure: fix, re-run until exit 0; never commit with a red gate.

See also: [AGENTS.md](../../AGENTS.md), `.cursor/rules/ci-pre-commit.mdc`.

---

## Before Any Architectural Change

The agent MUST ask:

1. Can this be replayed deterministically?
2. Can this be diagnosed operationally?
3. Does this preserve runtime authority?
4. Does this preserve transactional integrity?
5. Is this observable and versionable?
6. Could this create hidden state?
7. Could this bypass governance?

If any answer is unclear:

STOP.
Refactor the design.

---

# 17. Long-Term Vision

The target architecture is:

> An operational AI runtime that behaves more like a database transaction engine + workflow runtime than like a chatbot.

The cognition layer is replaceable.
The runtime semantics are not.

That distinction must remain true at every future milestone.

---

## Repository pointers

- Enforceable checklist: [docs/runtime_invariants.md](../../docs/runtime_invariants.md)
- Milestones: [docs/RRM1.md](../../docs/RRM1.md), [docs/RRM1.5.md](../../docs/RRM1.5.md), [docs/RRM2.md](../../docs/RRM2.md), [docs/RRM2.1.md](../../docs/RRM2.1.md)
