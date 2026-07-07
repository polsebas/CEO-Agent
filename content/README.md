# Demo content — orden de validación

Contenido narrativo y guiones para stakeholders. **No reemplaza** los tests gate; los complementa.

| ID | Agente | Escenario | Estado | Doc |
|----|--------|-----------|--------|-----|
| **A** | CFO | Compensación por incidencia (FacilRentaCar) | **Activo** — validar approval E2E primero | [A-cfo-compensation.md](./A-cfo-compensation.md) |
| B | COO | Reactivación de flota | Pendiente (post-A) | `docs/FACILRENTACAR_DEMO.md` |
| **C** | CMO | Campaña LinkedIn (pieza fuerte) | Código listo; **presentación** bloqueada hasta A E2E en UI | [C-cmo-linkedin.md](./C-cmo-linkedin.md) |

## Gate antes de presentar

```bash
OTEL_SDK_DISABLED=true .venv/bin/python -m pytest tests/vertical_slice/ -q
OTEL_SDK_DISABLED=true .venv/bin/python -m pytest tests/gate/test_scenario_compensation.py -q
OTEL_SDK_DISABLED=true .venv/bin/python -m pytest tests/gate/test_scenario_linkedin_campaign.py -q
python scripts/seed_demo.py --scenario compensation
```

## Rama

Todo el contenido FacilRentaCar vive en `demo/facilrentacar`, no en `main`.
