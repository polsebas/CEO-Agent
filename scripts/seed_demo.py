#!/usr/bin/env python3
"""Seed deterministic demo sessions for MVP-1 walkthroughs."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


async def seed_demo(fixtures: list[str] | None = None) -> list[dict]:
    reset_in_memory_store()
    results = []
    paths = sorted(DEMO_DIR.glob("*.json"))
    if fixtures:
        paths = [DEMO_DIR / f"{name}.json" if not name.endswith(".json") else DEMO_DIR / name for name in fixtures]

    for path in paths:
        if not path.exists():
            continue
        spec = json.loads(path.read_text())
        result = await manual_orchestrator.run_founder_request(
            spec["message"],
            session_id=spec["session_id"],
            correlation_id=spec["correlation_id"],
        )
        results.append(
            {
                "demo_id": spec.get("demo_id", path.stem),
                "title": spec.get("title", path.stem),
                "session_id": result.get("session_id", spec["session_id"]),
                "correlation_id": result.get("correlation_id", spec["correlation_id"]),
                "ui_url": f"/sessions/{spec['session_id']}?correlation_id={spec['correlation_id']}",
            }
        )
        print(f"Seeded {spec.get('demo_id')}: {spec['session_id']}")
    return results


def main() -> None:
    asyncio.run(seed_demo())
    print("\nOpen http://localhost:8000/login (role: operator) then visit session URLs above.")


if __name__ == "__main__":
    main()
