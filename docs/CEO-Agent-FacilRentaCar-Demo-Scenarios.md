# CEO-Agent × FacilRentaCar — Escenarios de Integración Demo

> **Destinatario:** Agente de desarrollo (Cursor AI)
> **Propósito:** Este documento describe 4 escenarios narrativos de integración entre CEO-Agent y FacilRentaCar/Automotriz Rentals. Cada escenario es un plan de desarrollo autocontenido que debés implementar siguiendo los contratos arquitectónicos del runtime. Leé este documento completo antes de tocar código.

---

## Contexto arquitectónico obligatorio

Antes de implementar cualquier escenario, internalizá estos invariantes del runtime:

**CEO-Agent** es un runtime cognitivo gobernado. El flujo canónico es:

```
Evento de entrada (JSON fixture)
  → Preprocessor 4-tier (core/preprocessor.py)
  → ManualOrchestrator (core/orchestrator.py)
  → PolicyEngine (core/policy.py)
  → StructuredAgentRunner → Agno agent.arun()
  → DecisionRecord generado
  → ApprovalService eleva propuesta (core/approval_service.py)
  → Founder aprueba/rechaza desde UI (/approvals)
  → persist_runtime_tx: decision + effect + outbox en una TX
  → Efecto ejecutado (tool call al MCP de FacilRentaCar)
```

**Regla de oro:** Ningún efecto sobre FacilRentaCar se ejecuta sin `ApprovalBinding` confirmado. El `side_effect_level` de toda `ActionProposal` dirigida al MCP debe ser `"EXECUTE_CRITICAL"`.

**MCP de FacilRentaCar** ya existe como wrapper HTTP de la API. Se registra en `tools/registry.py` como herramienta externa. El `ToolRouter` (tools/router.py) despacha las llamadas.

**Schemas que usarás en todos los escenarios:**
- `schemas/approvals.py` — `ActionProposal`, `ImmutableActionProposal`, `Approval`, `ApprovalBinding`
- `schemas/decisions.py` — `DecisionRecord`, `CalibratedConfidence`
- `schemas/world.py` — `WorldState` (extenderás `Company` con campos de FacilRentaCar)
- `schemas/responses/__init__.py` — `CEOResponse`, `CFOResponse`, `COOResponse`, `CMOResponse`

**Tests:** Cada escenario requiere al mínimo un test gate en `tests/gate/` y un fixture en `demo/`. Ejecutá `./scripts/ci-local.sh` antes de cada commit. No commitees si hay tests en rojo.

---

## Escenario 1 — Extensión de reserva con descuento de compensación

### Narrativa

Un cliente con una reserva activa reporta un desperfecto menor en el vehículo durante el período de renta. El sistema FacilRentaCar genera un evento de incidencia. El CEO-Agent detecta el evento, el CFO agent calcula el descuento de compensación apropiado según la política vigente, y el CEO agent eleva una propuesta de compensación al founder. El founder aprueba o rechaza desde la consola operacional. Solo tras el approval, el efecto se ejecuta contra la API de FacilRentaCar.

**Valor demostrado:** governance sobre una decisión financiera directa, trazabilidad completa del razonamiento, rollback explícito si se rechaza.

---

### Plan de desarrollo

#### Paso 1 — Fixture de entrada (`demo/compensation_request.json`)

Creá el archivo `demo/compensation_request.json` con esta estructura:

```json
{
  "event_type": "vehicle_incident_reported",
  "correlation_id": "demo-compensation-001",
  "reservation_id": "RES-2024-0891",
  "client_id": "CLI-4421",
  "client_name": "Empresa XYZ S.A.",
  "vehicle_id": "VEH-112",
  "vehicle_model": "Toyota Hilux 2023",
  "incident_description": "Ruido inusual en transmisión reportado por el cliente durante el período de renta",
  "incident_severity": "minor",
  "reservation_amount_ars": 185000.0,
  "reservation_start": "2024-12-01",
  "reservation_end": "2024-12-07",
  "days_remaining": 3,
  "policy_max_compensation_pct": 0.20,
  "requested_by": "founder"
}
```

#### Paso 2 — Extensión del WorldState (`schemas/world.py`)

Agregá al modelo `Company` los campos necesarios para FacilRentaCar sin romper el `default_world_state()` existente. Creá una subclase o usá campos opcionales:

