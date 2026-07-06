# MVP-1 Demo Walkthrough

Guía reproducible (&lt;10 min) para stakeholders no técnicos.

## Prerrequisitos

```bash
export AUTH_DISABLED=true   # opcional para dev local
python scripts/seed_demo.py   # solo escenarios MVP-1 (sin FacilRentaCar)
uvicorn main:app --reload
```

Abrir `http://localhost:8000/login` y elegir rol según el paso.

## Demo 1 — Founder workflow (orchestration)

1. Login como **operator**
2. Ir a **Execute** o usar sesión seed `demo-founder-strategy`
3. URL directa: `/sessions/demo-founder-strategy?correlation_id=demo-founder-strategy-corr`
4. Mostrar **Timeline** unificada: intent → transitions → spans
5. Sidebar: human summaries operacionales

## Demo 2 — Approval flow (governance)

1. Operator prepara acción (API o flujo existente)
2. Login como **reviewer**
3. Ir a **Approvals** → aprobar acción pendiente
4. Volver a session detail y mostrar evento en timeline

## Demo 3 — Retry storm (adaptive cognition)

1. Sesión seed: `demo-degraded-session`
2. Tab **Adaptive**: policy, stability events
3. Human summary: degraded mode / retry depth

## Demo 4 — Replay divergence (runtime intelligence)

1. Sesión seed: `demo-incident-response`
2. Tab **Replay**: confidence, drift severity, frozen vs live
3. **Export bundle** para compartir caso async

## Roles MVP

| Rol | Pantallas |
|-----|-----------|
| operator | Dashboard, Sessions, Execute, Replay |
| reviewer | Approvals, Diagnostics, Replay analysis |
| readonly | Dashboard, Session explorer |

## Criterio de éxito

Stakeholder entiende valor **sin** leer logs raw ni JSON crudo — solo timeline + human summaries + approvals separados.

## FacilRentaCar (4 escenarios gobernados)

Ver [`docs/FACILRENTACAR_DEMO.md`](FACILRENTACAR_DEMO.md). Seed **por escenario** (no incluido en seed default):

```bash
python scripts/seed_demo.py --scenario compensation   # | reactivation | occupancy | cancellation
python scripts/seed_demo.py --facilrentacar-all       # los 4 escenarios FRC
```

Los efectos mutantes se ejecutan vía `approval_service → execute_tool(agent=system, post_approval=True)`, no outbox.
