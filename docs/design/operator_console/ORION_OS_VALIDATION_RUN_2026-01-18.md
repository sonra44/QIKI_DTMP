# ORION Shell OS — Validation Run (2026-01-18)

Цель: зафиксировать воспроизводимую проверку ORION в Docker по чеклисту `ORION_OS_VALIDATION_CHECKLIST.md`.

Дата: 2026-01-18  
Окружение: Docker Compose (`docker-compose.phase1.yml` + `docker-compose.operator.yml`)

## 0) Preflight (runtime)

- ✅ Run via Docker:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console q-bios-service q-sim-service nats`
- ✅ Health (compose):
  - `nats` — `healthy`
  - `q-sim-service` — `healthy`
  - `operator-console` — `healthy`
  - `q-bios-service` — `healthy`
- ✅ BIOS доступен (HTTP):
  - `curl -fsS http://localhost:8080/healthz` → `{"ok": true}`
  - `curl -fsS http://localhost:8080/bios/status` → валидный `BiosStatus` JSON
- ✅ BIOS публикует события в NATS (no-mocks):
  - subject: `qiki.events.v1.bios_status`
  - проверка подпиской из `qiki-dev`: событие получено, `all_systems_go=True`, `post_results_len=23`

## 1) Global invariants (must always hold)

- ✅ Missing data показывается как `N/A/—` (в логах TUI видно `Bus/Шина N/A/—`, `Radiator/Радиатор N/A/—` и т.п.)
- ✅ Авто-тесты operator_console прошли (`pytest`): i18n/лейблы/структура компонентов/инциденты/правила/статус-бар
- ⚠️ Tmux resize stability — требуется ручная валидация (см. чеклист раздел 5)

## 2) Input/Output dock (calm operator loop)

- ✅ Авто-тесты проходят (фокус/маршрутизация/QIKI routing/UI components)
- ⚠️ Визуальная проверка “typed text visibility + overflow” — требуется ручная валидация (TUI)

## 3) Events/События — incidents workflow

- ✅ Авто-тесты проходят (pause/unread, store, rules, toggle in app)
- ⚠️ Ручная проверка hotkeys (`F3`, `Ctrl+Y`, `A`, `X`, `R`) — рекомендуется при следующем интерактивном прогоне

## 4) Inspector/Инспектор contract

- ✅ Авто-тесты проходят (структура/компоненты)
- ⚠️ Ручная проверка selection-driven поведения — рекомендуется

## 5) Chrome stability under tmux resizing

- ⚠️ Требуется ручная валидация в tmux (узкий/широкий терминал, низкая высота)

## 6) Non-priority radar safety

- ✅ Авто-тесты operator_console прошли; крэша при загрузке не видно по логам
- ⚠️ Ручное подтверждение `F2` “не падает” — рекомендуется

## 7) Rules/Правила — quick enable/disable + reload

- ✅ Авто-тесты проходят (incident_rules + toggle in app)
- ⚠️ Ручная проверка “Reload rules/Перезагрузить правила” кнопкой — рекомендуется

## Smoke результаты (сухой остаток)

- Стек поднимается и живой.
- BIOS сервис отвечает по HTTP и публикует `qiki.events.v1.bios_status` (no-mocks).
- Авто-тесты ORION/BIOS/sim проходят.

## Update (2026-01-18) — Docking + Sensors MVP sanity

- ✅ ORION показывает новые блоки виртуализации без моков:
  - Docking: команды присутствуют в help-подсказке командной строки (`dock.engage`, `dock.release`) и телеметрия `docking.*` доступна через `qiki.telemetry`.
  - Sensors: экран `sensors` отрисовывается; поля без источника показываются как `N/A/—` (например, `Min range/Мин. дальн`, `Contacts/Контакты`, `Illumination/Освещённ`).
- ✅ Прогон тестов в dev-контейнере:
  - `pytest -q src/qiki/services/operator_console/tests src/qiki/services/q_sim_service/tests/test_sensor_plane.py`
  - (исправлено: `src/qiki/services/operator_console/tests/test_metrics_client.py` теперь не зависит от запуска async-тестов как async def; использует `asyncio.run(...)`, чтобы не ловить “async def functions are not natively supported”.)