```python
class FacilRentaCarCompany(Company):
    active_reservations: int = 0
    fleet_size: int = 0
    pending_incidents: int = 0
    compensation_policy_max_pct: float = 0.20
```

Si preferís no subclasear, agregá los campos como `Optional` directamente en `Company` con `default=None`.

#### Paso 3 — Tools MCP para este escenario (`tools/stubs/facilrentacar.py`)

Creá `tools/stubs/facilrentacar.py` con las herramientas que el CFO y CEO agents necesitan para este escenario. Estas tools llaman al MCP existente vía HTTP:

```python
# tools/stubs/facilrentacar.py

async def get_reservation_detail(reservation_id: str) -> dict:
    """Obtiene detalle completo de una reserva activa."""
    # Llamada al MCP: GET /reservas/{reservation_id}
    ...

async def get_compensation_policy() -> dict:
    """Obtiene la política de compensación vigente."""
    # Llamada al MCP: GET /politicas/compensacion
    ...

async def apply_reservation_discount(
    reservation_id: str,
    discount_pct: float,
    reason: str,
    approval_id: str,
) -> dict:
    """Aplica descuento a una reserva. Requiere approval_id válido."""
    # Llamada al MCP: POST /reservas/{reservation_id}/descuento
    # IMPORTANTE: este método solo se llama desde el outbox processor
    # nunca directamente desde el agente
    ...
```

Registrá estas tools en `tools/registry.py` bajo el namespace `"facilrentacar"`.

#### Paso 4 — Prompt del CFO agent (`prompts/cfo_agent_v1.md`)

Reemplazá o extendé el prompt existente para incluir instrucciones específicas de compensación:

```markdown
Sos el CFO Agent de FacilRentaCar. Cuando recibís un evento de incidencia de vehículo:

1. Llamá a `get_reservation_detail` para obtener el monto y días restantes
2. Llamá a `get_compensation_policy` para conocer el máximo permitido
3. Calculá el descuento propuesto: considerá severidad del incidente, días restantes y monto total
4. Retorná un `CFOResponse` con:
   - `recommended_action`: "apply_discount"
   - `discount_pct`: porcentaje recomendado (nunca superar `policy_max_compensation_pct`)
   - `discount_amount_ars`: monto en pesos
   - `justification`: razón del cálculo
   - `confidence`: score entre 0.0 y 1.0
   - `risk_flags`: lista de flags si el descuento supera el 15%
```

#### Paso 5 — Orquestación en `core/orchestrator.py`

Localizá el método de dispatch del `ManualOrchestrator` y agregá el handler para `event_type == "vehicle_incident_reported"`:

```python
async def _handle_vehicle_incident(self, event: dict) -> DecisionRecord:
    # 1. Invocar CFO agent para calcular compensación
    cfo_response = await self._run_agent("cfo", event)
    
    # 2. Invocar CEO agent para decisión final
    ceo_response = await self._run_agent("ceo", {
        **event,
        "cfo_recommendation": cfo_response.model_dump()
    })
    
    # 3. Construir ActionProposal
    proposal = ActionProposal(
        task_id=...,
        agent="ceo",
        action="apply_reservation_discount",
        side_effect_level="EXECUTE_CRITICAL",
        impact_summary=f"Descuento {cfo_response.discount_pct*100:.0f}% sobre reserva {event['reservation_id']} — ARS {cfo_response.discount_amount_ars:,.0f}",
        rollback_strategy="No se aplica descuento. La reserva continúa con el monto original.",
        estimated_cost_usd=cfo_response.discount_amount_ars / 1000,  # rough USD
    )
    
    # 4. Elevar a approval service
    await self.approval_service.create(proposal, ...)
    
    # 5. Persistir DecisionRecord
    ...
```

#### Paso 6 — Outbox effect (`workers/outbox_processor.py`)

Agregá el handler del efecto en el outbox processor. Este es el único lugar donde se llama `apply_reservation_discount`:

```python
case "apply_reservation_discount":
    await facilrentacar_tools.apply_reservation_discount(
        reservation_id=payload["reservation_id"],
        discount_pct=payload["discount_pct"],
        reason=payload["reason"],
        approval_id=payload["approval_id"],
    )
```

#### Paso 7 — Script de demo (`scripts/seed_demo.py`)

