"""Structured agent execution with retry layer integrated into runtime."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from schemas.cognition import StructuredRetryTrace
from schemas.responses.base import parse_structured_response, reset_retry_counter
from schemas.runtime import CognitiveBudget

T = TypeVar("T", bound=BaseModel)


class StructuredAgentRunner:
    async def run(
        self,
        agent,
        prompt: str,
        response_model: type[T],
        correlation_id: str,
        *,
        session_id: str = "",
        agent_id: str = "ceo",
        step_id: int = 0,
        budget: CognitiveBudget | None = None,
    ) -> tuple[T, StructuredRetryTrace]:
        budget = budget or CognitiveBudget()
        reset_retry_counter(correlation_id)
        trace = StructuredRetryTrace(
            correlation_id=correlation_id,
            session_id=session_id or correlation_id,
            agent_id=agent_id,
            step_id=step_id,
            created_at=datetime.now(timezone.utc),
        )
        model = getattr(agent, "model", None)
        llm_attempts = 0

        if model is not None:
            try:
                run_response = await agent.arun(prompt, output_schema=response_model)
                llm_attempts = 1
                content = getattr(run_response, "content", None)
                if isinstance(content, response_model):
                    trace.llm_retry_triggered = llm_attempts > 1
                    return content, trace
                if content is not None:
                    raw = content if isinstance(content, str) else json.dumps(content)
                    try:
                        parsed = parse_structured_response(raw, response_model, correlation_id)
                        trace.llm_retry_triggered = llm_attempts > 1
                        return parsed, trace
                    except (ValidationError, ValueError) as exc:
                        trace.validation_error = str(exc)
                        trace.repair_attempts += 1
                        trace.llm_retry_triggered = True
            except Exception as exc:
                trace.validation_error = str(exc)
                trace.final_failure_reason = str(exc)
                trace.llm_retry_triggered = llm_attempts > 1

        fallback = self._deterministic_fallback(prompt, response_model, budget)
        try:
            parsed = parse_structured_response(fallback, response_model, correlation_id)
            return parsed, trace
        except (ValidationError, ValueError) as exc:
            trace.validation_error = str(exc)
            trace.repair_attempts += 1
            trace.final_failure_reason = str(exc)
            trace.llm_retry_triggered = llm_attempts > 0
            return response_model.model_validate(json.loads(fallback)), trace

    def _deterministic_fallback(
        self,
        prompt: str,
        response_model: type[T],
        budget: CognitiveBudget,
    ) -> str:
        from schemas.responses import CEOResponse, CTOResponse

        if response_model is CEOResponse:
            payload = CEOResponse(
                summary=f"Executive analysis for: {prompt[: budget.reasoning_budget // 10]}",
                priorities=["Resolve infrastructure incidents", "Protect runway"],
                delegations=["cto"] if any(k in prompt.lower() for k in ("incident", "deployment", "github")) else [],
                risks=[],
                kpis_snapshot={},
                recommended_actions=["Delegate technical analysis to CTO"] if "incident" in prompt.lower() else [],
            )
        elif response_model is CTOResponse:
            payload = CTOResponse(
                summary=f"Technical assessment: {prompt}",
                incidents=[],
                deployment_status="unknown",
                github_summary={},
                recommended_actions=["Investigate blocked PRs"],
            )
        else:
            payload = response_model.model_validate({"summary": prompt})
        return payload.model_dump_json()


structured_agent_runner = StructuredAgentRunner()
