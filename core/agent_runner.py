"""Structured agent execution with retry layer integrated into runtime."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from schemas.responses.base import parse_structured_response, reset_retry_counter
from schemas.runtime import CognitiveBudget, RuntimeState

T = TypeVar("T", bound=BaseModel)


class StructuredAgentRunner:
    async def run(
        self,
        agent,
        prompt: str,
        response_model: type[T],
        correlation_id: str,
        *,
        budget: CognitiveBudget | None = None,
    ) -> tuple[T, RuntimeState]:
        budget = budget or CognitiveBudget()
        reset_retry_counter(correlation_id)
        model = getattr(agent, "model", None)

        if model is not None:
            try:
                run_response = await agent.arun(prompt, output_schema=response_model)
                content = getattr(run_response, "content", None)
                if isinstance(content, response_model):
                    return content, RuntimeState.REASONING
                if content is not None:
                    raw = content if isinstance(content, str) else json.dumps(content)
                    parsed = parse_structured_response(raw, response_model, correlation_id)
                    return parsed, RuntimeState.REASONING
            except Exception:
                pass

        fallback = self._deterministic_fallback(prompt, response_model, budget)
        parsed = parse_structured_response(fallback, response_model, correlation_id)
        return parsed, RuntimeState.REASONING

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
