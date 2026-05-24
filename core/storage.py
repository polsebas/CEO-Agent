"""PgAgentStorage wrapper with pooling."""

from __future__ import annotations

from core.config import settings

_storage = None


def get_agent_storage():
    global _storage
    if _storage is not None:
        return _storage
    if settings.use_in_memory_store:
        return None
    try:
        from agno.storage.postgres import PostgresStorage

        _storage = PostgresStorage(
            db_url=settings.database_url,
            table_name="agent_sessions",
        )
        _storage.create()
        return _storage
    except Exception:
        return None
