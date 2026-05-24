"""Calibrated confidence — multi-factor, not LLM raw score."""

from schemas.decisions import CalibratedConfidence


def calibrate_confidence(
    *,
    deterministic_checks: float = 1.0,
    policy_validation: float = 1.0,
    historical_success_rate: float = 1.0,
    tool_reliability: float = 1.0,
    retry_count: int = 0,
) -> CalibratedConfidence:
    retry_penalty = max(0.0, 1.0 - (retry_count * 0.15))
    factors = {
        "deterministic_checks": deterministic_checks,
        "policy_validation": policy_validation,
        "historical_success_rate": historical_success_rate,
        "tool_reliability": tool_reliability,
        "retry_penalty": retry_penalty,
    }
    weights = {
        "deterministic_checks": 0.25,
        "policy_validation": 0.25,
        "historical_success_rate": 0.20,
        "tool_reliability": 0.20,
        "retry_penalty": 0.10,
    }
    score = sum(factors[k] * weights[k] for k in factors)
    return CalibratedConfidence(score=min(1.0, max(0.0, score)), factors=factors)
