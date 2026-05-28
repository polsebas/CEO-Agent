"""RRM-3D — session stabilization gates."""

from __future__ import annotations

import pytest

from core.cognition_loops import detect_delegation_loop, detect_tool_cycle
from core.retry_storms import is_retry_storm, retry_density
from core.session_stability import session_stability_service
from schemas.cognition import CognitiveTelemetry


@pytest.mark.rrm3
def test_delegation_loop_detected():
    assert detect_delegation_loop(["cto", "cto", "cto"]) is True
    assert detect_delegation_loop(["cto", "ceo"]) is False


@pytest.mark.rrm3
def test_tool_cycle_detected():
    tools = ["a", "b", "c", "d", "a", "b", "c", "d"]
    assert detect_tool_cycle(tools) is True


@pytest.mark.rrm3
def test_retry_storm_mitigation():
    tel = [
        CognitiveTelemetry(
            correlation_id="c",
            session_id="s",
            agent_id="ceo",
            retry_count=5,
        )
        for _ in range(3)
    ]
    density = retry_density(tel)
    assert is_retry_storm(density)
    assessment = session_stability_service.assess_at_boundary(
        session_id="s",
        correlation_id="c",
        telemetry=tel,
        tool_names=[],
        delegations=[],
    )
    assert assessment.policy_recompute_required
    assert any(e.event_type == "retry_storm" for e in assessment.events)


@pytest.mark.rrm3
def test_stability_assessment_reproducible():
    tel = [
        CognitiveTelemetry(
            correlation_id="c",
            session_id="s",
            agent_id="ceo",
            retry_count=1,
        )
    ]
    a = session_stability_service.assess_at_boundary(
        session_id="s",
        correlation_id="c",
        telemetry=tel,
        tool_names=["t1"],
        delegations=["cto"],
    )
    b = session_stability_service.assess_at_boundary(
        session_id="s",
        correlation_id="c",
        telemetry=tel,
        tool_names=["t1"],
        delegations=["cto"],
    )
    assert a.stability_score == b.stability_score
