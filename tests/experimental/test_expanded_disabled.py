import pytest

from core.agent_registry import AgentDisabledError
from experimental.agents.expanded import delegate_to_cfo
from schemas.messages import AgentMessage, AgentRole, MessageIntent
from uuid import uuid4


@pytest.mark.asyncio
async def test_expanded_cfo_disabled():
    msg = AgentMessage(
        id=str(uuid4()),
        sender=AgentRole.CEO,
        receiver=AgentRole.CFO,
        intent=MessageIntent.DELEGATION,
        payload={"objective": "test"},
        correlation_id=str(uuid4()),
    )
    with pytest.raises(AgentDisabledError):
        await delegate_to_cfo(msg, str(uuid4()))
