"""Shared pytest fixtures for FacilRentaCar scenario tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from schemas.responses import CEOResponse, CFOResponse, COOResponse, CancellationOption
from tests.fixtures.fake_tool_router import FakeToolRouter


@pytest.fixture
def fake_tool_router():
    router = FakeToolRouter()
    with patch("tools.router.execute_tool", new=AsyncMock(side_effect=router.execute_tool)):
        with patch("core.facilrentacar_handlers.execute_tool", new=AsyncMock(side_effect=router.execute_tool)):
            yield router


@pytest.fixture
def mock_compensation_agents():
    cfo = CFOResponse(
        summary="Compensación recomendada por incidencia menor",
        recommended_action="apply_discount",
        discount_pct=0.12,
        discount_amount_ars=22200.0,
        justification="Incidencia menor con 3 días restantes",
        confidence=0.88,
    )
    ceo = CEOResponse(
        summary="Elevar descuento 12% a approval del founder",
        recommended_actions=["apply_reservation_discount"],
    )
    return cfo, ceo


@pytest.fixture
def mock_reactivation_agents():
    coo = COOResponse(
        summary="Priorizar Mendoza Centro por reservas pendientes",
        vehicles_to_activate_now=["VEH-205", "VEH-206"],
        vehicles_to_hold=["VEH-401"],
        hold_reason="Staff limitado Malargüe",
        operational_notes="Activar Pickups en Mendoza Centro primero",
        confidence=0.9,
    )
    ceo = CEOResponse(summary="Aprobar reactivación parcial de flota")
    return coo, ceo


@pytest.fixture
def mock_occupancy_agents():
    coo = COOResponse(
        summary="Escasez crítica SUV/Pickup",
        recommended_action="rate_adjustment",
        operational_risk="high",
    )
    cfo = CFOResponse(
        summary="Rango tarifario recomendado",
        min_rate=30800.0,
        max_rate=35000.0,
        recommended_rate=32200.0,
        revenue_uplift_ars=84000.0,
    )
    ceo = CEOResponse(summary="Publicar ajuste tarifario moderado", approved_rate=32200.0)
    return coo, cfo, ceo


@pytest.fixture
def mock_cancellation_agents():
    options = [
        CancellationOption(
            option_id="full_refund",
            description="Reembolso completo",
            financial_impact_ars=625000.0,
            client_relationship_impact="positive",
            recommendation_score=0.85,
        ),
        CancellationOption(
            option_id="apply_penalty",
            description="Penalidad contractual",
            financial_impact_ars=187500.0,
            client_relationship_impact="negative",
            recommendation_score=0.35,
        ),
    ]
    cfo = CFOResponse(summary="Cliente corporativo de alto valor")
    ceo = CEOResponse(
        summary="Recomendar reembolso completo por LTV",
        recommended_option="full_refund",
        cancellation_options=options,
        client_ltv_estimate_ars=3786666.0,
        reasoning="LTV supera 10x penalidad",
    )
    return cfo, ceo


def patch_agent_runner_responses(*responses):
    async def _run(agent, prompt, response_model, correlation_id, **kwargs):
        for resp in responses:
            if isinstance(resp, response_model):
                from schemas.cognition import CognitiveTelemetry, StructuredRetryTrace
                from datetime import datetime, timezone

                trace = StructuredRetryTrace(
                    correlation_id=correlation_id,
                    session_id=kwargs.get("session_id", correlation_id),
                    agent_id=kwargs.get("agent_id", "ceo"),
                    step_id=kwargs.get("step_id", 0),
                    created_at=datetime.now(timezone.utc),
                )
                tel = CognitiveTelemetry(
                    correlation_id=correlation_id,
                    session_id=kwargs.get("session_id", correlation_id),
                    agent_id=kwargs.get("agent_id", "ceo"),
                )
                return resp, trace, tel
        raise ValueError(f"No mock for {response_model}")

    return patch("core.facilrentacar_handlers.structured_agent_runner.run", new=AsyncMock(side_effect=_run))
