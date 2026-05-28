"""RRM-3C1 — context intelligence gates."""

from __future__ import annotations

import pytest

from core.context_lifecycle import context_lifecycle
from core.context_priority import score_layer, select_layers
from core.canonical import stable_hash


@pytest.mark.rrm3
def test_prioritization_stable():
    s1 = score_layer("l3", token_utilization=0.5, session_age_seconds=100)
    s2 = score_layer("l3", token_utilization=0.5, session_age_seconds=100)
    assert s1.composite == s2.composite


@pytest.mark.rrm3
def test_bounded_layer_selection():
    layers = {
        "l1": "x" * 2000,
        "l3": "y" * 2000,
        "l4": "z" * 2000,
        "l5": "w" * 2000,
    }
    selected = select_layers(
        layers,
        memory_budget=500,
        estimated_tokens=4000,
        token_utilization=1.2,
    )
    assert "l1" in selected
    assert len(selected) <= len(layers)


@pytest.mark.rrm3
def test_deterministic_compression():
    layers = {"l4": "a" * 500}
    s1, e1 = context_lifecycle.summarize_old_context(layers)
    s2, e2 = context_lifecycle.summarize_old_context(layers)
    assert s1 == s2
    assert e1 == e2
    assert stable_hash(s1) == stable_hash(s2)
