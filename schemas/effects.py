from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SideEffectRecord(BaseModel):
    id: str
    action_id: str
    correlation_id: str
    systems_affected: list[str]
    mutation_status: Literal["pending", "partial", "complete", "failed"]
    rollback_available: bool
    rollback_executed: bool = False
    rollback_strategy: str | None = None
    created_at: datetime
