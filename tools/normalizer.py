"""Tool result normalizer — all tools return ToolResult."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from schemas.tools import ToolResult


async def normalize_tool_call(
    tool_name: str,
    correlation_id: str,
    source: str,
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> ToolResult:
    start = time.perf_counter()
    try:
        result = await fn(*args, **kwargs)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if isinstance(result, ToolResult):
            result.latency_ms = latency_ms
            result.correlation_id = correlation_id
            return result
        data = result if isinstance(result, dict) else {"result": result}
        return ToolResult(
            success=True,
            data=data,
            source=source,
            latency_ms=latency_ms,
            tool_name=tool_name,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ToolResult(
            success=False,
            data=None,
            errors=[str(exc)],
            source=source,
            latency_ms=latency_ms,
            tool_name=tool_name,
            correlation_id=correlation_id,
        )
