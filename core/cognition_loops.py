"""Deterministic cognition loop detection."""

from __future__ import annotations

from core.canonical import stable_hash


def sequence_signature(items: list[str], window: int = 4) -> str:
    if len(items) < window:
        return ""
    tail = items[-window:]
    return stable_hash({"seq": tail})


def detect_delegation_loop(delegation_targets: list[str], *, threshold: int = 3) -> bool:
    if len(delegation_targets) < threshold:
        return False
    tail = delegation_targets[-threshold:]
    return len(set(tail)) == 1


def detect_tool_cycle(tool_names: list[str], *, threshold: int = 4) -> bool:
    sig = sequence_signature(tool_names, window=threshold)
    if not sig or len(tool_names) < threshold * 2:
        return False
    prev_sig = sequence_signature(tool_names[:-threshold], window=threshold)
    return bool(prev_sig and sig == prev_sig)


def detect_retry_loop(retry_signatures: list[str], *, threshold: int = 2) -> bool:
    if len(retry_signatures) < threshold:
        return False
    return len(set(retry_signatures[-threshold:])) == 1
