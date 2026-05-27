"""Postgres integration — requires DATABASE_URL and USE_IN_MEMORY_STORE=false."""

import asyncio
import os

import pytest

from core.config import settings
from core.orchestrator import manual_orchestrator
from core.persistence import get_pool, reset_in_memory_store
from core.runtime_session import SessionLockError


@pytest.fixture
def postgres_settings(monkeypatch):
    monkeypatch.setattr(settings, "use_in_memory_store", False)
    monkeypatch.setattr(settings, "database_url", os.environ.get(
        "DATABASE_URL", "postgresql://ceo:ceo@localhost:5432/ceo_agent"
    ))
    reset_in_memory_store()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_founder_request(postgres_settings):
    import asyncpg

    try:
        await asyncpg.connect(settings.database_url, timeout=2)
    except Exception:
        pytest.skip("Postgres not available")
    result = await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id="pg-session-1",
        correlation_id="pg-corr-1",
    )
    assert "error" not in result
    pool = await get_pool()
    assert pool is not None


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_same_session_contention(postgres_settings):
    import asyncpg

    try:
        await asyncpg.connect(settings.database_url, timeout=2)
    except Exception:
        pytest.skip("Postgres not available")
    session_id = "pg-contention"
    results = await asyncio.gather(
        manual_orchestrator.run_founder_request(
            "A",
            session_id=session_id,
            correlation_id="pg-corr-a",
        ),
        manual_orchestrator.run_founder_request(
            "B",
            session_id=session_id,
            correlation_id="pg-corr-b",
        ),
        return_exceptions=True,
    )
    lock_errors = sum(
        1 for r in results if isinstance(r, dict) and "Concurrent write" in r.get("error", "")
    )
    successes = sum(
        1 for r in results if isinstance(r, dict) and r.get("correlation_id") and not r.get("error")
    )
    assert lock_errors >= 1
    assert successes >= 1
