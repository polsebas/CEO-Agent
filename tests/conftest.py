import pytest

from core.cache import reset_cache
from core.config import settings


@pytest.fixture(autouse=True)
def in_memory_store(monkeypatch):
    monkeypatch.setattr(settings, "use_in_memory_store", True)
    monkeypatch.setattr(settings, "auth_disabled", True)
    from core.persistence import reset_in_memory_store
    from core.replay_store import reset_replay_store

    reset_in_memory_store()
    reset_replay_store()
    reset_cache()
    yield
    reset_in_memory_store()
    reset_replay_store()
    reset_cache()
