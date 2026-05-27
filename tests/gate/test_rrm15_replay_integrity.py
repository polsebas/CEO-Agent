"""RRM-1.5 Replay Integrity gate — contract tests for SPEC-RRM1.5.

Tests marked ``skip`` are the acceptance checklist until FrozenReplayExecutor
and related milestones land. Structural tests run in CI today.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store
from core.replay import replay_engine
from core.replay_validator import prompt_hash, reorchestrate_frozen_outcome, validate_frozen_replay
from core.replay_store import get_baseline_fingerprint_memory
from schemas.runtime import ReplayMode

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- RRM15-M7 / AC-M7: mutative entrypoints audit (passes today) ---


@pytest.mark.rrm15
def test_founder_request_enters_run_mutative_session():
    src = (REPO_ROOT / "core" / "orchestrator.py").read_text(encoding="utf-8")
    assert "async def run_founder_request" in src
    idx = src.index("async def run_founder_request")
    block = src[idx : idx + 2500]
    assert "run_mutative_session" in block


@pytest.mark.rrm15
def test_approval_service_enters_run_mutative_session():
    src = (REPO_ROOT / "core" / "approval_service.py").read_text(encoding="utf-8")
    assert "run_mutative_session" in src


@pytest.mark.rrm15
def test_experimental_expanded_enters_run_mutative_session():
    src = (REPO_ROOT / "experimental" / "agents" / "expanded.py").read_text(encoding="utf-8")
    assert "run_mutative_session" in src


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_reorchestrate_frozen_does_not_invoke_orchestrator():
    reset_in_memory_store()
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id="iso-session",
        correlation_id="iso-corr",
    )
    with patch.object(manual_orchestrator, "run_founder_request", new_callable=AsyncMock) as mock_run:
        with patch.object(manual_orchestrator, "_run_locked", new_callable=AsyncMock) as mock_locked:
            await reorchestrate_frozen_outcome("iso-session", "iso-corr")
    mock_run.assert_not_called()
    mock_locked.assert_not_called()


# --- RRM15-M5 / AC-M5: outbox contract (structural, passes today) ---


@pytest.mark.rrm15
def test_outbox_batch_uses_skip_locked_and_process_after_handler():
    src = (REPO_ROOT / "workers" / "outbox_processor.py").read_text(encoding="utf-8")
    assert "FOR UPDATE SKIP LOCKED" in src
    assert "if not await _handle_event(event)" in src
    assert "processed = TRUE" in src
    handler_idx = src.index("if not await _handle_event")
    mark_idx = src.index("processed = TRUE")
    assert handler_idx < mark_idx


# --- Baseline persistence regression (passes today) ---


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_baseline_fingerprint_stored_on_session_complete():
    reset_in_memory_store()
    session_id = "rrm15-baseline"
    correlation_id = "rrm15-baseline-corr"
    result = await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    assert "error" not in result
    baseline = get_baseline_fingerprint_memory(session_id)
    assert baseline is not None
    assert len(baseline) == 64


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_validate_frozen_replay_matches_persisted_baseline():
    reset_in_memory_store()
    session_id = "rrm15-validate"
    correlation_id = "rrm15-validate-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    ok, fp, baseline = await validate_frozen_replay(session_id, correlation_id)
    assert baseline is not None
    assert ok is True
    assert fp == baseline


# --- RRM15 gap detector: orchestrator code change invisible to frozen replay (today) ---


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_frozen_replay_ignores_orchestrator_logic_without_executor():
    """Documents SPEC gap: validate_frozen_replay does not re-run ManualOrchestrator.

    Replace with ``test_orchestrator_logic_change_breaks_frozen_replay`` (skip M1) once
    FrozenReplayExecutor replays transitions from the bundle.
    """
    reset_in_memory_store()
    session_id = "rrm15-gap"
    correlation_id = "rrm15-gap-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )

    async def _broken_orchestrator(*_a, **_k):
        raise RuntimeError("orchestrator must not run during frozen replay")

    with patch.object(manual_orchestrator, "_run_locked", side_effect=_broken_orchestrator):
        ok, _, baseline = await validate_frozen_replay(session_id, correlation_id)
    assert ok is True
    assert baseline is not None


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_orchestrator_logic_change_breaks_frozen_replay():
    reset_in_memory_store()
    session_id = "rrm15-version"
    correlation_id = "rrm15-version-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    from core.frozen_replay_executor import frozen_replay_executor

    with patch.object(frozen_replay_executor, "ORCHESTRATOR_VERSION", "rrm15-9.9.9"):
        ok, _, baseline = await validate_frozen_replay(session_id, correlation_id)
    assert baseline is not None
    assert ok is False


# --- RRM15-M1: FrozenReplayExecutor ---


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_frozen_executor_matches_baseline_without_reorchestrate_shortcut():
    from core.frozen_replay_executor import frozen_replay_executor
    from schemas.replay import outcome_fingerprint

    reset_in_memory_store()
    session_id = "rrm15-exec"
    correlation_id = "rrm15-exec-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    baseline = get_baseline_fingerprint_memory(session_id)
    outcome = await frozen_replay_executor.run_from_session(session_id, correlation_id)
    assert outcome_fingerprint(outcome) == baseline


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_frozen_executor_step_transitions_match_persisted_history():
    from core import persistence
    from core.frozen_replay_executor import frozen_replay_executor
    from core.replay_errors import ReplayIntegrityError

    reset_in_memory_store()
    session_id = "rrm15-trans"
    correlation_id = "rrm15-trans-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    assert persistence._in_memory_runtime_transitions
    persistence._in_memory_runtime_transitions[0]["from_state"] = "invalid_state"
    with pytest.raises(ReplayIntegrityError):
        await frozen_replay_executor.run_from_session(session_id, correlation_id)


# --- RRM15-M2: Live replay adapter ---


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_live_replay_detects_tool_output_drift_without_snapshot_mutator():
    import copy
    from unittest.mock import patch

    from core.live_replay_adapter import LiveToolReplayAdapter
    from core.replay_store import get_replay_snapshots_memory
    from schemas.runtime import ReplayMode
    from tools.router import execute_tool

    reset_in_memory_store()
    session_id = "rrm15-live-drift"
    correlation_id = "rrm15-live-drift-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    before = copy.deepcopy(get_replay_snapshots_memory(session_id))
    original = execute_tool

    async def drifted(tool_name, agent_id, corr, params=None):
        r = await original(tool_name, agent_id, corr, params)
        return r.model_copy(update={"tool_name": "mutated_tool"})

    adapter = LiveToolReplayAdapter(tool_executor=drifted)
    with patch("core.replay.live_replay_adapter", adapter):
        session = await replay_engine.replay_session(
            session_id, correlation_id, ReplayMode.LIVE
        )
    assert session.outcome_match is False
    assert "tool_sequence" in (session.world_state_snapshot.get("drift_fields") or [])
    assert get_replay_snapshots_memory(session_id) == before


# --- RRM15-M3: RuntimeState canonicalization (skipped) ---


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_final_runtime_state_from_state_machine():
    reset_in_memory_store()
    session_id = "rrm15-sm"
    correlation_id = "rrm15-sm-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    outcome = await reorchestrate_frozen_outcome(session_id, correlation_id)
    assert outcome.final_runtime_state == "completed"


# --- RRM15-M6: prompt_hash full sha256 ---


@pytest.mark.rrm15
def test_prompt_hash_is_full_sha256():
    h = prompt_hash("deterministic prompt material")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# --- RRM15-M1c: regression — ten frozen replays stable (passes today via rebuild) ---


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_frozen_replay_stable_ten_iterations_until_executor_lands():
    """Keeps RRM1 regression; still valid when executor is replay-faithful."""
    reset_in_memory_store()
    session_id = "rrm15-ten"
    correlation_id = "rrm15-ten-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    fingerprints = []
    for _ in range(10):
        session = await replay_engine.replay_session(session_id, correlation_id, ReplayMode.FROZEN)
        assert session.outcome_match is True
        fingerprints.append(session.world_state_snapshot.get("outcome_fingerprint"))
    assert len(set(fingerprints)) == 1


# M4 → tests/integration/test_postgres_replay.py
# M5 → tests/gate/test_outbox_semantics.py + tests/integration/test_postgres_outbox.py
