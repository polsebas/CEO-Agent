import pytest

from core.cache import reset_cache
from core.config import settings
from core.runtime_session import reset_memory_session_locks


@pytest.fixture(autouse=True)
def in_memory_store(monkeypatch):
    monkeypatch.setattr(settings, "use_in_memory_store", True)
    monkeypatch.setattr(settings, "auth_disabled", True)
    from core.persistence import reset_in_memory_store
    from core.replay_store import reset_replay_store

    reset_in_memory_store()
    reset_replay_store()
    reset_memory_session_locks()
    reset_cache()
    yield
    reset_in_memory_store()
    reset_replay_store()
    reset_memory_session_locks()
    reset_cache()


def pytest_configure(config):
    config.addinivalue_line("markers", "postgres: integration tests requiring Postgres")
