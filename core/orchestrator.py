"""Manual orchestrator — sole runtime authority (Agno is cognition adapter only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents.factory import create_ceo_agent, create_cto_agent
from core.agent_registry import AgentDisabledError, assert_agent_active
from core.agent_runner import structured_agent_runner
from core.confidence import calibrate_confidence
from core.adaptive_context import clear_session_approval_bias, set_session_approval_bias
from core.adaptive_governance import adaptive_governance_service
from core.adaptive_policy import adaptive_policy_engine, policy_hash
from core.adaptive_signals import collect_adaptive_signals
from core.canonical import stable_hash
from core.replay_errors import ReplayIntegrityError, ReplayVersionMismatchError
from core.cognitive_budget import adaptive_policy_to_budget
from core.context import ContextWindowManager
from core.context_lifecycle import context_lifecycle
from core.context_priority import score_layer, select_layers
from core.delegation_policy import delegation_allowed
from core.health import agent_health_registry
from core.replay_analytics import analyze_replay
from core.session_stability import session_stability_service
from core.tool_reliability import tool_reliability_service
from core.tool_routing import decide_routing
from core.prompt_lineage import prompt_lineage_tracker
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
from schemas.adaptive import AdaptivePolicy
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

    def _cognitive_budget_from_policy(self, policy: AdaptivePolicy) -> CognitiveBudget:
        return adaptive_policy_to_budget(policy)

    def _cognitive_budget(self, *, degraded: bool = False, policy: AdaptivePolicy | None = None) -> CognitiveBudget:
        if policy is not None:
            return self._cognitive_budget_from_policy(policy)
        if degraded:
            return CognitiveBudget(memory_budget=4000, max_retries=0, force_deterministic=True)
        return CognitiveBudget()

    def _filter_new_stability_events(
        self, sm: RuntimeStateMachine, events: list
    ) -> list:
        new_events = []
        for ev in events:
            key = f"{ev.event_type}:{stable_hash(ev.metadata)}"
            if key in sm._stability_event_keys:
                continue
            sm._stability_event_keys.add(key)
            new_events.append(ev)
        return new_events

    async def _persist_context_priorities(
        self,
        conn: Any,
        *,
        session_id: str,
        correlation_id: str,
        scores: list,
        business_suffix: str,
    ) -> None:
        if not scores:
            return
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=correlation_id,
                session_id=session_id,
                event_type="context.priority",
                event_payload={"layers": [s.source_id for s in scores]},
                business_key=f"context.priority:{business_suffix}",
                context_priority_scores=scores,
            ),
        )

    async def _resolve_adaptive_policy(
        self,
        conn: Any,
        session_id: str,
        correlation_id: str,
        sm: RuntimeStateMachine,
        *,
        force: bool = False,
        tool_failure_rate: float = 0.0,
        telemetry: list | None = None,
    ) -> AdaptivePolicy:
        if sm.adaptive_policy is not None and not force and not sm.policy_recompute_required:
            set_session_approval_bias(session_id, sm.adaptive_policy.approval_escalation_bias)
            return sm.adaptive_policy

        from core.persistence import query_cognitive_telemetry

        tel_rows = telemetry
        if tel_rows is None:
            tel_rows = await query_cognitive_telemetry(
                session_id, correlation_id=correlation_id, conn=conn
            )

        signals = await collect_adaptive_signals(
            session_id,
            correlation_id,
            conn=conn,
            tool_failure_rate=tool_failure_rate,
            stability_pressure=0.0,
        )
        governance_events = []
        analytics = None
        if force:
            try:
                analytics = await analyze_replay(session_id, correlation_id, conn=conn)
                signals = adaptive_governance_service.apply_replay_to_signals(signals, analytics)
                governance_events = adaptive_governance_service.events_from_analytics(analytics)
            except (ReplayIntegrityError, ReplayVersionMismatchError):
                pass

        assessment = session_stability_service.assess_at_boundary(
            session_id=session_id,
            correlation_id=correlation_id,
            telemetry=tel_rows or [],
            tool_names=list(sm._session_tool_names),
            delegations=list(sm._session_delegations),
        )
        if assessment.stability_pressure > 0:
            signals = signals.model_copy(update={"stability_pressure": assessment.stability_pressure})

        policy = adaptive_policy_engine.derive(signals)
        if analytics is not None:
            policy = adaptive_governance_service.adjust_policy_cognition_only(policy, analytics)

        sm.adaptive_policy = policy
        sm.policy_recompute_required = False
        set_session_approval_bias(session_id, policy.approval_escalation_bias)

        from core.adaptive_policy import signals_hash as sh

        snap = adaptive_policy_engine.snapshot(signals, policy=policy)
        new_stability = self._filter_new_stability_events(sm, assessment.events)
        await persist_runtime_tx(
            conn,
            PersistRuntimePayload(
                correlation_id=correlation_id,
                session_id=session_id,
                event_type="adaptive.policy",
                event_payload={"policy_hash": policy_hash(policy), "signals_hash": sh(signals)},
                business_key=f"adaptive.policy:{snap.policy_hash}",
                adaptive_policy_snapshot=snap,
                stability_events=new_stability,
                governance_events=governance_events if force else [],
            ),
        )
        if new_stability:
            from core.telemetry.otel import record_delegation_disable, record_retry_storm

            for ev in new_stability:
                if ev.event_type == "retry_storm":
                    record_retry_storm(session_id)
                if ev.event_type == "delegation_loop":
                    record_delegation_disable(session_id)
        from core.telemetry.otel import record_adaptive_policy_change, record_context_budget_ratio

        record_adaptive_policy_change(session_id)
        record_context_budget_ratio(policy.context_budget_ratio, session_id)
        return policy

    async def _boundary_recompute_if_needed(
        self,
        conn: Any,
        session_id: str,
        correlation_id: str,
        sm: RuntimeStateMachine,
        *,
        telemetry: list | None = None,
        retry_trace=None,
    ) -> AdaptivePolicy:
        if retry_trace and (retry_trace.repair_attempts or retry_trace.llm_retry_triggered):
            sm.policy_recompute_required = True
        if sm.policy_recompute_required:
            return await self._resolve_adaptive_policy(
                conn,
                session_id,
                correlation_id,
                sm,
                force=True,
                telemetry=telemetry,
            )
        if sm.adaptive_policy:
            return sm.adaptive_policy
        return await self._resolve_adaptive_policy(conn, session_id, correlation_id, sm)

    async def _finalize_session_payload(
        self,
        conn: Any,
        *,
        session_id: str,
        correlation_id: str,
        telemetry: list[CognitiveTelemetry],
        tool_results: list[ToolResult],
    ) -> dict:
        tool_fail = 0.0
        if tool_results:
            tool_fail = 1.0 - sum(1 for t in tool_results if t.success) / len(tool_results)
        return {
            "cognitive_telemetry": telemetry,
            "tool_failure_rate": tool_fail,
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

            policy = await self._resolve_adaptive_policy(
                conn, session_id, correlation_id, sm, tool_failure_rate=0.0, telemetry=[]
            )

            await self._record_transition(conn, sm, RuntimeState.REASONING, session_id)
            ceo_result = await self._run_ceo_analysis(
                conn, user_input, correlation_id, session_id, sm, policy=policy
            )
            if ceo_result.get("telemetry"):
                session_telemetry.append(ceo_result["telemetry"])

            delegations = ceo_result.get("delegations", [])
            sm._session_delegations.extend(delegations)
            if delegation_allowed(policy, specialist="cto", ceo_delegations=delegations):
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
                        conn, delegation, session_id, sm, policy=policy
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
            await self._resolve_adaptive_policy(
                conn,
                session_id,
                correlation_id,
                sm,
                force=True,
                tool_failure_rate=intel.get("tool_failure_rate", 0.0),
                telemetry=session_telemetry,
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
        finally:
            clear_session_approval_bias(session_id)

    async def delegate_to_specialist(
        self,
        conn: Any,
        message: AgentMessage,
        session_id: str,
        sm: RuntimeStateMachine,
        *,
        degraded: bool = False,
        policy: AdaptivePolicy | None = None,
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

        if policy is None:
            policy = await self._resolve_adaptive_policy(
                conn, session_id, message.correlation_id, sm
            )
        budget = self._cognitive_budget(degraded=degraded, policy=policy)

        priority_scores: list = []
        if bundle.fingerprint and bundle.layers:
            priority_scores = [
                score_layer(
                    k,
                    token_utilization=bundle.fingerprint.token_utilization,
                    session_age_seconds=context_lifecycle.context_age_seconds(session_id),
                )
                for k in bundle.layers
            ]
            bundle.layers = select_layers(
                bundle.layers,
                memory_budget=budget.memory_budget,
                estimated_tokens=bundle.estimated_tokens,
                token_utilization=bundle.fingerprint.token_utilization,
                session_age_seconds=context_lifecycle.context_age_seconds(session_id),
            )
            if bundle.fingerprint.token_utilization > 0.9 or policy.context_budget_ratio < 0.6:
                bundle.layers, _entry = context_lifecycle.summarize_old_context(bundle.layers)
                bundle.fingerprint = context_lifecycle.enrich_fingerprint(
                    bundle.fingerprint,
                    session_id=session_id,
                    compression_strategy="aggressive",
                    provenance_entry=_entry,
                )
            await self._persist_context_priorities(
                conn,
                session_id=session_id,
                correlation_id=message.correlation_id,
                scores=priority_scores,
                business_suffix="delegate",
            )

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
            from core.persistence import query_tool_reliability_profiles

            profiles = {p.tool_name: p for p in await query_tool_reliability_profiles(conn=conn)}
            tool_plan = [
                ("get_repo_health", {}),
                ("list_github_prs", {"status": "open"}),
                ("analyze_incidents", {}),
            ]
            routing = decide_routing(None, policy)
            if not routing.allow_parallel:
                tool_plan = tool_plan[:1]
            reliability_updates: list = []
            for tool_name, params in tool_plan:
                if sm.state == RuntimeState.OBSERVING:
                    await self._record_transition(conn, sm, RuntimeState.REASONING, session_id)
                await self._record_transition(conn, sm, RuntimeState.WAITING_TOOL, session_id)
                prof = profiles.get(tool_name)
                tr_route = decide_routing(prof, policy)
                if tr_route.skip_optional and tool_name != "get_repo_health":
                    continue
                extra_bias = 1.0 if tr_route.require_approval_escalation else 0.0
                tr = await execute_tool(
                    tool_name,
                    agent_id,
                    message.correlation_id,
                    params,
                    session_id=session_id,
                    extra_approval_bias=extra_bias,
                )
                tool_results.append(tr)
                sm._session_tool_names.append(tool_name)
                prev = profiles.get(tool_name)
                updated = tool_reliability_service.update_from_result(prev, tr)
                profiles[tool_name] = updated
                reliability_updates.append(updated)
                from core.telemetry.otel import record_tool_confidence

                record_tool_confidence(tool_name, updated.confidence_score)
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

            if reliability_updates:
                await persist_runtime_tx(
                    conn,
                    PersistRuntimePayload(
                        correlation_id=message.correlation_id,
                        session_id=session_id,
                        event_type="tool.reliability",
                        event_payload={"tools": [p.tool_name for p in reliability_updates]},
                        business_key=f"tool.reliability:{step}",
                        tool_reliability_updates=reliability_updates,
                    ),
                )

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
                budget=self._cognitive_budget(degraded=degraded, policy=policy),
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
                await self._boundary_recompute_if_needed(
                    conn, session_id, message.correlation_id, sm, retry_trace=trace
                )

        decision = DecisionRecord(
            id=str(uuid4()),
            correlation_id=message.correlation_id,
            causation_id=message.id,
            objective=message.payload.get("objective", ""),
            context_used=[message.id],
            policies_applied=(
                [policy_engine.active_crisis.value] if policy_engine.active_crisis else []
            )
            + ([f"adaptive_bias:{policy.approval_escalation_bias}"] if policy else []),
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
        policy: AdaptivePolicy | None = None,
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
        if policy is None:
            policy = await self._resolve_adaptive_policy(conn, session_id, correlation_id, sm)
        budget = self._cognitive_budget(degraded=degraded, policy=policy)
        if bundle.fingerprint and bundle.layers:
            priority_scores = [
                score_layer(
                    k,
                    token_utilization=bundle.fingerprint.token_utilization,
                    session_age_seconds=context_lifecycle.context_age_seconds(session_id),
                )
                for k in bundle.layers
            ]
            bundle.layers = select_layers(
                bundle.layers,
                memory_budget=budget.memory_budget,
                estimated_tokens=bundle.estimated_tokens,
                token_utilization=bundle.fingerprint.token_utilization,
                session_age_seconds=context_lifecycle.context_age_seconds(session_id),
            )
            await self._persist_context_priorities(
                conn,
                session_id=session_id,
                correlation_id=correlation_id,
                scores=priority_scores,
                business_suffix="ceo",
            )
        kpi = await execute_tool(
            "read_kpi_dashboard",
            "ceo",
            correlation_id,
            session_id=session_id,
        )
        sm._session_tool_names.append("read_kpi_dashboard")
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
            budget=budget,
        )
        if policy and not delegation_allowed(policy, specialist="cto", ceo_delegations=response.delegations):
            response = response.model_copy(update={"delegations": []})
        if bundle.fingerprint:
            tel = tel.model_copy(update={"context_pressure": bundle.fingerprint.token_utilization})
        if trace.repair_attempts or trace.llm_retry_triggered:
            await self._boundary_recompute_if_needed(
                conn, session_id, correlation_id, sm, retry_trace=trace
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
