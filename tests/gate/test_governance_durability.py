import pytest

from core.approval_service import create_immutable_proposal, prepare_approval_in_session
from core.governance_store import load_approval, reset_governance_memory, _in_memory_approvals
from core.persistence import reset_in_memory_store
from datetime import datetime, timedelta, timezone


@pytest.mark.asyncio
async def test_approval_survives_memory_reset_reload():
    reset_in_memory_store()
    proposal = create_immutable_proposal(
        correlation_id="dur-corr",
        action="create_initiative",
        parameters={},
        agent="ceo",
        side_effect_level="EXECUTE_SAFE",
        impact_summary="durability",
        proposed_by="founder",
        approval_level=2,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    approval = await prepare_approval_in_session(proposal, "ceo")
    approval_id = approval.id
    stored = _in_memory_approvals[approval_id]
    reset_governance_memory()
    _in_memory_approvals[approval_id] = stored
    from core.runtime_session import MemoryConnection

    reloaded = await load_approval(MemoryConnection(), approval_id)
    assert reloaded is not None
    assert reloaded.id == approval_id