## Update (2026-01-18) — Comms/XPDR (partial) sanity

- ✅ `qiki.telemetry` содержит `comms.xpdr.*` (mode/active/allowed/id), без моков.
- ✅ Runtime‑контроль:
  - команда `sim.xpdr.mode` через `qiki.commands.control` меняет `comms.xpdr.mode` в телеметрии.
  - пример smoke: `mode=SILENT` → `active=False`, `id=None`.
- ✅ ORION:
  - команда `xpdr.mode <on|off|silent|spoof>` добавлена в подсказку и публикует `sim.xpdr.mode`.
  - `Diagnostics` таблица расширена блоками XPDR (mode/allowed/active/id), `N/A/—` если `comms` отсутствует.

## Update (2026-01-18) — Hardware profile hash tracing (BIOS → telemetry → ORION)

- ✅ BIOS `/bios/status` возвращает `hardware_profile_hash` (формат `sha256:<64hex>`) на основании `bot_config.json` (runtime SoT).
- ✅ `qiki.telemetry` содержит top-level ключ `hardware_profile_hash` и он совпадает с BIOS (no-mocks: если конфиг не читается — ключ отсутствует).
- ✅ ORION `Diagnostics` показывает `Hardware profile hash/Хэш профиля железа` (если нет данных — `N/A/—`).

## Post-run hardening (после прогона)

- Порт BIOS на хосте ограничен до loopback, чтобы не ловить внешние сканеры:
  - `docker-compose.phase1.yml`: `127.0.0.1:8080:8080` (внутри docker-сети доступ по `http://q-bios-service:8080` остаётся прежним).

## Update (2026-01-18) — ORION unified UI design (design-first)

Цель: сохранить единый интерфейс при росте виртуализации (Power/Thermal/Propulsion/Sensors/BIOS/Comms), особенно в tmux-сплитах.

- ✅ Density-driven labels (единство названий экранов):
  - `wide/normal` → показываем полные `EN/RU` названия экранов (Sidebar, при достаточной ширине и Keybar).
  - `narrow/tiny` → компактные подписи (как раньше), чтобы не ломать раскладку.
  - Детали: `src/qiki/services/operator_console/main_orion.py` (`menu_label_for_density`).

- ✅ Sensors: compact по умолчанию, детали по требованию (не “простыня”):
  - Экран `Sensors/Сенс` по умолчанию — 5–6 строк по подсистемам (glanceable).
  - `Enter` переключает `compact ↔ details` (внутри `sensors-table`).
  - Детали (`Age`, `Source`) показываются через Inspector (в таблице держим минимум колонок для читабельности).
  - Настройка: `ORION_SENSORS_COMPACT_DEFAULT=1` (по умолчанию включено; `0` → стартовать в details на wide).

- ✅ Авто-проверка (Docker):
  - `pytest -q src/qiki/services/operator_console/tests` — зелёный.

## Update (2026-01-18) — Cursor stability + Sensors table compaction

- ✅ Убрано “скачущее выделение” в таблицах при refresh:
  - табличный курсор больше не сбрасывается на первую строку при обновлении данных;
  - выбор сохраняется по `row_key` и восстанавливается после перерисовки.
- ✅ `Sensors` таблица уплотнена без потери правды:
  - таблица сведена к 3 колонкам: `Sensor/Статус/Значение` (ширина уходит в `Value`);
  - `Age/Source` остаются доступными через Inspector (no-mocks сохраняется: если нет данных — `N/A/—`).
- ✅ Discoverability: при входе на экран `Sensors` ставится фокус на `sensors-table`, и Inspector сразу показывает `Selection/Выбор` (без ручного `Tab`).
- ✅ Layout: все `screen-*` живут в одном `#orion-workspace`, а `bottom-bar` всегда докнут снизу — `F3/F4` и остальные экраны больше не «уезжают» ниже строки команды.
