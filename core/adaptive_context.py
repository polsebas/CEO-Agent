"""Session-scoped adaptive governance bias for policy evaluation."""

from __future__ import annotations

_bias_by_session: dict[str, float] = {}


def set_session_approval_bias(session_id: str, bias: float) -> None:
    _bias_by_session[session_id] = max(0.0, bias)


def get_session_approval_bias(session_id: str | None) -> float:
    if not session_id:
        return 0.0
    return _bias_by_session.get(session_id, 0.0)


def clear_session_approval_bias(session_id: str) -> None:
    _bias_by_session.pop(session_id, None)


def reset_adaptive_context() -> None:
    _bias_by_session.clear()
