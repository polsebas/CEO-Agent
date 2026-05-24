"""Retry policy engine for tool calls."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from schemas.runtime import RetryPolicy
from schemas.tools import ToolResult

T = TypeVar("T")


async def with_retry(
    fn: Callable[[], Awaitable[ToolResult]],
    policy: RetryPolicy | None = None,
) -> ToolResult:
    policy = policy or RetryPolicy()
    last: ToolResult | None = None
    for attempt in range(policy.max_retries + 1):
        result = await fn()
        last = result
        if result.success:
            return result
        retryable = any(err in str(result.errors) for err in policy.retry_on for err in result.errors)
        if not retryable and attempt >= policy.max_retries:
            break
        if attempt < policy.max_retries:
            await asyncio.sleep(policy.retry_backoff_ms / 1000)
    return last or ToolResult(
        success=False,
        errors=["Retry exhausted"],
        source="retry",
        latency_ms=0,
        tool_name="unknown",
        correlation_id="",
    )
