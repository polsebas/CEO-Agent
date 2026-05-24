"""Manual orchestrator — primary delegation path with real Agno cognition."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from agents.factory import create_ceo_agent, create_cto_agent
from core.agent_runner import structured_agent_runner
from core.confidence import calibrate_confidence
from core.context import ContextWindowManager
from core.health import agent_health_registry
from core.persistence import (
    get_world_state,
    persist_execution_bundle,
    save_replay_snapshot,
)
from core.policy import policy_engine
from core.runtime import RuntimeStateMachine
from core.session_lock import SessionLockError, session_lock
from schemas.crisis import CRISIS_OVERRIDES
from schemas.decisions import DecisionRecord
from schemas.effects import SideEffectRecord
from schemas.messages import AgentMessage, AgentRole, MessageIntent
from schemas.responses import CEOResponse, CTOResponse
from schemas.runtime import CognitiveBudget, RuntimeState
from schemas.tools import ToolResult
from tools.router import execute_tool


class ManualOrchestrator:
    def __init__(self) -> None:
        self.context_manager = ContextWindowManager(max_tokens=8000)

    def _make_state_machine(self, correlation_id: str, session_id: str) -> RuntimeStateMachine:
        sm = RuntimeStateMachine(correlation_id=correlation_id, session_id=session_id)
        sm.start()
        sm.transition(RuntimeState.REASONING)
        return sm

    async def run_founder_request(
        self,
        user_input: str,
        *,
        session_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        from core.runtime import new_session_ids

        if not session_id and not correlation_id:
            correlation_id, session_id = new_session_ids()
        elif not session_id:
            session_id = str(uuid4())
        elif not correlation_id:
            correlation_id = str(uuid4())

        try:
            async with session_lock(session_id):
                return await self._run_locked(user_input, session_id, correlation_id)
        except SessionLockError:
            return {"error": "Concurrent write to same session forbidden", "session_id": session_id}

    async def _run_locked(self, user_input: str, session_id: str, correlation_id: str) -> dict:
        sm = RuntimeStateMachine(correlation_id=correlation_id, session_id=session_id)
        try:
            sm.start()
            world = get_world_state()
            policy_engine.activate_crisis_if_needed(world)

            if await agent_health_registry.is_degraded("ceo"):
                return await self._escalate_degraded(user_input, correlation_id, session_id, sm)

            sm.transition(RuntimeState.REASONING)
            ceo_result = await self._run_ceo_analysis(user_input, correlation_id, session_id, sm)

            if "delegate_cto" in user_input.lower() or any(
                k in user_input.lower() for k in ("incident", "deployment", "github", "anomaly")
            ):
                delegation = AgentMessage(
                    id=str(uuid4()),
                    sender=AgentRole.CEO,
                    receiver=AgentRole.CTO,
                    intent=MessageIntent.DELEGATION,
                    payload={"objective": user_input},
                    correlation_id=correlation_id,
                    causation_id=ceo_result.get("decision_id"),
                )
                cto_result = await self.delegate_to_specialist(delegation, session_id, sm)
                ceo_result["cto_delegation"] = cto_result

            sm.complete()
            await persist_execution_bundle(
                correlation_id=correlation_id,
                event_type="session.completed",
                event_payload={"session_id": session_id, "summary": ceo_result.get("summary", "")},
            )
            return {
                "session_id": session_id,
                "correlation_id": correlation_id,
                "runtime_state": sm.state.value,
                "result": ceo_result,
            }
        except Exception as exc:
            sm.fail(str(exc))
            return {"error": str(exc), "session_id": session_id, "correlation_id": correlation_id}

    async def delegate_to_specialist(
        self,
        message: AgentMessage,
        session_id: str,
        sm: RuntimeStateMachine,
    ) -> dict:
        specialist = message.receiver if message.receiver != "human" else AgentRole.CTO
        agent_id = specialist.value if isinstance(specialist, AgentRole) else str(specialist)

        if await agent_health_registry.is_degraded(agent_id):
            sm.transition(RuntimeState.ESCALATED)
            return {"error": "Agent degraded", "agent": agent_id}

        world = get_world_state()
        crisis_override = CRISIS_OVERRIDES.get(policy_engine.active_crisis) if policy_engine.active_crisis else None
        extra_layers = crisis_override.context_expansion if crisis_override else []

        bundle = self.context_manager.build_context(
            session_id,
            message.id,
            active_task=message.payload.get("objective", ""),
            world_state=world,
            extra_layers=extra_layers,
        )

        if not self.context_manager.within_budget(bundle, CognitiveBudget().memory_budget):
            return {"error": "Context budget exceeded"}

        tool_results: list[ToolResult] = []
        step = 0
        if agent_id == "cto":
            for tool_name, params in [
                ("get_repo_health", {}),
                ("list_github_prs", {"status": "open"}),
                ("analyze_incidents", {}),
            ]:
                if sm.state == RuntimeState.OBSERVING:
                    sm.transition(RuntimeState.REASONING)
                sm.transition(RuntimeState.WAITING_TOOL)
                tr = await execute_tool(tool_name, agent_id, message.correlation_id, params)
                tool_results.append(tr)
                sm.transition(RuntimeState.OBSERVING)
                await save_replay_snapshot(
                    session_id,
                    message.correlation_id,
                    step,
                    {
                        "runtime_state": sm.state.value,
                        "tool_results": [t.model_dump() for t in tool_results],
                        "prompt": message.payload.get("objective", ""),
                        "response": {},
                        "world_state_version": world.version,
                    },
                )
                step += 1

            prompt = self._build_cto_prompt(message.payload.get("objective", ""), tool_results, bundle)
            cto_agent = create_cto_agent()
            cto_response, _ = await structured_agent_runner.run(
                cto_agent,
                prompt,
                CTOResponse,
                message.correlation_id,
            )
            summary = cto_response.summary
            await save_replay_snapshot(
                session_id,
                message.correlation_id,
                step,
                {
                    "runtime_state": sm.state.value,
                    "tool_results": [t.model_dump() for t in tool_results],
                    "prompt": prompt,
                    "response": cto_response.model_dump(),
                    "world_state_version": world.version,
                },
            )
        else:
            summary = f"Specialist {agent_id} processed: {message.payload}"
            cto_response = None

        decision = DecisionRecord(
            id=str(uuid4()),
            correlation_id=message.correlation_id,
            causation_id=message.id,
            objective=message.payload.get("objective", ""),
            context_used=[message.id],
            policies_applied=[policy_engine.active_crisis.value] if policy_engine.active_crisis else [],
            tools_used=[t.tool_name for t in tool_results],
            reasoning_summary=summary,
            confidence=calibrate_confidence(
                tool_reliability=sum(1 for t in tool_results if t.success) / max(len(tool_results), 1),
            ),
            final_action=f"delegate:{agent_id}",
            outcome="success",
            agent=agent_id,
            runtime_state=sm.state,
            created_at=datetime.utcnow(),
        )

        effect = SideEffectRecord(
            id=str(uuid4()),
            action_id=decision.id,
            correlation_id=message.correlation_id,
            systems_affected=["github"] if agent_id == "cto" else [],
            mutation_status="complete" if all(t.success for t in tool_results) else "partial",
            rollback_available=False,
            created_at=datetime.utcnow(),
        )

        await persist_execution_bundle(
            correlation_id=message.correlation_id,
            causation_id=message.id,
            event_type="decision.recorded",
            event_payload=decision.model_dump(mode="json"),
            decision=decision,
            side_effect=effect,
        )

        await agent_health_registry.record_run(
            agent_id,
            success=effect.mutation_status == "complete",
            latency_ms=sum(t.latency_ms for t in tool_results),
        )

        return {
            "decision_id": decision.id,
            "summary": summary,
            "tool_results": [t.model_dump() for t in tool_results],
            "structured_response": cto_response.model_dump() if cto_response else {},
        }

    async def _run_ceo_analysis(
        self,
        user_input: str,
        correlation_id: str,
        session_id: str,
        sm: RuntimeStateMachine,
    ) -> dict:
        world = get_world_state()
        kpi = await execute_tool("read_kpi_dashboard", "ceo", correlation_id)
        prompt = f"Objective: {user_input}\nKPIs: {kpi.data}\nIncidents: {[i.title for i in world.active_incidents]}"
        ceo_agent = create_ceo_agent()
        response, _ = await structured_agent_runner.run(
            ceo_agent,
            prompt,
            CEOResponse,
            correlation_id,
        )
        decision = DecisionRecord(
            id=str(uuid4()),
            correlation_id=correlation_id,
            objective=user_input,
            reasoning_summary=response.summary,
            confidence=calibrate_confidence(deterministic_checks=0.9),
            final_action="ceo_analysis",
            outcome="success",
            agent="ceo",
            runtime_state=sm.state,
            created_at=datetime.utcnow(),
        )
        await persist_execution_bundle(
            correlation_id=correlation_id,
            event_type="decision.recorded",
            event_payload=decision.model_dump(mode="json"),
            decision=decision,
        )
        await agent_health_registry.record_run("ceo", success=True, latency_ms=50)
        await save_replay_snapshot(
            session_id,
            correlation_id,
            0,
            {
                "runtime_state": sm.state.value,
                "tool_results": [kpi.model_dump()],
                "prompt": prompt,
                "response": response.model_dump(),
                "world_state_version": world.version,
            },
        )
        return {"decision_id": decision.id, "summary": response.summary, "response": response.model_dump()}

    def _build_cto_prompt(self, objective: str, tool_results: list[ToolResult], bundle) -> str:
        tools_summary = {t.tool_name: t.data for t in tool_results}
        return f"Objective: {objective}\nTool results: {tools_summary}\nContext layers: {list(bundle.layers.keys())}"

    async def _escalate_degraded(self, user_input: str, correlation_id: str, session_id: str, sm: RuntimeStateMachine) -> dict:
        sm.transition(RuntimeState.ESCALATED)
        result = await execute_tool("escalate_to_human", "ceo", correlation_id, {"reason": "CEO agent degraded"})
        return {
            "session_id": session_id,
            "correlation_id": correlation_id,
            "escalated": True,
            "reason": "Agent in degraded mode",
            "result": result.model_dump(),
        }


manual_orchestrator = ManualOrchestrator()
