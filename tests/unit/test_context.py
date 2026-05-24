import asyncio

import pytest

from core.context import ContextWindowManager
from core.persistence import reset_in_memory_store
from core.runtime import RuntimeStateMachine
from schemas.runtime import CognitiveBudget, RuntimeState
from schemas.world import default_world_state


def test_context_within_budget():
    mgr = ContextWindowManager(max_tokens=8000)
    bundle = mgr.build_context(
        "s1", "t1", active_task="Analyze incident", world_state=default_world_state()
    )
    assert mgr.within_budget(bundle, CognitiveBudget().memory_budget)


def test_context_l1_l2_always_present():
    mgr = ContextWindowManager()
    bundle = mgr.build_context("s1", "t1", active_task="task", world_state=default_world_state())
    from schemas.runtime import ContextLayer

    assert ContextLayer.L1_ACTIVE_TASK in bundle.layers
    assert ContextLayer.L2_WORLD_STATE in bundle.layers