Agregá una función `seed_compensation_scenario()` que:
1. Limpia el estado previo
2. Carga `demo/compensation_request.json`
3. Crea la sesión y dispara el evento via `POST /api/run`
4. Imprime la URL de la consola donde el founder puede aprobar

#### Paso 8 — Test gate (`tests/gate/test_scenario_compensation.py`)

```python
@pytest.mark.asyncio
async def test_compensation_requires_approval_before_effect():
    """El descuento NO debe aplicarse antes del approval."""
    # Disparar evento → verificar que outbox NO tiene efecto pendiente
    # antes del approval
    ...

async def test_compensation_approval_creates_binding():
    """Aprobar genera un ApprovalBinding con checksum válido."""
    ...

async def test_compensation_rejection_leaves_no_effect():
    """Rechazar no genera ningún efecto en outbox."""
    ...
```

---

## Escenario 3 — Override de política de cancelación para cliente corporativo

### Narrativa

Una empresa cliente con múltiples reservas activas solicita cancelar todas fuera del plazo establecido por la política, alegando fuerza mayor (evento extraordinario documentado). El CFO agent calcula el impacto financiero de dos opciones: reembolso completo vs aplicar penalidad contractual. El CEO agent analiza el valor del cliente a largo plazo y recomienda una posición. La decisión se eleva al founder con ambas opciones explícitas, sus impactos y la recomendación del CEO. El founder decide.

**Valor demostrado:** razonamiento multi-opción con trade-off explícito, governance sobre excepción contractual, trazabilidad de por qué se hizo una excepción.

---

### Plan de desarrollo

#### Paso 1 — Fixture de entrada (`demo/cancellation_override.json`)

```json
{
  "event_type": "corporate_cancellation_override_request",
  "correlation_id": "demo-cancellation-001",
  "client_id": "CORP-0088",
  "client_name": "Grupo Constructor Mendoza S.A.",
  "client_history_months": 18,
  "client_total_reservations_ytd": 34,
  "client_revenue_ytd_ars": 2840000.0,
  "reservations_to_cancel": [
    {"id": "RES-2024-0901", "amount_ars": 220000.0, "start": "2024-12-10"},
    {"id": "RES-2024-0902", "amount_ars": 195000.0, "start": "2024-12-12"},
    {"id": "RES-2024-0903", "amount_ars": 210000.0, "start": "2024-12-15"}
  ],
  "total_cancellation_amount_ars": 625000.0,
  "cancellation_policy_penalty_pct": 0.30,
  "force_majeure_document": "nota_directorio_2024_12_01.pdf",
  "requested_by": "founder"
}
```

#### Paso 2 — Tools MCP para este escenario

Agregá a `tools/stubs/facilrentacar.py`:

```python
async def get_client_history(client_id: str) -> dict:
    """Historial completo del cliente: reservas, pagos, incidentes."""
    # Llamada al MCP: GET /clientes/{client_id}/historial
    ...

async def get_cancellation_policy() -> dict:
    """Política de cancelación vigente con tramos y penalidades."""
    # Llamada al MCP: GET /politicas/cancelacion
    ...

async def execute_cancellation_override(
    client_id: str,
    reservation_ids: list[str],
    override_type: str,  # "full_refund" | "apply_penalty"
    override_reason: str,
    approval_id: str,
) -> dict:
    """Ejecuta la cancelación con el tipo de override aprobado."""
    # Llamada al MCP: POST /reservas/cancelacion-masiva
    # Solo llamar desde outbox processor
    ...
```

#### Paso 3 — Output schema del CEO para este escenario

En `schemas/responses/__init__.py`, extendé `CEOResponse` o creá un tipo específico que capture las dos opciones:

```python
class CancellationOption(BaseModel):
    option_id: str  # "full_refund" | "apply_penalty"
    description: str
    financial_impact_ars: float
    client_relationship_impact: str  # "positive" | "neutral" | "negative"
    recommendation_score: float  # 0.0 a 1.0

class CEOCancellationResponse(BaseModel):
    options: list[CancellationOption]
    recommended_option: str
    reasoning: str
    client_ltv_estimate_ars: float
    confidence: float
    risk_flags: list[str]
```

#### Paso 4 — Prompt del CEO agent para override (`prompts/ceo_agent_v1.md`)

Agregá una sección de instrucciones para overrides corporativos:

