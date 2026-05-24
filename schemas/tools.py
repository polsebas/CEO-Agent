from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool
    data: dict | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: str
    latency_ms: int
    cached: bool = False
    tool_name: str
    correlation_id: str
