"""Session isolation — Postgres advisory locks with in-process fallback."""

from __future__ import annotations

from contextlib import asynccontextmanager

from core.persistence import get_pool

_in_process_locks: set[str] = set()


class SessionLockError(Exception):
    pass


@asynccontextmanager
async def session_lock(session_id: str):
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", session_id)
                yield
        return

    if session_id in _in_process_locks:
        raise SessionLockError(f"Session {session_id} already locked")
    _in_process_locks.add(session_id)
    try:
        yield
    finally:
        _in_process_locks.discard(session_id)


def reset_session_locks() -> None:
    _in_process_locks.clear()