```markdown
## Override de cancelación corporativa

Cuando recibís un evento `corporate_cancellation_override_request`:

1. Llamá a `get_client_history` para evaluar el valor histórico del cliente
2. Llamá a `get_cancellation_policy` para conocer la penalidad contractual
3. Calculá el LTV estimado del cliente (revenue_ytd / meses * 24)
4. Construí dos opciones explícitas: reembolso completo vs penalidad
5. Recomendá la opción con mayor valor esperado a largo plazo
6. Si el LTV supera 10x el monto de la penalidad, recomendá reembolso completo
7. Siempre incluí risk_flags si el precedente puede generar otras solicitudes similares
```

#### Paso 5 — Impact summary enriquecido en `ActionProposal`

Para este escenario el `impact_summary` debe ser especialmente descriptivo porque el founder necesita toda la información en la pantalla de approval:

```python
impact_summary = (
    f"OVERRIDE CANCELACIÓN — {event['client_name']}\n"
    f"Opción recomendada: {ceo_response.recommended_option}\n"
    f"Monto en juego: ARS {event['total_cancellation_amount_ars']:,.0f}\n"
    f"Penalidad contractual: ARS {penalty_amount:,.0f}\n"
    f"LTV estimado cliente: ARS {ceo_response.client_ltv_estimate_ars:,.0f}\n"
    f"Razón: {ceo_response.reasoning}"
)
```

#### Paso 6 — Extensión de la UI de approvals (`ui/templates/approvals.html`)

Para este escenario, la pantalla de approval debe mostrar ambas opciones como botones distintos, no solo aprobar/rechazar. Extendé el template para que cuando `side_effect_level == "EXECUTE_CRITICAL"` y el action sea `"execute_cancellation_override"`, se rendericen las opciones desde `parameters`:

```html
<!-- Dentro del loop de approvals pendientes -->
{% if approval.proposal.action == "execute_cancellation_override" %}
  <div class="options-grid">
    {% for option in approval.proposal.parameters.options %}
    <button hx-post="/approvals/{{ approval.id }}/approve"
            hx-vals='{"selected_option": "{{ option.option_id }}"}'>
      {{ option.description }} — ARS {{ option.financial_impact_ars | formato_ars }}
    </button>
    {% endfor %}
  </div>
{% endif %}
```

#### Paso 7 — Test gate (`tests/gate/test_scenario_cancellation_override.py`)

```python
async def test_override_requires_founder_approval():
    """Ninguna cancelación se ejecuta sin ApprovalBinding."""
    ...

async def test_both_options_present_in_proposal():
    """La propuesta siempre contiene exactamente 2 opciones."""
    ...

async def test_rejection_preserves_original_policy():
    """Si se rechaza el override, la política de penalidad se aplica normalmente."""
    ...

async def test_approved_option_matches_outbox_payload():
    """El outbox payload contiene el option_id aprobado por el founder."""
    ...
```

---

## Escenario 4 — Alerta de ocupación crítica — ajuste de tarifas

### Narrativa

El sistema monitorea la ocupación de la flota en tiempo real. Cuando la ocupación supera el 90% en un período proyectado, el COO agent detecta la escasez y el CFO agent propone un ajuste de tarifas temporal para maximizar revenue. El CEO agent decide el rango de precios y el período de vigencia, y eleva la propuesta al founder. El founder aprueba el rango (puede modificar los límites antes de aprobar). Solo tras el approval, las nuevas tarifas se publican en el sistema.

**Valor demostrado:** decisión proactiva (no reactiva), cognición sobre métricas en tiempo real, governance sobre pricing con impacto directo en revenue.

---

### Plan de desarrollo

#### Paso 1 — Fixture de entrada (`demo/fleet_occupancy_alert.json`)

```json
{
  "event_type": "fleet_occupancy_critical",
  "correlation_id": "demo-occupancy-001",
  "alert_triggered_at": "2024-12-05T09:00:00Z",
  "current_occupancy_pct": 0.93,
  "threshold_pct": 0.90,
  "projection_period_days": 14,
  "period_start": "2024-12-20",
  "period_end": "2025-01-03",
  "fleet_total": 45,
  "fleet_available": 3,
  "current_base_rate_ars_per_day": 28000.0,
  "market_comparable_rate_ars_per_day": 35000.0,
  "max_allowed_increase_pct": 0.35,
  "categories_affected": ["SUV", "Pickup"],
  "requested_by": "system"
}
```

