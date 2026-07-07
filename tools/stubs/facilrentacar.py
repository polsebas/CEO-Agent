"""FacilRentaCar tool stubs — read via MCP attempt, mutate only with approval_id."""

from __future__ import annotations

from tools.facilrentacar.client import _facilrentacar_mcp_call, _stub


async def get_reservation_detail(reservation_id: str) -> dict:
    mcp = await _facilrentacar_mcp_call("get_reservation_detail", {"reservation_id": reservation_id})
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub("get_reservation_detail", reservation_id=reservation_id)


async def get_compensation_policy() -> dict:
    mcp = await _facilrentacar_mcp_call("get_compensation_policy", {})
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub("get_compensation_policy")


async def apply_reservation_discount(
    reservation_id: str,
    discount_pct: float,
    reason: str,
    approval_id: str,
) -> dict:
    if not approval_id:
        raise ValueError("approval_id required for apply_reservation_discount")
    mcp = await _facilrentacar_mcp_call(
        "apply_reservation_discount",
        {
            "reservation_id": reservation_id,
            "discount_pct": discount_pct,
            "reason": reason,
            "approval_id": approval_id,
        },
    )
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub(
        "apply_reservation_discount",
        reservation_id=reservation_id,
        discount_pct=discount_pct,
        reason=reason,
        approval_id=approval_id,
    )


async def get_client_history(client_id: str) -> dict:
    mcp = await _facilrentacar_mcp_call("get_client_history", {"client_id": client_id})
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub("get_client_history", client_id=client_id)


async def get_cancellation_policy() -> dict:
    mcp = await _facilrentacar_mcp_call("get_cancellation_policy", {})
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub("get_cancellation_policy")


async def execute_cancellation_override(
    client_id: str,
    reservation_ids: list[str],
    override_type: str,
    override_reason: str,
    approval_id: str,
) -> dict:
    if not approval_id:
        raise ValueError("approval_id required for execute_cancellation_override")
    mcp = await _facilrentacar_mcp_call(
        "execute_cancellation_override",
        {
            "client_id": client_id,
            "reservation_ids": reservation_ids,
            "override_type": override_type,
            "override_reason": override_reason,
            "approval_id": approval_id,
        },
    )
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub(
        "execute_cancellation_override",
        client_id=client_id,
        reservation_ids=reservation_ids,
        override_type=override_type,
        override_reason=override_reason,
        approval_id=approval_id,
    )


async def get_fleet_occupancy(period_start: str, period_end: str) -> dict:
    mcp = await _facilrentacar_mcp_call(
        "get_fleet_occupancy",
        {"period_start": period_start, "period_end": period_end},
    )
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub("get_fleet_occupancy", period_start=period_start, period_end=period_end)


async def get_current_rates(categories: list[str]) -> dict:
    mcp = await _facilrentacar_mcp_call("get_current_rates", {"categories": categories})
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub("get_current_rates", categories=categories)


async def get_market_rates(categories: list[str]) -> dict:
    mcp = await _facilrentacar_mcp_call("get_market_rates", {"categories": categories})
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub("get_market_rates", categories=categories)


async def publish_rate_adjustment(
    categories: list[str],
    new_rate_ars_per_day: float,
    valid_from: str,
    valid_to: str,
    adjustment_reason: str,
    approval_id: str,
) -> dict:
    if not approval_id:
        raise ValueError("approval_id required for publish_rate_adjustment")
    mcp = await _facilrentacar_mcp_call(
        "publish_rate_adjustment",
        {
            "categories": categories,
            "new_rate_ars_per_day": new_rate_ars_per_day,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "adjustment_reason": adjustment_reason,
            "approval_id": approval_id,
        },
    )
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub(
        "publish_rate_adjustment",
        categories=categories,
        new_rate_ars_per_day=new_rate_ars_per_day,
        valid_from=valid_from,
        valid_to=valid_to,
        adjustment_reason=adjustment_reason,
        approval_id=approval_id,
    )


async def get_branch_status(branch_name: str) -> dict:
    mcp = await _facilrentacar_mcp_call("get_branch_status", {"branch_name": branch_name})
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub("get_branch_status", branch=branch_name)


async def get_pending_reservations_by_branch(branch_name: str) -> dict:
    mcp = await _facilrentacar_mcp_call(
        "get_pending_reservations_by_branch",
        {"branch_name": branch_name},
    )
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub("get_pending_reservations_by_branch", branch=branch_name)


async def activate_vehicles(
    vehicle_ids: list[str],
    activation_notes: str,
    approval_id: str,
) -> dict:
    if not approval_id:
        raise ValueError("approval_id required for activate_vehicles")
    mcp = await _facilrentacar_mcp_call(
        "activate_vehicles",
        {
            "vehicle_ids": vehicle_ids,
            "activation_notes": activation_notes,
            "approval_id": approval_id,
        },
    )
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub(
        "activate_vehicles",
        vehicle_ids=vehicle_ids,
        activation_notes=activation_notes,
        approval_id=approval_id,
    )


async def launch_linkedin_campaign(
    campaign_name: str,
    target_segment: str,
    budget_ars: float,
    approval_id: str,
) -> dict:
    if not approval_id:
        raise ValueError("approval_id required for launch_linkedin_campaign")
    mcp = await _facilrentacar_mcp_call(
        "launch_linkedin_campaign",
        {
            "campaign_name": campaign_name,
            "target_segment": target_segment,
            "budget_ars": budget_ars,
            "approval_id": approval_id,
        },
    )
    if mcp:
        return {"source": "facilrentacar_mcp", **mcp}
    return _stub(
        "launch_linkedin_campaign",
        campaign_name=campaign_name,
        target_segment=target_segment,
        budget_ars=budget_ars,
        approval_id=approval_id,
    )
