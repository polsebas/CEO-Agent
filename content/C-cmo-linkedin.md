# Demo C — CMO: campaña LinkedIn (fase 2)

**Estado:** 🚧 Bloqueado hasta validar [Demo A — CFO](./A-cfo-compensation.md) end-to-end en UI.

**Rol:** pieza fuerte para LinkedIn — muestra gasto de marketing con approval obligatorio.

## Narrativa planeada

1. CMO agent consulta `get_analytics_summary` (orgánico LinkedIn: impresiones, CTR, CAC histórico).
2. Detecta oportunidad: boost de post corporativo / lead gen B2B flota.
3. `propose_campaign` genera borrador (`side_effect_level` PLAN → approval).
4. CEO consolida y eleva `launch_linkedin_campaign` como `EXECUTE_CRITICAL`.
5. Founder aprueba presupuesto y segmentación en `/approvals`.
6. Post-approval: stub ejecuta “campaña publicada” con `approval_id` en auditoría.

## Por qué después de A

| A (CFO) | C (CMO) |
|---------|---------|
| Un agente + decisión financiera directa | CMO + CEO + presupuesto visible |
| Descuento en reserva existente | Gasto nuevo + creatividad |
| Valida el patrón approval → execute | Reutiliza el mismo patrón ya demostrado |

## Entregables previstos (no implementados aún)

- `demo/linkedin_campaign_request.json`
- Extensión `prompts/cmo_agent_v1.md` (contexto FacilRentaCar B2B)
- `tests/gate/test_scenario_linkedin_campaign.py`
- `python scripts/seed_demo.py --scenario linkedin`
- Guion demo + post LinkedIn largo (case study)

## Borrador ángulo LinkedIn (C — cuando esté listo)

> Tu CMO agent no “publica en LinkedIn”.  
> Propone campaña con CAC/LTV, el runtime eleva approval, y vos autorizás el spend.  
> Marketing gobernado en un runtime que se comporta como motor transaccional, no como chat.

## Checklist de desbloqueo

- [ ] Demo A presentada E2E en UI sin atajos
- [ ] `test_compensation_approved_executes_with_approval_id` verde en CI
- [ ] Stakeholder confirma que entiende reviewer vs operator
