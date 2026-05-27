"""In-memory replay snapshot store for tests and fallback."""

_replay_store: dict[str, list[dict]] = {}
_baseline_fingerprints: dict[str, str] = {}
_baseline_records: dict[str, dict] = {}


def save_baseline_record_memory(
    session_id: str,
    correlation_id: str,
    fingerprint: str,
    orchestrator_version: str,
) -> None:
    _baseline_fingerprints[session_id] = fingerprint
    _baseline_records[session_id] = {
        "correlation_id": correlation_id,
        "outcome_fingerprint": fingerprint,
        "orchestrator_version": orchestrator_version,
    }


def save_baseline_fingerprint_memory(session_id: str, correlation_id: str, fingerprint: str) -> None:
    save_baseline_record_memory(session_id, correlation_id, fingerprint, "rrm15-legacy")


def get_baseline_fingerprint_memory(session_id: str) -> str | None:
    return _baseline_fingerprints.get(session_id)


def get_baseline_record_memory(session_id: str) -> dict | None:
    return _baseline_records.get(session_id)


def save_replay_snapshot_memory(session_id: str, step: int, data: dict) -> None:
    _replay_store.setdefault(session_id, [])
    while len(_replay_store[session_id]) <= step:
        _replay_store[session_id].append({})
    _replay_store[session_id][step] = data


def get_replay_snapshots_memory(session_id: str) -> list[dict]:
    return _replay_store.get(session_id, [])


def reset_replay_store() -> None:
    _replay_store.clear()
    _baseline_fingerprints.clear()
    _baseline_records.clear()
