# ARTIFACT: G2-QIKI-008 — Power Combat Constraint Acceptance

Статус: PASS  
Дата: 2026-03-06

## Что доказано

1. После подтверждённого hostile burst power contour оставляет отдельный системный след.
2. Этот след виден в ORION V через существующий `F2/Power`.
3. Тот же hostile follow-up меняется по текущему power-state.

## Выбранный truth-source

- `power.load_shedding`
- `power.shed_reasons`
- `power.pdu_throttled`
- `power.throttled_loads`

Канонический `reason_code`:
- `COMBAT_ENTRY_POWER_OVERCURRENT`

## Проверки

### Ruff

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  ruff check \
  src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tools/orion_v_qiki_hostile_power_gate_smoke.py
```

Результат:
- `All checks passed!`

### Unit

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/unit/test_qiki_orion_intents_service.py
```

Результат:
- `32 passed`

### Runtime proof

```bash
bash scripts/prove_orion_v_qiki_hostile_power_gate.sh
```

Результат:

```text
OK: orion_v_qiki_hostile_power_gate_smoke
POWER_CODE=COMBAT_ENTRY_POWER_OVERCURRENT
POWER_STATUS=blocked
POWER_SHED_REASONS=['pdu_overcurrent']
```

## Итог

`G2-QIKI-008` закрыт через power-ветку честно:
- hostile burst оставляет power cost;
- ORION V показывает системный след в `F2/Power`;
- follow-up hostile request уходит в `blocked/resource` по `COMBAT_ENTRY_POWER_OVERCURRENT`.
