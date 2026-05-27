"""Cognitive telemetry engine."""

from __future__ import annotations

import time
from typing import Any

from core.replay_validator import prompt_hash
from core.telemetry.otel import record_cognitive_metrics
from schemas.cognition import CognitiveTelemetry, StructuredRetryTrace


class CognitiveTelemetryEngine:
    def build(
        self,
        *,
        correlation_id: str,
        session_id: str,
        agent_id: str,
        trace: StructuredRetryTrace | None,
        context_pressure: float = 0.0,
        token_estimate: int = 0,
        reasoning_latency_ms: int = 0,
        replay_confidence: float = 1.0,
    ) -> CognitiveTelemetry:
        retry_count = 0
        if trace:
            retry_count = trace.repair_attempts + (1 if trace.llm_retry_triggered else 0)
        return CognitiveTelemetry(
            correlation_id=correlation_id,
            session_id=session_id,
            agent_id=agent_id,
            reasoning_latency_ms=reasoning_latency_ms,
            retry_count=retry_count,
            token_estimate=token_estimate,
            context_pressure=context_pressure,
            replay_confidence=replay_confidence,
        )

    def record_otel(self, telemetry: CognitiveTelemetry) -> None:
        record_cognitive_metrics(
            agent_id=telemetry.agent_id,
            session_id=telemetry.session_id,
            token_estimate=telemetry.token_estimate,
            reasoning_latency_ms=telemetry.reasoning_latency_ms,
            retry_count=telemetry.retry_count,
        )


cognition_engine = CognitiveTelemetryEngine()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class TimedReasoning:
    """Context manager for reasoning latency."""

    def __init__(self) -> None:
        self.started = 0.0
        self.elapsed_ms = 0

    def __enter__(self) -> TimedReasoning:
        self.started = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed_ms = int((time.perf_counter() - self.started) * 1000)


def hash_prompt_material(prompt: str) -> str:
    return prompt_hash(prompt)
