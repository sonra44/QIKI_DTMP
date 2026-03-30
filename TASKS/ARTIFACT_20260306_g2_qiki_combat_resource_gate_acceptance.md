# ACCEPTANCE: G2-QIKI-004 — resource gate hostile continuation

Статус: PASS/PASS
Дата: 2026-03-06

## Что доказано

Для одного и того же hostile-intent сценария:

`QIKI, атакуй объект UNBT9999`

система теперь различает два честных состояния мира:

1. `blocked/resource`
- `COMBAT_ENTRY_RCS_RESOURCE_LOW`
- hostile-контекст уже открыт;
- protocol block уже снят;
- но ресурсный RCS-контур не готов к продолжению combat-entry.

2. `allowed/protocol`
- `COMBAT_ENTRY_PROCEDURE_READY`
- hostile-контекст открыт;
- station influence нет;
- ресурсный контур RCS готов;
- оператор снова получает уже существующий prepared combat-entry path.

## Truth-source

Новый hostile resource gate использует только текущую телеметрию:
- `world_snapshot["propulsion"]["rcs"]["enabled"]`
- `world_snapshot["propulsion"]["rcs"]["propellant_kg"]`
- при необходимости `world_snapshot["thermal"]`

Новый hidden state не вводился.

## Docker-proof

Команда:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_cockpit.py
```

Результат:
- green

Команда:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  ruff check src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_cockpit.py \
  tools/orion_v_qiki_hostile_resource_gate_smoke.py
```

Результат:
- `All checks passed!`

## Runtime-proof

Команда:

```bash
bash scripts/prove_orion_v_qiki_hostile_resource_gate.sh
```

Фактический результат:

```text
OK: orion_v_qiki_hostile_resource_gate_smoke
RESOURCE_BLOCK_HELP=QIKI blocked: ... [COMBAT_ENTRY_RCS_RESOURCE_LOW]
ALLOWED_HELP=QIKI allowed: ... [COMBAT_ENTRY_PROCEDURE_READY] | q confirm
BLOCKED_CODE=COMBAT_ENTRY_RCS_RESOURCE_LOW
ALLOWED_CODE=COMBAT_ENTRY_PROCEDURE_READY
```

## Контур A: инженерный

PASS:
- truth-source детерминирован;
- hostile resource gate не вводит второй источник истины;
- unit tests зелёные;
- runtime-proof зелёный.

## Контур B: продуктовый

PASS:
- hostile continuation теперь зависит не только от протокола, но и от ресурса;
- оператор видит объяснимую ресурсную причину;
- проект стал ближе к `Encounter 1v1`, не уходя в weapons stack.
