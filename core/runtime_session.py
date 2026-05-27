"""Single transactional boundary for mutative runtime requests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from core.persistence import get_pool

T = TypeVar("T")


class MemoryConnection:
    """Marker connection for in-memory test / dev store (no asyncpg)."""


# Process-local session locks for in-memory mode (simulates pg_advisory_xact_lock)
_memory_session_locks: set[str] = set()


class SessionLockError(Exception):
    pass


async def acquire_session_lock(conn: Any, session_id: str) -> None:
    """Acquire advisory lock on the same connection used for persistence."""
    if isinstance(conn, MemoryConnection):
        if session_id in _memory_session_locks:
            raise SessionLockError(f"Session {session_id} already locked")
        _memory_session_locks.add(session_id)
        return
    await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", session_id)


def release_memory_session_lock(session_id: str) -> None:
    _memory_session_locks.discard(session_id)


@asynccontextmanager
async def mutative_session(session_id: str) -> AsyncIterator[Any]:
    """
    One transaction + one advisory lock + one connection for the full mutative request.
    Yields conn (asyncpg.Connection or MemoryConnection).
    """
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await acquire_session_lock(conn, session_id)
                yield conn
        return

    if session_id in _memory_session_locks:
        raise SessionLockError(f"Session {session_id} already locked")
    _memory_session_locks.add(session_id)
    try:
        yield MemoryConnection()
    finally:
        _memory_session_locks.discard(session_id)


async def run_mutative_session(
    session_id: str,
    fn: Callable[[Any], Awaitable[T]],
) -> T:
    async with mutative_session(session_id) as conn:
        return await fn(conn)


def reset_memory_session_locks() -> None:
    _memory_session_locks.clear()
