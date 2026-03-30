# ARTIFACT: G2-QIKI-010 acceptance — comms combat constraint

Статус: pass
Дата: 2026-03-06
Этап: `G2-QIKI-010: Comms Combat Constraint`

## Что доказано

- hostile follow-up теперь имеет отдельный `comms` truth-source без нового store;
- при деградированном target-link QIKI меняет hostile follow-up на:
  - `status=deferred`
  - `domain=resource`
  - `reason_code=COMBAT_ENTRY_COMMS_LINK_DEGRADED`
- ORION V показывает этот след через существующий `F2/Comms`;
- новый контур не ломает предыдущие hostile стадии (`propulsion/power/thermal`).

## Truth-source

Используются уже существующие поля `comms`:
- `plane_enabled`
- `link_state`
- `antenna_status`
- `data_rate_kbps`
- `latency_ms`
- `packet_loss_pct`

## Проверки

### Ruff

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tools/orion_v_qiki_comms_combat_constraint_smoke.py
```

Результат: `All checks passed!`

### Pytest

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_qiki_orion_intents_service.py
```

Результат: зелёный.

### Runtime proof

```bash
bash scripts/prove_orion_v_qiki_comms_combat_constraint.sh
```

Факт proof:
- `OK: orion_v_qiki_comms_combat_constraint_smoke`
- `COMMS_CODE=COMBAT_ENTRY_COMMS_LINK_DEGRADED`
- `COMMS_STATUS=deferred`
- `COMMS_LINK=degraded`
- `COMMS_RATE=0.00`
- `COMMS_ANTENNA=unlock`

## Вывод

Этап `G2-QIKI-010` закрыт честно: hostile/combat loop теперь учитывает отдельное `comms`-ограничение как самостоятельный follow-up контур.
