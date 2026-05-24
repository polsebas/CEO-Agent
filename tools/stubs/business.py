"""Stub tools for CFO, COO, CMO and CEO read operations."""

from __future__ import annotations

from core.persistence import get_world_state


async def read_kpi_dashboard() -> dict:
    c = get_world_state().company
    return {
        "mrr_usd": c.mrr_usd,
        "churn_rate": c.churn_rate,
        "burn_rate_usd": c.burn_rate_usd,
        "runway_months": c.runway_months,
    }


async def get_cashflow_summary() -> dict:
    c = get_world_state().company
    return {
        "monthly_revenue": c.mrr_usd,
        "monthly_burn": c.burn_rate_usd,
        "net_cashflow": c.mrr_usd - c.burn_rate_usd,
    }


async def calculate_runway() -> dict:
    c = get_world_state().company
    return {"runway_months": c.runway_months, "burn_rate_usd": c.burn_rate_usd}


async def detect_blockers() -> dict:
    return {"blockers": ["Auth middleware PR blocked", "CI pipeline failing on main"], "count": 2}


async def list_active_tasks() -> dict:
    return {
        "tasks": [
            {"id": "T-1", "title": "Resolve deployment anomaly", "status": "in_progress"},
            {"id": "T-2", "title": "Review Q1 budget", "status": "pending"},
        ]
    }


async def get_analytics_summary() -> dict:
    return {
        "cac_usd": 120.0,
        "ltv_usd": 980.0,
        "conversion_rate": 0.034,
        "active_campaigns": 2,
    }


async def propose_campaign(name: str = "Q2 Growth") -> dict:
    return {"proposal": name, "estimated_cac": 115.0, "status": "draft"}


async def create_initiative(title: str, owner: str = "ceo") -> dict:
    return {"initiative_id": "INIT-001", "title": title, "owner": owner, "status": "created"}


async def escalate_to_human(reason: str) -> dict:
    return {"escalated": True, "reason": reason, "queue": "human_board"}
