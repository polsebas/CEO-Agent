#!/usr/bin/env python3
"""RRM-1 gate report — reproducibility criteria, not test count."""

from __future__ import annotations

import subprocess
import sys


# Kept for ad-hoc reports; canonical pre-commit gate is scripts/ci-local.sh (see AGENTS.md).
CRITERIA = [
    (
        "unit-and-gate (CI mirror)",
        [
            "pytest",
            "tests/unit",
            "tests/governance",
            "tests/experimental",
            "tests/gate",
            "tests/vertical_slice",
            "tests/integration/test_session_contention.py",
            "-q",
            "--tb=short",
        ],
    ),
]


def main() -> int:
    results: list[tuple[str, bool, str]] = []
    for name, cmd in CRITERIA:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        ok = proc.returncode == 0
        results.append((name, ok, proc.stdout + proc.stderr))

    print("# RRM-1 Gate Report\n")
    all_ok = True
    for name, ok, out in results:
        status = "PASS" if ok else "FAIL"
        print(f"- **{name}**: {status}")
        if not ok:
            all_ok = False
            print(f"  ```\n{out[-2000:]}\n  ```")
    print("\n## Reproducibility criteria (manual verification)")
    print("- CanonicalReplayOutcome fingerprint stable across frozen replays")
    print("- No skip_policy in production router")
    print("- CEO+CTO only ACTIVE agents")
    print("- Session advisory lock on mutative paths")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
