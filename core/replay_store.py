"""In-memory replay snapshot store for tests and fallback."""

_replay_store: dict[str, list[dict]] = {}


def save_replay_snapshot_memory(session_id: str, step: int, data: dict) -> None:
    _replay_store.setdefault(session_id, [])
    while len(_replay_store[session_id]) <= step:
        _replay_store[session_id].append({})
    _replay_store[session_id][step] = data


def get_replay_snapshots_memory(session_id: str) -> list[dict]:
    return _replay_store.get(session_id, [])


def reset_replay_store() -> None:
    _replay_store.clear()
