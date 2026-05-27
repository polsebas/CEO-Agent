"""Manual orchestrator — sole runtime authority (Agno is cognition adapter only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents.factory import create_ceo_agent, create_cto_agent
from core.agent_registry import AgentDisabledError, assert_agent_active
from core.agent_runner import structured_agent_runner
from core.confidence import calibrate_confidence
from core.context import ContextWindowManager
from core.context_lifecycle import context_lifecycle
from core.health import agent_health_registry
from core.prompt_lineage import prompt_lineage_tracker
from core.runtime_health import runtime_health_engine
from core.spans import span_manager
from core.persistence import get_world_state
from core.policy import policy_engine
from core.runtime import RuntimeStateMachine
from core.runtime_session import SessionLockError, run_mutative_session
from core.transaction import PersistRuntimePayload, RuntimeTransition, persist_runtime_tx
from schemas.crisis import CRISIS_OVERRIDES
from schemas.decisions import DecisionRecord
from schemas.effects import SideEffectRecord
from schemas.messages import AgentMessage, AgentRole, MessageIntent
from schemas.responses import CEOResponse, CTOResponse
from schemas.cognition import CognitiveTelemetry
from schemas.runtime import CognitiveBudget, RuntimeState
from schemas.spans import SpanStatus, SpanType
from schemas.tools import ToolResult
from tools.router import execute_tool


class ManualOrchestrator:
    def __init__(self) -> None:
        self.context_manager = ContextWindowManager(max_tokens=8000)

    async def _record_transition(
        self,
        conn: Any,
        sm: RuntimeStateMachine,
        to_state: RuntimeState,
        session_id: str,
    ) -> None:
        from_state = sm.state.value
        tspan = span_manager.start(
            SpanType.TRANSITION,
            runtime_state=from_state,
            metadata={"to": to_state.value},
        )
        sm.transition(to_state)
        span_manager.end(tspan, status=SpanStatus.OK)
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=sm.correlation_id,
                session_id=session_id,
                event_type="runtime.transition",
                event_payload={"from": from_state, "to": to_state.value},
                runtime_transition=RuntimeTransition(
                    from_state=from_state,
                    to_state=to_state.value,
                    correlation_id=sm.correlation_id,
                    session_id=session_id,
                ),
                business_key=f"transition:{from_state}:{to_state.value}:{len(sm.history)}",
            ),
        )

    async def _session_health_degraded(self, session_id: str, *, conn: Any) -> bool:
        from core.persistence import query_runtime_health

        rows = await query_runtime_health(session_id, conn=conn)
        if rows and rows[-1].degraded_mode_active:
            return True
        return await agent_health_registry.is_degraded("ceo")

    def _cognitive_budget(self, *, degraded: bool = False) -> CognitiveBudget:
        budget = CognitiveBudget()
        if degraded:
            budget = CognitiveBudget(
                memory_budget=4000,
                max_retries=0,
                force_deterministic=True,
            )
        return budget

    async def _finalize_session_payload(
        self,
        conn: Any,
        *,
        session_id: str,
        correlation_id: str,
        telemetry: list[CognitiveTelemetry],
        tool_results: list[ToolResult],
    ) -> dict:
        from core.persistence import query_execution_spans
        from core.replay_validator import build_canonical_outcome
        from core.spans import drain_pending_spans
        from core.telemetry.otel import record_health_score

        spans = await query_execution_spans(session_id, correlation_id=correlation_id, conn=conn)
        spans = spans + drain_pending_spans()
        await build_canonical_outcome(session_id, correlation_id, conn=conn)
        replay_confidence = 1.0
        tool_fail = 0.0
        if tool_results:
            tool_fail = 1.0 - sum(1 for t in tool_results if t.success) / len(tool_results)
        ctx_pressure = telemetry[-1].context_pressure if telemetry else 0.0
        health = runtime_health_engine.compute(
            correlation_id=correlation_id,
            session_id=session_id,
            telemetry=telemetry,
            spans=spans,
            tool_failure_rate=tool_fail,
            replay_confidence=replay_confidence,
            context_pressure=ctx_pressure,
        )
        anomalies = runtime_health_engine.detect_anomalies(health, spans=spans)
        score = (
            health.orchestration_health + health.cognition_stability + health.replay_confidence
        ) / 3
        record_health_score(score, session_id)
        return {
            "runtime_health": health,
            "runtime_anomalies": anomalies,
            "cognitive_telemetry": telemetry,
        }

    async def run_founder_request(
        self,
        user_input: str,
        *,
        session_id: str | None = None,
        correlation_id: str | None = None,
        preprocessor_hint: dict | None = None,
    ) -> dict:
        from core.runtime import new_session_ids

        if not session_id and not correlation_id:
            correlation_id, session_id = new_session_ids()
        elif not session_id:
            session_id = str(uuid4())
        elif not correlation_id:
            correlation_id = str(uuid4())

        try:
            return await run_mutative_session(
                session_id,
                lambda conn: self._run_locked(
                    conn,
                    user_input,
                    session_id,
                    correlation_id,
                    preprocessor_hint=preprocessor_hint,
                ),
            )
        except SessionLockError:
            return {"error": "Concurrent write to same session forbidden", "session_id": session_id}

    async def run_deterministic_tool(
        self,
        conn: Any,
        *,
        tool_name: str,
        agent_id: str,
        correlation_id: str,
        session_id: str,
        params: dict | None = None,
    ) -> dict:
        """Unified path for tier1/2 tool execution under full runtime pipeline."""
        span_manager.begin_session(session_id=session_id, correlation_id=correlation_id)
        orch = span_manager.start(SpanType.ORCHESTRATION, runtime_state="perceiving")
        sm = RuntimeStateMachine(correlation_id=correlation_id, session_id=session_id)
        sm.start()
        await self._record_transition(conn, sm, RuntimeState.REASONING, session_id)
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=correlation_id,
                session_id=session_id,
                event_type="founder.intent",
                event_payload={"message": f"deterministic:{tool_name}", "tool": tool_name},
                business_key="founder.intent",
            ),
        )
        await self._record_transition(conn, sm, RuntimeState.WAITING_TOOL, session_id)
        result = await execute_tool(
            tool_name, agent_id, correlation_id, params, session_id=session_id
        )
        await self._record_transition(conn, sm, RuntimeState.OBSERVING, session_id)
        sm.complete()
        span_manager.end(orch, status=SpanStatus.OK)
        intel = await self._finalize_session_payload(
            conn,
            session_id=session_id,
            correlation_id=correlation_id,
            telemetry=[],
            tool_results=[result],
        )
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=correlation_id,
                session_id=session_id,
                event_type="session.completed",
                event_payload={"tool": tool_name, "success": result.success},
                business_key="session.completed",
                store_replay_baseline=True,
                **intel,
            ),
        )
        return {
            "mode": "deterministic",
            "correlation_id": correlation_id,
            "session_id": session_id,
            "result": result.model_dump(),
        }

    async def _run_locked(
        self,
        conn: Any,
        user_input: str,
        session_id: str,
        correlation_id: str,
        *,
        preprocessor_hint: dict | None = None,
    ) -> dict:
        if preprocessor_hint and preprocessor_hint.get("tool_name"):
            return await self.run_deterministic_tool(
                conn,
                tool_name=preprocessor_hint["tool_name"],
                agent_id=preprocessor_hint.get("agent_id", "ceo"),
                correlation_id=correlation_id,
                session_id=session_id,
                params=preprocessor_hint.get("params"),
            )

        span_manager.begin_session(session_id=session_id, correlation_id=correlation_id)
        context_lifecycle.register_session(session_id)
        prompt_lineage_tracker.reset_session(session_id)
        orch_span = span_manager.start(SpanType.ORCHESTRATION, runtime_state="perceiving")
        session_telemetry: list[CognitiveTelemetry] = []
        sm = RuntimeStateMachine(correlation_id=correlation_id, session_id=session_id)
        try:
            sm.start()
            world = get_world_state()
            policy_engine.activate_crisis_if_needed(world)

            await persist_runtime_tx(
                conn,
                PersistRuntimePayload(
                    correlation_id=correlation_id,
                    session_id=session_id,
                    event_type="founder.intent",
                    event_payload={"message": user_input},
                    business_key="founder.intent",
                ),
            )

            degraded = await self._session_health_degraded(session_id, conn=conn)
            if degraded or await agent_health_registry.is_degraded("ceo"):
                return await self._escalate_degraded(
                    conn, user_input, correlation_id, session_id, sm, orch_span=orch_span
                )

            await self._record_transition(conn, sm, RuntimeState.REASONING, session_id)
            ceo_result = await self._run_ceo_analysis(
                conn, user_input, correlation_id, session_id, sm, degraded=degraded
            )
            if ceo_result.get("telemetry"):
                session_telemetry.append(ceo_result["telemetry"])

            delegations = ceo_result.get("delegations", [])
            if "cto" in delegations:
                try:
                    assert_agent_active("cto")
                except AgentDisabledError as exc:
                    ceo_result["cto_error"] = str(exc)
                else:
                    delegation = AgentMessage(
                        id=str(uuid4()),
                        sender=AgentRole.CEO,
                        receiver=AgentRole.CTO,
                        intent=MessageIntent.DELEGATION,
                        payload={"objective": user_input},
                        correlation_id=correlation_id,
                        causation_id=ceo_result.get("decision_id"),
                    )
                    cto_result = await self.delegate_to_specialist(
                        conn, delegation, session_id, sm, degraded=degraded
                    )
                    ceo_result["cto_delegation"] = cto_result
                    if cto_result.get("telemetry"):
                        session_telemetry.append(cto_result["telemetry"])

            sm.complete()
            span_manager.end(orch_span, status=SpanStatus.OK)
            intel = await self._finalize_session_payload(
                conn,
                session_id=session_id,
                correlation_id=correlation_id,
                telemetry=session_telemetry,
                tool_results=[],
            )
            await persist_runtime_tx(
                conn,
                PersistRuntimePayload(
                    correlation_id=correlation_id,
                    session_id=session_id,
                    event_type="session.completed",
                    event_payload={"session_id": session_id, "summary": ceo_result.get("summary", "")},
                    business_key="session.completed",
                    store_replay_baseline=True,
                    **intel,
                ),
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
        conn: Any,
        message: AgentMessage,
        session_id: str,
        sm: RuntimeStateMachine,
        *,
        degraded: bool = False,
    ) -> dict:
        specialist = message.receiver if message.receiver != "human" else AgentRole.CTO
        agent_id = specialist.value if isinstance(specialist, AgentRole) else str(specialist)
        assert_agent_active(agent_id)

        if await agent_health_registry.is_degraded(agent_id):
            await self._record_transition(conn, sm, RuntimeState.ESCALATED, session_id)
            return {"error": "Agent degraded", "agent": agent_id}

        world = get_world_state()
        crisis_override = CRISIS_OVERRIDES.get(policy_engine.active_crisis) if policy_engine.active_crisis else None
        extra_layers = crisis_override.context_expansion if crisis_override else []

        cspan = span_manager.start(SpanType.CONTEXT_BUILD, runtime_state=sm.state.value)
        bundle = self.context_manager.build_context(
            session_id,
            message.id,
            active_task=message.payload.get("objective", ""),
            world_state=world,
            extra_layers=extra_layers,
        )
        span_manager.end(cspan, status=SpanStatus.OK)

        budget = self._cognitive_budget(degraded=degraded)
        if bundle.fingerprint and context_lifecycle.enforce_budget(
            bundle.fingerprint.token_utilization,
            budget.memory_budget,
            bundle.estimated_tokens,
        ) is False:
            return {"error": "Context budget exceeded"}
        if not self.context_manager.within_budget(bundle, budget.memory_budget):
            return {"error": "Context budget exceeded"}

        tool_results: list[ToolResult] = []
        step = 0
        cto_response = None
        tel = None
        summary = f"Specialist {agent_id} processed: {message.payload}"

        if agent_id == "cto":
            for tool_name, params in [
                ("get_repo_health", {}),
                ("list_github_prs", {"status": "open"}),
                ("analyze_incidents", {}),
            ]:
                if sm.state == RuntimeState.OBSERVING:
                    await self._record_transition(conn, sm, RuntimeState.REASONING, session_id)
                await self._record_transition(conn, sm, RuntimeState.WAITING_TOOL, session_id)
                tr = await execute_tool(
                    tool_name, agent_id, message.correlation_id, params, session_id=session_id
                )
                tool_results.append(tr)
                await self._record_transition(conn, sm, RuntimeState.OBSERVING, session_id)
                await persist_runtime_tx(
                    conn,
                    PersistRuntimePayload(
                        correlation_id=message.correlation_id,
                        session_id=session_id,
                        event_type="replay.snapshot",
                        event_payload={"step": step},
                        replay_snapshot={
                            "runtime_state": sm.state.value,
                            "tool_results": [t.model_dump() for t in tool_results],
                            "prompt": message.payload.get("objective", ""),
                            "response": {},
                            "world_state_version": world.version,
                            "context_fingerprint": (
                                bundle.fingerprint.model_dump() if bundle.fingerprint else {}
                            ),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        replay_step=step,
                        business_key=f"replay:{step}",
                    ),
                )
                step += 1

            prompt = self._build_cto_prompt(message.payload.get("objective", ""), tool_results, bundle)
            cto_agent = create_cto_agent()
            lineage = prompt_lineage_tracker.build(
                prompt=prompt,
                session_id=session_id,
                correlation_id=message.correlation_id,
                fingerprint=bundle.fingerprint,
            )
            cto_response, trace, tel = await structured_agent_runner.run(
                cto_agent,
                prompt,
                CTOResponse,
                message.correlation_id,
                session_id=session_id,
                agent_id=agent_id,
                step_id=step,
                budget=self._cognitive_budget(degraded=degraded),
            )
            if bundle.fingerprint:
                tel = tel.model_copy(update={"context_pressure": bundle.fingerprint.token_utilization})
            summary = cto_response.summary
            await persist_runtime_tx(
                conn,
                PersistRuntimePayload(
                    correlation_id=message.correlation_id,
                    session_id=session_id,
                    event_type="replay.snapshot",
                    event_payload={"step": step},
                    replay_snapshot={
                        "runtime_state": sm.state.value,
                        "tool_results": [t.model_dump() for t in tool_results],
                        "prompt": prompt,
                        "response": cto_response.model_dump(),
                        "world_state_version": world.version,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    replay_step=step,
                    retry_trace=trace,
                    cognitive_telemetry=[tel],
                    prompt_lineage=[lineage],
                    business_key=f"replay:{step}:cto",
                ),
            )
            if trace.repair_attempts or trace.llm_retry_triggered:
                rspan = span_manager.start(SpanType.RETRY, metadata={"agent_id": agent_id})
                span_manager.end(rspan, status=SpanStatus.OK)

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
            created_at=datetime.now(timezone.utc),
        )

        effect = SideEffectRecord(
            id=str(uuid4()),
            action_id=decision.id,
            correlation_id=message.correlation_id,
            systems_affected=["github"] if agent_id == "cto" else [],
            mutation_status="complete" if all(t.success for t in tool_results) else "partial",
            rollback_available=False,
            created_at=datetime.now(timezone.utc),
        )

        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=message.correlation_id,
                session_id=session_id,
                event_type="decision.recorded",
                event_payload=decision.model_dump(mode="json"),
                causation_id=message.id,
                decision=decision,
                side_effect=effect,
                business_key=f"decision:{decision.id}",
            ),
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
            "telemetry": tel if agent_id == "cto" else None,
        }

    async def _run_ceo_analysis(
        self,
        conn: Any,
        user_input: str,
        correlation_id: str,
        session_id: str,
        sm: RuntimeStateMachine,
        *,
        degraded: bool = False,
    ) -> dict:
        world = get_world_state()
        cspan = span_manager.start(SpanType.CONTEXT_BUILD, runtime_state=sm.state.value)
        bundle = self.context_manager.build_context(
            session_id,
            correlation_id,
            active_task=user_input,
            world_state=world,
        )
        span_manager.end(cspan, status=SpanStatus.OK)
        kpi = await execute_tool(
            "read_kpi_dashboard", "ceo", correlation_id, session_id=session_id
        )
        context_prompt = self.context_manager.to_prompt(bundle)
        prompt = f"Objective: {user_input}\n{context_prompt}\nKPIs: {kpi.data}\nIncidents: {[i.title for i in world.active_incidents]}"

        lineage = prompt_lineage_tracker.build(
            prompt=prompt,
            session_id=session_id,
            correlation_id=correlation_id,
            fingerprint=bundle.fingerprint,
        )
        ceo_agent = create_ceo_agent()
        response, trace, tel = await structured_agent_runner.run(
            ceo_agent,
            prompt,
            CEOResponse,
            correlation_id,
            session_id=session_id,
            agent_id="ceo",
            step_id=0,
            budget=self._cognitive_budget(degraded=degraded),
        )
        if bundle.fingerprint:
            tel = tel.model_copy(update={"context_pressure": bundle.fingerprint.token_utilization})
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
            created_at=datetime.now(timezone.utc),
        )
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=correlation_id,
                session_id=session_id,
                event_type="decision.recorded",
                event_payload=decision.model_dump(mode="json"),
                decision=decision,
                replay_snapshot={
                    "runtime_state": sm.state.value,
                    "tool_results": [kpi.model_dump()],
                    "prompt": prompt,
                    "response": response.model_dump(),
                    "world_state_version": world.version,
                    "context_fingerprint": bundle.fingerprint.model_dump() if bundle.fingerprint else {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                replay_step=0,
                retry_trace=trace,
                cognitive_telemetry=[tel],
                prompt_lineage=[lineage],
                business_key=f"decision:{decision.id}",
            ),
        )
        await agent_health_registry.record_run("ceo", success=True, latency_ms=tel.reasoning_latency_ms)
        return {
            "decision_id": decision.id,
            "summary": response.summary,
            "response": response.model_dump(),
            "delegations": response.delegations,
            "telemetry": tel,
        }

    def _build_cto_prompt(self, objective: str, tool_results: list[ToolResult], bundle) -> str:
        tools_summary = {t.tool_name: t.data for t in tool_results}
        return f"Objective: {objective}\nTool results: {tools_summary}\nContext layers: {list(bundle.layers.keys())}"

    async def _escalate_degraded(
        self,
        conn: Any,
        user_input: str,
        correlation_id: str,
        session_id: str,
        sm: RuntimeStateMachine,
        *,
        orch_span: Any = None,
    ) -> dict:
        await self._record_transition(conn, sm, RuntimeState.ESCALATED, session_id)
        result = await execute_tool(
            "escalate_to_human",
            "ceo",
            correlation_id,
            {"reason": "CEO agent degraded"},
            session_id=session_id,
        )
        try:
            sm.complete()
        except Exception:
            pass
        if orch_span is not None:
            span_manager.end(orch_span, status=SpanStatus.ERROR)
        intel = await self._finalize_session_payload(
            conn,
            session_id=session_id,
            correlation_id=correlation_id,
            telemetry=[],
            tool_results=[result],
        )
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=correlation_id,
                session_id=session_id,
                event_type="session.completed",
                event_payload={
                    "escalated": True,
                    "reason": "Agent in degraded mode",
                    "message": user_input[:200],
                },
                business_key="session.completed",
                store_replay_baseline=True,
                **intel,
            ),
        )
        return {
            "session_id": session_id,
            "correlation_id": correlation_id,
            "escalated": True,
            "reason": "Agent in degraded mode",
            "result": result.model_dump(),
        }


manual_orchestrator = ManualOrchestrator()
