"""Canonical stub response contracts for FacilRentaCar tools."""

from __future__ import annotations

RESERVATION_DETAIL = {
    "reservation_id": "RES-2024-0891",
    "client_id": "CLI-4421",
    "client_name": "Empresa XYZ S.A.",
    "vehicle_id": "VEH-112",
    "amount_ars": 185000.0,
    "days_remaining": 3,
    "status": "active",
}

COMPENSATION_POLICY = {
    "max_pct": 0.20,
    "policy_name": "standard_compensation",
    "requires_approval_above_pct": 0.15,
}

APPLY_DISCOUNT_SUCCESS = {
    "reservation_id": "RES-2024-0891",
    "discount_pct": 0.12,
    "new_amount_ars": 162800.0,
    "status": "applied",
}

CLIENT_HISTORY = {
    "client_id": "CORP-0088",
    "client_name": "Grupo Constructor Mendoza S.A.",
    "months_active": 18,
    "reservations_ytd": 34,
    "revenue_ytd_ars": 2840000.0,
    "incidents_ytd": 1,
}

CANCELLATION_POLICY = {
    "penalty_pct": 0.30,
    "grace_period_hours": 48,
    "corporate_exception_allowed": True,
}

CANCELLATION_OVERRIDE_SUCCESS = {
    "client_id": "CORP-0088",
    "reservation_ids": ["RES-2024-0901", "RES-2024-0902", "RES-2024-0903"],
    "override_type": "full_refund",
    "status": "cancelled",
}

FLEET_OCCUPANCY = {
    "period_start": "2024-12-20",
    "period_end": "2025-01-03",
    "overall_occupancy_pct": 0.93,
    "categories": {
        "SUV": {"occupancy_pct": 0.95, "available": 1},
        "Pickup": {"occupancy_pct": 0.91, "available": 2},
    },
}

CURRENT_RATES = {
    "SUV": 28000.0,
    "Pickup": 28000.0,
}

MARKET_RATES = {
    "SUV": 35000.0,
    "Pickup": 34000.0,
}

RATE_ADJUSTMENT_SUCCESS = {
    "categories": ["SUV", "Pickup"],
    "new_rate_ars_per_day": 32200.0,
    "valid_from": "2024-12-20",
    "valid_to": "2025-01-03",
    "status": "published",
}

BRANCH_STATUS = {
    "branch": "Mendoza Centro",
    "staff_available": 4,
    "operational_capacity": 6,
    "vehicles_in_service": 12,
}

PENDING_RESERVATIONS = {
    "branch": "Mendoza Centro",
    "pending_count": 3,
    "reservation_ids": ["RES-P-101", "RES-P-102", "RES-P-103"],
}

ACTIVATE_VEHICLES_SUCCESS = {
    "vehicle_ids": ["VEH-205", "VEH-206"],
    "status": "available",
    "activated_count": 2,
}

LINKEDIN_ANALYTICS = {
    "cac_usd": 145.0,
    "ltv_usd": 980.0,
    "conversion_rate": 0.028,
    "active_campaigns": 1,
    "organic_impressions": 42000,
    "organic_ctr": 0.019,
}

LINKEDIN_CAMPAIGN_DRAFT = {
    "proposal": "B2B Fleet Lead Gen — Q1",
    "estimated_cac": 130.0,
    "status": "draft",
}

LINKEDIN_CAMPAIGN_LAUNCH_SUCCESS = {
    "campaign_name": "B2B Fleet Lead Gen — Q1",
    "status": "live",
    "launched_channel": "linkedin",
}

CONTRACT_BY_TOOL: dict[str, dict] = {
    "get_reservation_detail": RESERVATION_DETAIL,
    "get_compensation_policy": COMPENSATION_POLICY,
    "apply_reservation_discount": APPLY_DISCOUNT_SUCCESS,
    "get_client_history": CLIENT_HISTORY,
    "get_cancellation_policy": CANCELLATION_POLICY,
    "execute_cancellation_override": CANCELLATION_OVERRIDE_SUCCESS,
    "get_fleet_occupancy": FLEET_OCCUPANCY,
    "get_current_rates": CURRENT_RATES,
    "get_market_rates": MARKET_RATES,
    "publish_rate_adjustment": RATE_ADJUSTMENT_SUCCESS,
    "get_branch_status": BRANCH_STATUS,
    "get_pending_reservations_by_branch": PENDING_RESERVATIONS,
    "activate_vehicles": ACTIVATE_VEHICLES_SUCCESS,
    "get_analytics_summary": LINKEDIN_ANALYTICS,
    "propose_campaign": LINKEDIN_CAMPAIGN_DRAFT,
    "launch_linkedin_campaign": LINKEDIN_CAMPAIGN_LAUNCH_SUCCESS,
}
