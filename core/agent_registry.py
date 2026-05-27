"""Runtime agent availability — production boundary CEO+CTO only."""

from __future__ import annotations

from enum import Enum


class AgentAvailability(str, Enum):
    ACTIVE = "active"
    EXPERIMENTAL = "experimental"
    DISABLED = "disabled"


AGENT_RUNTIME_STATUS: dict[str, AgentAvailability] = {
    "ceo": AgentAvailability.ACTIVE,
    "cto": AgentAvailability.ACTIVE,
    "cfo": AgentAvailability.DISABLED,
    "coo": AgentAvailability.DISABLED,
    "cmo": AgentAvailability.DISABLED,
}


class AgentDisabledError(Exception):
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} is disabled in production runtime")


def assert_agent_active(agent_id: str) -> None:
    status = AGENT_RUNTIME_STATUS.get(agent_id, AgentAvailability.DISABLED)
    if status != AgentAvailability.ACTIVE:
        raise AgentDisabledError(agent_id)


def is_agent_active(agent_id: str) -> bool:
    return AGENT_RUNTIME_STATUS.get(agent_id) == AgentAvailability.ACTIVE
