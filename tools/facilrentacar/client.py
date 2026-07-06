"""FacilRentaCar MCP client with stub fallback."""

from __future__ import annotations

import httpx

from core.config import settings
from core.mcp_security import MCPValidationError, validate_mcp_response, validate_mcp_url
from tools.stubs import facilrentacar_contracts as contracts


async def _facilrentacar_mcp_call(method: str, params: dict) -> dict | None:
    try:
        validate_mcp_url(settings.facilrentacar_mcp_url)
    except MCPValidationError:
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.mcp_timeout_seconds) as client:
            response = await client.post(
                f"{settings.facilrentacar_mcp_url}/tools/{method}",
                json=params,
            )
            if response.status_code == 200:
                payload = response.json()
                return validate_mcp_response(payload)
    except Exception:
        return None
    return None


def _stub(tool_name: str, **kwargs) -> dict:
    base = dict(contracts.CONTRACT_BY_TOOL.get(tool_name, {}))
    base.update(kwargs)
    base["source"] = "stub"
    return base
