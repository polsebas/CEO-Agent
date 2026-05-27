from schemas.crisis import CRISIS_OVERRIDES, CrisisType
from schemas.world import Company, Incident, WorldState
from core.policy import policy_engine


def test_crisis_detection_infrastructure():
    world = WorldState(
        company=Company(
            id="c1",
            name="TestCo",
            mrr_usd=10000,
            churn_rate=0.05,
            burn_rate_usd=50000,
            runway_months=12,
        ),
        active_incidents=[
            Incident(id="1", title="Outage", severity="critical", status="open", service="api"),
        ],
    )
    crisis = policy_engine.detect_crisis(world)
    assert crisis == CrisisType.INFRASTRUCTURE
    assert crisis in CRISIS_OVERRIDES
