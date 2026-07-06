"""Deterministic tool router for FacilRentaCar gate tests."""

from __future__ import annotations

from tools.stubs import facilrentacar_contracts as contracts
from schemas.tools import ToolResult


class FakeToolRouter:
    def __init__(self, responses: dict[str, dict] | None = None) -> None:
        self.responses = responses or dict(contracts.CONTRACT_BY_TOOL)

    async def execute_tool(
        self,
        tool_name: str,
        agent_id: str,
        correlation_id: str,
        params: dict | None = None,
        **kwargs,
    ) -> ToolResult:
        if tool_name not in self.responses:
            return ToolResult(
                success=False,
                errors=[f"Unknown fake tool: {tool_name}"],
                source="fake",
                latency_ms=0,
                tool_name=tool_name,
                correlation_id=correlation_id,
            )
        data = dict(self.responses[tool_name])
        if params:
            data.update(params)
        data["source"] = "fake"
        return ToolResult(
            success=True,
            data=data,
            source="fake",
            latency_ms=1,
            tool_name=tool_name,
            correlation_id=correlation_id,
        )
