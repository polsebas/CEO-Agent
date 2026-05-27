"""Shared fixtures for Postgres integration tests."""

from __future__ import annotations

import os

import pytest

from core.config import settings
from core.persistence import reset_in_memory_store


@pytest.fixture
def postgres_settings(monkeypatch):
    monkeypatch.setattr(settings, "use_in_memory_store", False)
    monkeypatch.setattr(
        settings,
        "database_url",
        os.environ.get("DATABASE_URL", "postgresql://ceo:ceo@localhost:5432/ceo_agent"),
    )
    reset_in_memory_store()
    yield
    reset_in_memory_store()


@pytest.fixture
def postgres_available(postgres_settings):
    import asyncio

    import asyncpg

    async def probe() -> None:
        conn = await asyncpg.connect(settings.database_url, timeout=2)
        await conn.close()

    try:
        asyncio.run(probe())
    except Exception:
        pytest.skip("Postgres not available")
