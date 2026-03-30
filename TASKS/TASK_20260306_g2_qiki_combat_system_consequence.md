# TASK: G2 — системное отражение боевого последствия

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G2_QIKI_COMBAT_EVENT_CONSEQUENCE_CANON.md`

Уже доказано:
- hostile combat-entry меняет tactical state;
- ORION V публикует отдельный combat event как факт мира.

Пока не доказано:
- что боевое действие оставляет системную цену в `EPS/Thermal/Propulsion/Comms`, которая меняет следующие допустимые действия.

## Цель

Реализовать первый законченный контур системной цены боя, где:
- боевой event уже существует;
- одна подсистема отражает его как ограничение или стоимость;
- QIKI учитывает это в следующем hostile follow-up.

## Следующее действие

1. Зафиксировать acceptance этого этапа в отдельном артефакте.
2. Синхронизировать внешний canonical board и bootstrap.
3. Сделать replan следующего G2-этапа после propulsion-cost reflection.

## Журнал доказательств

### Петля 1: propulsion cost reflection через расход RCS propellant

Изменённые файлы:
- `src/qiki/services/q_sim_service/core/world_model.py`
- `src/qiki/services/q_sim_service/tests/test_rcs_propulsion.py`
- `tools/orion_v_qiki_combat_system_consequence_smoke.py`
- `scripts/prove_orion_v_qiki_combat_system_consequence.sh`

Результат:
- telemetry теперь несёт `propulsion.fuel_pct`, `propulsion.fuel_total_g`, `propulsion.fuel_rate_gs`, `propulsion.remaining_fuel_g`;
- `F2/Propulsion` показывает системную цену hostile burst без нового экрана;
- при начальном `propellant_kg=2.05` один `hostile_rcs_intercept_burst` снижает ресурс до `0.81276 кг`;
- следующий hostile follow-up уходит в `blocked/resource` с `COMBAT_ENTRY_RCS_RESOURCE_LOW`.

Доказательства:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/q_sim_service/core/world_model.py src/qiki/services/q_sim_service/tests/test_rcs_propulsion.py tools/orion_v_qiki_combat_system_consequence_smoke.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_sim_service/tests/test_rcs_propulsion.py tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py`
- `bash scripts/prove_orion_v_qiki_combat_system_consequence.sh`
