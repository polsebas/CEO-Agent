# Demo A — CFO: compensación gobernada (FacilRentaCar)

**Duración:** ~5 min · **Audiencia:** founder / reviewer / stakeholder no técnico  
**Objetivo:** demostrar approval flow **end-to-end** antes de escalar a C (CMO LinkedIn).

## Por qué arrancamos acá

- Un solo agente financiero activo (CFO → CEO), sin cadena COO.
- Efecto mutante claro: descuento en reserva (`EXECUTE_CRITICAL`).
- Gate automatizado: `tests/gate/test_scenario_compensation.py` (4 tests + integridad governance).

## Prerrequisitos

```bash
git checkout demo/facilrentacar
pip install -e ".[dev]"
export AUTH_DISABLED=true   # dev local
python scripts/seed_demo.py --scenario compensation
uvicorn api.main:app --reload --app-dir .
```

## Guión E2E (consola operacional)

### 1. Contexto (operator, 30 s)

1. Login **operator** → `http://localhost:8000/login`
2. Abrir sesión seed:
   - `http://localhost:8000/sessions/demo-compensation-001?correlation_id=demo-compensation-001`
3. Narrar el incidente: *Empresa XYZ, Hilux en renta, ruido en transmisión, severidad menor.*
4. Mostrar **Timeline**: evento → CFO analiza → CEO eleva propuesta.
5. Sidebar: resumen humano (descuento %, ARS, justificación).

**Mensaje clave:** el agente **recomienda**; no ejecuta el descuento solo.

### 2. Governance (reviewer, 2 min)

1. Cerrar sesión operator o usar ventana incógnito.
2. Login **reviewer** → `http://localhost:8000/approvals`
3. Tarjeta pendiente: *Compensación RES-2024-0891* · `EXECUTE_CRITICAL`
4. Leer `impact_summary` y parámetros (%, monto ARS, rollback).
5. **Aprobar** → confirmar redirect / éxito.
6. Volver a la sesión (cualquier rol con acceso) y mostrar efecto en timeline.

**Mensaje clave:** sin `ApprovalBinding` no hay descuento en FacilRentaCar.

### 3. Variante rechazo (opcional, 1 min)

Re-seed y repetir con **Rechazar** + motivo. Mostrar que no hay efecto `complete` en la correlación.

```bash
python scripts/seed_demo.py --scenario compensation
```

## Qué NO mostrar

- JSON crudo del runtime ni logs OTel.
- Bypass de `/approvals` vía API (salvo demo técnica interna).

## Criterio de cierre (A validado)

- [ ] Seed crea approval pendiente (`approval_id` en stdout).
- [ ] Reviewer aprueba desde UI sin error.
- [ ] Timeline de sesión refleja ejecución post-approval.
- [ ] `pytest tests/vertical_slice/` → 16 passed.
- [ ] `pytest tests/gate/test_scenario_compensation.py` → 4 passed.

Cuando los cinco ítems están verdes → habilitar trabajo en **[C — CMO LinkedIn](./C-cmo-linkedin.md)**.

## Borrador LinkedIn (pieza corta — A)

> Un cliente reporta un desperfecto menor en un vehículo de renta.  
> El CFO agent calcula el descuento dentro de política; el CEO agent eleva la propuesta.  
> El founder aprueba en consola — **solo entonces** se aplica el crédito.  
> Governance + trazabilidad, no chatbot que “decide solo”.  
> #AI #Governance #FacilRentaCar
