import pytest

from core.runtime import InvalidStateTransition, RuntimeStateMachine
from schemas.runtime import RuntimeState


def test_valid_state_transitions():
    sm = RuntimeStateMachine(correlation_id="c1", session_id="s1")
    sm.start()
    assert sm.state == RuntimeState.PERCEIVING
    sm.transition(RuntimeState.REASONING)
    sm.transition(RuntimeState.COMPLETED)
    assert sm.state == RuntimeState.COMPLETED


def test_invalid_transition_raises():
    sm = RuntimeStateMachine(correlation_id="c1", session_id="s1")
    with pytest.raises(InvalidStateTransition):
        sm.transition(RuntimeState.EXECUTING)


def test_stuck_detection():
    sm = RuntimeStateMachine(correlation_id="c1", session_id="s1", max_stuck_iterations=3)
    sm.start()
    sm.transition(RuntimeState.REASONING)
    sm.transition(RuntimeState.WAITING_TOOL)
    sm.detect_stuck(False)
    sm.detect_stuck(False)
    result = sm.detect_stuck(False)
    assert result == RuntimeState.REPLANNING