#### Paso 2 — Tools MCP para este escenario

Agregá a `tools/stubs/facilrentacar.py`:

```python
async def get_fleet_occupancy(period_start: str, period_end: str) -> dict:
    """Ocupación proyectada de la flota por categoría."""
    # Llamada al MCP: GET /flota/ocupacion?desde=...&hasta=...
    ...

async def get_current_rates(categories: list[str]) -> dict:
    """Tarifas vigentes por categoría de vehículo."""
    # Llamada al MCP: GET /tarifas/vigentes
    ...

async def get_market_rates(categories: list[str]) -> dict:
    """Tarifas de mercado comparables (benchmarking)."""
    # Llamada al MCP: GET /tarifas/mercado
    ...

async def publish_rate_adjustment(
    categories: list[str],
    new_rate_ars_per_day: float,
    valid_from: str,
    valid_to: str,
    adjustment_reason: str,
    approval_id: str,
) -> dict:
    """Publica nuevas tarifas en el sistema. Solo desde outbox processor."""
    # Llamada al MCP: POST /tarifas/ajuste
    ...
```

#### Paso 3 — Orquestación multi-agente COO → CFO → CEO

Este es el escenario con mayor profundidad de orquestación. En `ManualOrchestrator`:

```python
async def _handle_fleet_occupancy_critical(self, event: dict) -> DecisionRecord:
    # Paso 1: COO evalúa la situación operacional
    coo_response = await self._run_agent("coo", event)
    # coo_response: análisis de disponibilidad, proyección de demanda
    
    # Paso 2: CFO calcula el rango de precios óptimo
    cfo_response = await self._run_agent("cfo", {
        **event,
        "coo_analysis": coo_response.model_dump()
    })
    # cfo_response: min_rate, max_rate, expected_revenue_uplift
    
    # Paso 3: CEO decide el rango final y período
    ceo_response = await self._run_agent("ceo", {
        **event,
        "coo_analysis": coo_response.model_dump(),
        "cfo_proposal": cfo_response.model_dump()
    })
    # ceo_response: approved_rate, period, rationale
    
    # Paso 4: Construir proposal con rango explícito
    proposal = ActionProposal(
        action="publish_rate_adjustment",
        side_effect_level="EXECUTE_CRITICAL",
        impact_summary=...,
        rollback_strategy="Revertir a tarifas anteriores: ARS 28.000/día",
        estimated_cost_usd=0.0,  # es revenue positivo
    )
```

#### Paso 4 — Prompt del COO agent (`prompts/coo_agent_v1.md`)

```markdown
Sos el COO Agent de FacilRentaCar. Para alertas de ocupación crítica:

1. Llamá a `get_fleet_occupancy` para el período proyectado
2. Identificá las categorías con mayor escasez
3. Proyectá la demanda no satisfecha si no se toman acciones
4. Retorná un `COOResponse` con:
   - `occupancy_analysis`: resumen por categoría
   - `demand_projection`: reservas esperadas vs disponibilidad
   - `operational_risk`: "low" | "medium" | "high"
   - `recommended_action`: "rate_adjustment" | "waitlist" | "fleet_expansion"
```

#### Paso 5 — Prompt del CFO agent para pricing (`prompts/cfo_agent_v1.md`)

Agregá sección de pricing dinámico:

```markdown
## Pricing dinámico por ocupación

Cuando recibís un análisis de COO con `recommended_action == "rate_adjustment"`:

1. Llamá a `get_current_rates` para la tarifa base actual
2. Llamá a `get_market_rates` para el benchmark competitivo
3. Calculá el rango óptimo: mínimo = tarifa actual * 1.10, máximo = min(mercado, tarifa_actual * max_pct)
4. Estimá el uplift de revenue: (nueva_tarifa - tarifa_actual) * reservas_proyectadas
5. Nunca superar `max_allowed_increase_pct` del evento
6. Retorná CFOResponse con min_rate, max_rate, recommended_rate, revenue_uplift_ars
```

#### Paso 6 — Campo `parameters` enriquecido en `ImmutableActionProposal`

Para este escenario, el `parameters` de la propuesta inmutable debe contener todo lo necesario para que el outbox ejecute sin ambigüedad:

