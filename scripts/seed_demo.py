#!/usr/bin/env python3
"""Seed deterministic demo sessions for MVP-1 and FacilRentaCar scenarios."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"

MVP_FIXTURES = [
    "founder_strategy.json",
    "incident_response.json",
    "deployment_review.json",
    "degraded_session.json",
]

SCENARIO_FILES = {
    "compensation": "compensation_request.json",
    "cancellation": "cancellation_override.json",
    "occupancy": "fleet_occupancy_alert.json",
    "reactivation": "fleet_reactivation.json",
    "linkedin": "linkedin_campaign_request.json",
}


async def seed_fixture(path: Path) -> dict:
    spec = json.loads(path.read_text())
    if spec.get("event_type"):
        result = await manual_orchestrator.run_domain_event(
            spec,
            session_id=spec["session_id"],
            correlation_id=spec["correlation_id"],
        )
    else:
        result = await manual_orchestrator.run_founder_request(
            spec["message"],
            session_id=spec["session_id"],
            correlation_id=spec["correlation_id"],
        )
    return {
        "demo_id": spec.get("demo_id", path.stem),
        "title": spec.get("title", path.stem),
        "session_id": result.get("session_id", spec["session_id"]),
        "correlation_id": result.get("correlation_id", spec["correlation_id"]),
        "approval_id": (result.get("approval") or {}).get("approval_id"),
        "ui_url": f"/sessions/{spec['session_id']}?correlation_id={spec['correlation_id']}",
        "approvals_url": "/approvals",
    }


async def seed_demo(
    fixtures: list[str] | None = None,
    scenario: str | None = None,
    *,
    facilrentacar_all: bool = False,
) -> list[dict]:
    reset_in_memory_store()
    results = []

    if scenario:
        filename = SCENARIO_FILES.get(scenario)
        if not filename:
            raise SystemExit(f"Unknown scenario: {scenario}. Choose from: {', '.join(SCENARIO_FILES)}")
        paths = [DEMO_DIR / filename]
    elif facilrentacar_all:
        paths = [DEMO_DIR / name for name in SCENARIO_FILES.values()]
    elif fixtures:
        paths = [
            DEMO_DIR / (f"{name}.json" if not name.endswith(".json") else name) for name in fixtures
        ]
    else:
        paths = [DEMO_DIR / name for name in MVP_FIXTURES]

    for path in paths:
        if not path.exists():
            continue
        row = await seed_fixture(path)
        results.append(row)
        print(f"Seeded {row['demo_id']}: {row['session_id']}")
        if row.get("approval_id"):
            print(f"  Pending approval: {row['approval_id']} → {row['approvals_url']}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CEO-Agent demo sessions")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIO_FILES.keys()),
        help="Seed a single FacilRentaCar scenario",
    )
    parser.add_argument(
        "--facilrentacar-all",
        action="store_true",
        help="Seed all four FacilRentaCar scenarios",
    )
    parser.add_argument("fixtures", nargs="*", help="Optional fixture filenames")
    args = parser.parse_args()
    asyncio.run(
        seed_demo(
            fixtures=args.fixtures or None,
            scenario=args.scenario,
            facilrentacar_all=args.facilrentacar_all,
        )
    )
    print("\nOpen http://localhost:8000/login then visit session URLs above.")
    print("Reviewer: http://localhost:8000/approvals")


if __name__ == "__main__":
    main()
