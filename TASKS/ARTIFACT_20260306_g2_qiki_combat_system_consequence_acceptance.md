# ACCEPTANCE: G2-QIKI-007 — Combat System Consequence Reflection

Статус: PASS
Дата: 2026-03-06
Ответственные: user + codex

## Что доказывали

После подтверждённого hostile burst система должна показать не только отдельный combat event, но и системную цену этого действия в одном из контуров корабля, причём следующий hostile follow-up должен меняться по этой цене.

## Что изменено

- `src/qiki/services/q_sim_service/core/world_model.py`
- `src/qiki/services/q_sim_service/tests/test_rcs_propulsion.py`
- `tools/orion_v_qiki_combat_system_consequence_smoke.py`
- `scripts/prove_orion_v_qiki_combat_system_consequence.sh`

## Truth-source

- симуляционный расход `propulsion.rcs.propellant_kg`;
- производные telemetry-поля:
  - `propulsion.fuel_pct`
  - `propulsion.fuel_total_g`
  - `propulsion.fuel_rate_gs`
  - `propulsion.remaining_fuel_g`
- hostile follow-up reuse existing `COMBAT_ENTRY_RCS_RESOURCE_LOW` gate.

## Проверки

1. Ruff:
   - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/q_sim_service/core/world_model.py src/qiki/services/q_sim_service/tests/test_rcs_propulsion.py tools/orion_v_qiki_combat_system_consequence_smoke.py`
2. Unit:
   - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_sim_service/tests/test_rcs_propulsion.py tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py`
3. Runtime:
   - `bash scripts/prove_orion_v_qiki_combat_system_consequence.sh`

## Фактический результат

- `PREPARED_PROP_KG=2.05000`
- `FINAL_PROP_KG=0.81276`
- `FOLLOWUP_CODE=COMBAT_ENTRY_RCS_RESOURCE_LOW`
- `FOLLOWUP_STATUS=blocked`

## Вывод

Этап `G2-QIKI-007` закрыт честно:
- системная цена hostile burst существует в реальной телеметрии propulsion;
- ORION V показывает её через уже существующий subsystem-path;
- следующий hostile follow-up меняется по этой системной цене;
- Docker-proof и runtime-proof зелёные.
