# Agent instructions (CEO-Agent)

Coding agents must follow this file **and** `.cursor/rules/*.mdc` before proposing commits.

## Pre-commit CI (non-negotiable)

GitHub Actions workflow: `.github/workflows/rrm1-gate.yml` (`RRM1 Gate`).

### Always run before commit

```bash
pip install -e ".[dev]"
OTEL_SDK_DISABLED=true ./scripts/ci-local.sh
```

Exit code must be **0**. Do not commit if tests fail.

### Postgres integration (second CI job)

Required when modifying persistence, replay store, outbox, session locks, diagnostics spans, or `tests/integration/test_postgres_*`:

```bash
docker compose up -d db
export DATABASE_URL=postgresql://ceo:ceo@localhost:5432/ceo_agent
export USE_IN_MEMORY_STORE=false
OTEL_SDK_DISABLED=true ./scripts/ci-local.sh
```

Without `DATABASE_URL`, `ci-local.sh` only runs `unit-and-gate` and prints a skip notice — that is **not** enough for persistence changes.

### Common mistakes (causes CI red on push)

| Mistake | Fix |
|---------|-----|
| `pytest tests/ -q` only | Use `./scripts/ci-local.sh` (exact CI paths) |
| Subset of tests after a "small" fix | Full `ci-local.sh` before commit |
| Postgres paths changed, no `DATABASE_URL` | Run postgres job locally |
| Commit without running tests | Run gate first; report pass in summary |

## Runtime authority

For `core/`, `tests/gate/`, `tests/integration/`:

- Read `.agents/skills/runtime-reliability-architecture/SKILL.md`
- Enforce `docs/runtime_invariants.md`
- Cursor rule: `.cursor/rules/runtime-authority-core.mdc`

## Priority

Correctness → replay → governance → determinism → diagnostics → cognition → performance.
