"""RRM-3 replay-aware runtime governance events."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GovernanceAction(str, Enum):
    ESCALATE_APPROVAL = "escalate_approval"
    DISABLE_DELEGATION = "disable_delegation"
    FORCE_DETERMINISTIC = "force_deterministic"
    REPLAY_DRIFT_DETECTED = "replay_drift_detected"


class AdaptiveGovernanceEvent(BaseModel):
    session_id: str
    correlation_id: str
    action: GovernanceAction
    approval_bias_delta: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
