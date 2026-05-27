import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Company(BaseModel):
    id: str
    name: str
    mrr_usd: float
    churn_rate: float
    burn_rate_usd: float
    runway_months: float


class Incident(BaseModel):
    id: str
    title: str
    severity: Literal["low", "medium", "high", "critical"]
    status: Literal["open", "investigating", "resolved"]
    service: str


class Deployment(BaseModel):
    id: str
    service: str
    version: str
    status: Literal["healthy", "degraded", "failed"]
    deployed_at: datetime


class WorldState(BaseModel):
    version: int = 1
    company: Company
    active_incidents: list[Incident] = Field(default_factory=list)
    active_deployments: list[Deployment] = Field(default_factory=list)


class WorldStateSnapshot(BaseModel):
    version: int
    timestamp: datetime
    changed_entities: list[str]
    checksum: str
    state: WorldState

    @classmethod
    def from_state(cls, state: WorldState, changed_entities: list[str] | None = None) -> "WorldStateSnapshot":
        payload = state.model_dump(mode="json")
        checksum = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return cls(
            version=state.version,
            timestamp=datetime.now(timezone.utc),
            changed_entities=changed_entities or [],
            checksum=checksum,
            state=state,
        )


def default_world_state() -> WorldState:
    return WorldState(
        version=1,
        company=Company(
            id="company-1",
            name="Demo SaaS",
            mrr_usd=45000.0,
            churn_rate=0.032,
            burn_rate_usd=82000.0,
            runway_months=14.0,
        ),
        active_incidents=[
            Incident(
                id="inc-1",
                title="Deployment latency spike",
                severity="high",
                status="investigating",
                service="api-gateway",
            )
        ],
        active_deployments=[
            Deployment(
                id="dep-1",
                service="api-gateway",
                version="v2.4.1",
                status="degraded",
                deployed_at=datetime.now(timezone.utc),
            )
        ],
    )
