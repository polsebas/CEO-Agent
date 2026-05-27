import asyncio

import pytest

from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store
from core.runtime_session import SessionLockError


@pytest.mark.asyncio
async def test_same_session_id_one_wins_one_lock_error():
    reset_in_memory_store()
    session_id = "contention-session"
    results = await asyncio.gather(
        manual_orchestrator.run_founder_request(
            "message A",
            session_id=session_id,
            correlation_id="corr-a",
        ),
        manual_orchestrator.run_founder_request(
            "message B",
            session_id=session_id,
            correlation_id="corr-b",
        ),
        return_exceptions=True,
    )
    errors = [r for r in results if isinstance(r, dict) and r.get("error")]
    lock_errors = [r for r in errors if "Concurrent write" in r.get("error", "")]
    successes = [r for r in results if isinstance(r, dict) and "correlation_id" in r and not r.get("error")]
    assert len(lock_errors) == 1
    assert len(successes) == 1
