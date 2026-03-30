# ARTIFACT: G2-QIKI-009 — Thermal Follow-up Constraint Acceptance

Статус: PASS  
Дата: 2026-03-06

## Что доказано

1. После hostile burst thermal contour оставляет отдельный системный след.
2. Этот след виден в ORION V через существующий `F2/Thermal`.
3. Тот же hostile follow-up меняется по текущему thermal-state.

## Выбранный truth-source

- `thermal.nodes[*].warned`
- `thermal.nodes[*].tripped`

Канонический `reason_code`:
- `COMBAT_ENTRY_THERMAL_WARN`

## Проверки

### Ruff

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  ruff check \
  src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tools/orion_v_qiki_thermal_followup_constraint_smoke.py
```

Результат:
- `All checks passed!`

### Unit

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/unit/test_qiki_orion_intents_service.py
```

Результат:
- `33 passed`

### Runtime proof

```bash
bash scripts/prove_orion_v_qiki_thermal_followup_constraint.sh
```

Результат:

```text
OK: orion_v_qiki_thermal_followup_constraint_smoke
THERMAL_CODE=COMBAT_ENTRY_THERMAL_WARN
THERMAL_STATUS=deferred
PDU_WARNED=True
PDU_TEMP=85.02919
```

## Итог

`G2-QIKI-009` закрыт честно:
- hostile burst оставляет thermal follow-up след в `pdu`;
- ORION V показывает warned thermal node в `F2/Thermal`;
- hostile follow-up меняется по `COMBAT_ENTRY_THERMAL_WARN`.
