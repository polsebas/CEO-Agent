#!/usr/bin/env bash
# Local mirror of .github/workflows/rrm1-gate.yml — run before every commit/PR.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
  else
    PYTHON="python3"
  fi
fi

export OTEL_SDK_DISABLED="${OTEL_SDK_DISABLED:-true}"

echo "==> Installing dev dependencies (editable)"
"$PYTHON" -m pip install -e ".[dev]" -q

UNIT_GATE=(
  tests/unit
  tests/governance
  tests/experimental
  tests/gate
  tests/vertical_slice
  tests/integration/test_session_contention.py
)

echo "==> CI job: unit-and-gate"
"$PYTHON" -m pytest "${UNIT_GATE[@]}" -q --tb=short

if [[ "${CI_LOCAL_SKIP_POSTGRES:-}" == "1" ]]; then
  echo "==> Skipping postgres-integration (CI_LOCAL_SKIP_POSTGRES=1)"
  exit 0
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "==> postgres-integration: skipped (set DATABASE_URL to run; see AGENTS.md)"
  exit 0
fi

export USE_IN_MEMORY_STORE="${USE_IN_MEMORY_STORE:-false}"

POSTGRES_TESTS=(
  tests/integration/test_postgres_session.py
  tests/integration/test_postgres_replay.py
  tests/integration/test_postgres_outbox.py
  tests/integration/test_postgres_spans.py
  tests/integration/test_postgres_diagnostics.py
  tests/integration/test_postgres_rrm21_idempotency.py
)

echo "==> CI job: postgres-integration"
"$PYTHON" -m pytest "${POSTGRES_TESTS[@]}" -q --tb=short
