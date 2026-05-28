"""Delegation rules derived from adaptive policy."""

from __future__ import annotations

from schemas.adaptive import AdaptivePolicy


def delegation_allowed(policy: AdaptivePolicy, *, specialist: str, ceo_delegations: list[str]) -> bool:
    if not policy.delegation_enabled:
        return False
    if specialist not in ceo_delegations:
        return False
    return True


def delegation_frozen(policy: AdaptivePolicy) -> bool:
    return not policy.delegation_enabled