```python
parameters = {
    "categories": ceo_response.categories,
    "new_rate_ars_per_day": ceo_response.approved_rate,
    "valid_from": event["period_start"],
    "valid_to": event["period_end"],
    "adjustment_reason": f"Ocupación crítica {event['current_occupancy_pct']*100:.0f}%",
    "previous_rate_ars_per_day": event["current_base_rate_ars_per_day"],
    "approval_id": None,  # se completa al momento del approval
}
```

#### Paso 7 — Test gate (`tests/gate/test_scenario_rate_adjustment.py`)

```python
async def test_rate_never_exceeds_max_allowed():
    """La tarifa propuesta nunca supera max_allowed_increase_pct."""
    ...

async def test_multi_agent_chain_completes():
    """La cadena COO → CFO → CEO produce DecisionRecord válido."""
    ...

async def test_rate_published_only_after_approval():
    """Las nuevas tarifas no se publican hasta recibir ApprovalBinding."""
    ...

async def test_rollback_strategy_is_explicit():
    """El rollback_strategy en la propuesta referencia la tarifa anterior."""
    ...
```

---

## Escenario 5 — Reactivación de flota tras mantenimiento

### Narrativa

Varios vehículos regresan de mantenimiento preventivo. El sistema FacilRentaCar genera un evento batch. El COO agent evalúa la disponibilidad actual por sucursal, el volumen de reservas pendientes de asignación y la carga operacional del equipo. El CEO agent decide cuántos vehículos reactivar en cada sucursal y en qué orden de prioridad. La decisión se eleva al founder para approval antes de publicar los vehículos como disponibles. Tras el approval, el outbox marca los vehículos como disponibles en la API.

**Valor demostrado:** decisión operacional con múltiples entidades, distribución geográfica explícita, governance sobre disponibilidad de inventario físico.

---

### Plan de desarrollo

#### Paso 1 — Fixture de entrada (`demo/fleet_reactivation.json`)

```json
{
  "event_type": "fleet_maintenance_completed",
  "correlation_id": "demo-reactivation-001",
  "completed_at": "2024-12-05T08:00:00Z",
  "vehicles_returned": [
    {"id": "VEH-205", "model": "Ford Ranger 2022", "category": "Pickup", "branch": "Mendoza Centro"},
    {"id": "VEH-206", "model": "Ford Ranger 2022", "category": "Pickup", "branch": "Mendoza Centro"},
    {"id": "VEH-301", "model": "Toyota Corolla 2023", "category": "Sedan", "branch": "San Rafael"},
    {"id": "VEH-302", "model": "Toyota Corolla 2023", "category": "Sedan", "branch": "San Rafael"},
    {"id": "VEH-401", "model": "Chevrolet Tracker 2023", "category": "SUV", "branch": "Malargüe"}
  ],
  "total_vehicles": 5,
  "branches_affected": ["Mendoza Centro", "San Rafael", "Malargüe"],
  "pending_reservations_without_vehicle": 7,
  "requested_by": "system"
}
```

#### Paso 2 — Tools MCP para este escenario

Agregá a `tools/stubs/facilrentacar.py`:

```python
async def get_branch_status(branch_name: str) -> dict:
    """Estado actual de una sucursal: staff disponible, capacidad operacional."""
    # Llamada al MCP: GET /sucursales/{branch_name}/estado
    ...

async def get_pending_reservations_by_branch(branch_name: str) -> dict:
    """Reservas pendientes de asignación en una sucursal."""
    # Llamada al MCP: GET /sucursales/{branch_name}/reservas-pendientes
    ...

async def activate_vehicles(
    vehicle_ids: list[str],
    activation_notes: str,
    approval_id: str,
) -> dict:
    """Marca vehículos como disponibles en el sistema. Solo desde outbox."""
    # Llamada al MCP: POST /flota/activar
    # Payload: {"vehicle_ids": [...], "approval_id": "..."}
    ...
```

#### Paso 3 — Output schema del COO para reactivación

En `schemas/responses/__init__.py`:

```python
class VehicleActivationPriority(BaseModel):
    vehicle_id: str
    branch: str
    priority: int  # 1 = más urgente
    reason: str

class COOReactivationResponse(BaseModel):
    activation_plan: list[VehicleActivationPriority]
    vehicles_to_activate_now: list[str]
    vehicles_to_hold: list[str]
    hold_reason: str | None
    operational_notes: str
    confidence: float
```

