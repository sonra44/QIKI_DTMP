# Worklog — Sensor Plane status/limits слой (2026-01-18)

Цель круга: внедрить минимальный “миссион‑контрол” паттерн **status/limits** для Sensor Plane, не нарушая инварианты:
- no-mocks (только simulation-truth, иначе `N/A/—`)
- no-v2
- no-duplicates / SoT = `bot_config.json`

## Что изменено

1) Симуляция (`q_sim_service`)
- `src/qiki/services/q_sim_service/core/world_model.py`
  - Добавлено чтение лимитов радиации из `bot_config.json`:
    - `hardware_profile.sensor_plane.radiation.limits.warn_usvh`
    - `hardware_profile.sensor_plane.radiation.limits.crit_usvh`
  - В `sensor_plane` добавлены поля:
    - `imu.status`, `imu.reason`
    - `radiation.status`, `radiation.reason`, `radiation.limits`
    - `star_tracker.status`, `star_tracker.reason`
  - Политика no-mocks:
    - если сенсор выключен → `status=na`, `reason=disabled`
    - если нет данных → `status=na`, `reason=no reading`
    - если лимиты не настроены → `status=na`, `reason=limits not configured`

2) Runtime SoT (конфиг)
- `src/qiki/services/q_core_agent/config/bot_config.json`:
  - добавлены лимиты радиации `warn_usvh=1.0`, `crit_usvh=2.0`
- `src/qiki/shared/config/generator.py`:
  - генератор теперь тоже включает эти лимиты по умолчанию (чтобы не было дрейфа).

3) ORION (Operator Console)
- `src/qiki/services/operator_console/main_orion.py`
  - Sensors таблица научилась использовать `sensor_plane.<sub>.status` как источник “Статус” (ok/warn/crit/na → Норма/Предупреждение/Не норма/N/A).
  - Добавлена строка `Background/Фон` (radiation.background_usvh) со статусом из лимитов.

4) Документация
- `docs/task_plans/TZ_SENSOR_PLANE_VIRTUALIZATION.md`: добавлен раздел `Update (2026-01-18) — Status/Limits слой`.
- `docs/task_plans/RESEARCH_MISSION_CONTROL_PATTERNS_2026-01-18.md`: зафиксирован обзор паттернов (COSMOS/Yamcs/OpenMCT/NATS/Textual).

## Тесты / проверки

Unit tests (Docker-first):

```bash
docker compose -f docker-compose.phase1.yml run --rm --no-deps qiki-dev bash -lc \
  'pytest -q \
    src/qiki/services/q_sim_service/tests/test_sensor_plane.py \
    src/qiki/services/q_sim_service/tests/test_sensor_plane_limits_status.py \
    src/qiki/services/operator_console/tests'
```

Smoke (Docker):
- `qiki.telemetry` содержит `sensor_plane.radiation.status` и `limits` (проверено подпиской на NATS из `qiki-dev`).
- ORION контейнер стартует и показывает Sensors таблицу без падений.

