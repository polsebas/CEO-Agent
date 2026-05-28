"""Postgres integration — adaptive policy persistence."""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"),
        reason="DATABASE_URL required",
    ),
]


@pytest.mark.asyncio
async def test_adaptive_policy_table_exists():
    from core.persistence import ensure_schema, get_pool

    pool = await get_pool()
    assert pool is not None
    await ensure_schema(pool)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'adaptive_policies'
            """
        )
        assert row is not None


@pytest.mark.asyncio
async def test_tool_reliability_table_exists():
    from core.persistence import ensure_schema, get_pool

    pool = await get_pool()
    await ensure_schema(pool)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'tool_reliability_profiles'
            """
        )
        assert row is not None