#### Paso 4 — Prompt del COO agent para reactivación (`prompts/coo_agent_v1.md`)

```markdown
## Reactivación de flota post-mantenimiento

Cuando recibís un evento `fleet_maintenance_completed`:

1. Para cada sucursal afectada, llamá a `get_branch_status` y `get_pending_reservations_by_branch`
2. Priorizá la reactivación donde hay más reservas pendientes sin vehículo
3. Si una sucursal tiene baja carga operacional de staff, marcá vehículos en `vehicles_to_hold`
4. Retorná un plan ordenado por prioridad con justificación por vehículo
5. Nunca recomendés activar más vehículos de los que el staff puede procesar en el día
```

#### Paso 5 — Propuesta con lista explícita de vehículos

En la `ActionProposal` de este escenario, `parameters` debe ser auditabie:

```python
proposal = ActionProposal(
    action="activate_vehicles",
    side_effect_level="EXECUTE_CRITICAL",
    impact_summary=(
        f"REACTIVACIÓN FLOTA — {len(vehicles_to_activate)} vehículos\n"
        f"Sucursales: {', '.join(branches)}\n"
        f"Reservas pendientes que se satisfacen: {pending_count}\n"
        f"Vehículos en hold: {len(vehicles_to_hold)} ({hold_reason})"
    ),
    rollback_strategy="Mantener todos los vehículos en estado 'en_revision'. No se publica disponibilidad.",
)
```

#### Paso 6 — Test gate (`tests/gate/test_scenario_fleet_reactivation.py`)

```python
async def test_activation_requires_approval():
    """Los vehículos no se marcan disponibles sin ApprovalBinding."""
    ...

async def test_hold_vehicles_not_in_outbox():
    """Los vehículos en hold no aparecen en el payload del outbox."""
    ...

async def test_priority_order_matches_pending_reservations():
    """Las sucursales con más reservas pendientes tienen mayor prioridad."""
    ...

async def test_activation_payload_matches_approved_list():
    """El outbox payload contiene exactamente los vehicle_ids aprobados."""
    ...
```

---

## Instrucciones de implementación para el agente de Cursor

### Orden de implementación recomendado

1. **Primero:** Escenario 1 (compensación) — es el más simple, un solo agente activo (CFO → CEO), introduce el patrón base.
2. **Segundo:** Escenario 5 (reactivación) — introduce el COO agent y la lógica multi-entidad.
3. **Tercero:** Escenario 4 (tarifas) — introduce la cadena completa COO → CFO → CEO.
4. **Cuarto:** Escenario 3 (override corporativo) — introduce opciones múltiples en el approval.

### Reglas de implementación no negociables

- **No inventés schemas nuevos** si los existentes en `schemas/` alcanzan. Extendé con campos `Optional` antes de crear nuevos modelos.
- **Toda tool que produce side effects** debe tener `approval_id` como parámetro requerido y validarlo antes de ejecutar.
- **Los prompts de los agentes** deben producir siempre un `output_schema` tipado. Nunca texto libre.
- **Cada fixture en `demo/`** debe tener un test gate correspondiente en `tests/gate/`.
- **El `rollback_strategy`** en cada `ActionProposal` no puede ser `None` cuando `side_effect_level == "EXECUTE_CRITICAL"`.
- **Ejecutá `./scripts/ci-local.sh` antes de cada commit.** Si hay rojo, no commiteás.

### Archivos que no debés modificar sin revisar primero `docs/runtime_invariants.md`

- `core/persistence.py`
- `core/approval_service.py`
- `core/orchestrator.py` (modificar, sí; pero entendiendo el contrato primero)
- `schemas/approvals.py`
- `schemas/decisions.py`

### Cómo verificar que un escenario funciona end-to-end

```bash
# 1. Levantar infraestructura
docker compose up -d

# 2. Seedear el escenario específico
python scripts/seed_demo.py --scenario compensation  # o cancellation | occupancy | reactivation

# 3. Abrir la consola operacional
open http://localhost:8000/ui/approvals

# 4. Aprobar/rechazar desde la UI y verificar que el outbox procesa el efecto

# 5. Verificar el replay de la sesión en /ui/sessions
```

---

*Documento generado el 2025-05-30. Versión del runtime: CEO-Agent 0.1.0 (RRM-3). MCP FacilRentaCar: wrapper existente vía HTTP.*
