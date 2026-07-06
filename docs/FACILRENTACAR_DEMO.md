# FacilRentaCar — Demo operacional gobernado

Integración demo entre CEO-Agent y FacilRentaCar con 4 escenarios gobernados (`EXECUTE_CRITICAL`).

## Arquitectura de ejecución

Los efectos mutantes **no** pasan por outbox. Flujo canónico:

```text
Evento demo (JSON) → run_domain_event → agents (CFO/COO/CEO) → prepare_approval
→ Reviewer en /approvals → execute_approved_action (agent_id=system, post_approval=True) → tool MCP/stub
```

## Convención session_id / correlation_id

Para eventos de dominio FacilRentaCar, **`session_id` y `correlation_id` deben coincidir** (ej. `demo-compensation-001`).  
`prepare_approval` persiste con ese `session_id` canónico para trazabilidad replay.

## Escenarios

| Comando seed | Qué demuestra | TTL approval |
|--------------|---------------|--------------|
| `--scenario compensation` | Descuento por incidencia | 24h |
| `--scenario reactivation` | Activación de flota | 24h |
| `--scenario occupancy` | Tarifas dinámicas COO→CFO→CEO | 2h |
| `--scenario cancellation` | Override con dropdown de opciones | 2h |

## Quick start

```bash
python scripts/seed_demo.py --scenario compensation
uvicorn api.main:app --reload
# reviewer → http://localhost:8000/approvals
# sesión → http://localhost:8000/sessions/demo-compensation-001?correlation_id=demo-compensation-001
```

## Escenario 3 — contrato dropdown

- `prepare_approval`: `parameters.options[]` + `recommended_option` (inmutable, entra en checksum)
- UI/API: reviewer elige `selected_option` / `override_type` **obligatorio** antes de aprobar
- `execute_approved_action`: solo `override_type` está en la whitelist de `execution_overrides`; el resto se rechaza

## Governance hardening

| Control | Comportamiento |
|---------|----------------|
| `execution_overrides` | Whitelist por acción; tampering post-binding → `ValueError` |
| Ejecución fallida | `ApprovalStatus.EXECUTION_FAILED` (no `APPROVED`) |
| `agent_id=system` | Solo con `post_approval=True` desde `approval_service` |
| `rollback_strategy` | Campo inmutable en `ImmutableActionProposal` |

## Tests

```bash
pytest tests/gate/test_governance_execution_integrity.py -q
pytest tests/gate/test_scenario_*.py
pytest -m smoke tests/smoke/test_seed_scenarios.py
```

Fixtures canónicos: `tools/stubs/facilrentacar_contracts.py`

Referencia completa: [`CEO-Agent-FacilRentaCar-Demo-Scenarios.md`](CEO-Agent-FacilRentaCar-Demo-Scenarios.md)
