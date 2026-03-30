
Цель: зафиксировать **регламентное** ТЗ для внедрения виртуализации Docking Plane (байонетные порты, механическая стыковка) в проекте **QIKI_DTMP** так, чтобы:
- соблюсти **no‑mocks policy** (в UI только реальные данные симуляции или честное `N/A/—`);
- не создавать **дубли** и “вторые источники правды”;
- не добавлять `*_v2.*` и параллельные контракты/subject’ы.

ТЗ написано так, чтобы его можно было показать стороннему инженеру/модели без доступа к репозиторию.

---

## 0) Контекст (не обсуждается)

1) Проект — **симуляция / Digital Twin**. “Железо” бота виртуальное.  
2) “Реальные данные” в рамках проекта — это **simulation‑truth** (детерминированно вычисленные величины), а **не** метрики VPS/контейнера.  
3) **Запрещено**:
   - добавлять `*_v2.*` (например, `docking_v2`, `dock_v2`, `telemetry_v2` и т.п.);
   - заводить второй `bot_config`/`bot_spec`/`dock_spec` с дублирующим содержимым.
4) Разрешено:
   - расширять **существующий** `src/qiki/services/q_core_agent/config/bot_config.json` новыми параметрами;
   - расширять **существующую** телеметрию `qiki.telemetry` дополнительными ключами верхнего уровня (в `TelemetrySnapshotModel` разрешены `extra`);
   - использовать **существующий** subject управления `qiki.commands.control` (строковые `command_name` без новых `.proto`).

---

## 1) Каноничные документы/артефакты (источник правды)

**Текстовый SoT (человекочитаемый):**
- `docs/design/hardware_and_physics/bot_source_of_truth.md`
- `docs/operator_console/REAL_DATA_MATRIX.md`

**Машиночитаемые (приоритет выше текста):**
- `src/qiki/services/q_core_agent/config/bot_config.json` — runtime профиль “железа” (Docking Plane параметры и порты)

---

## 2) Проблема, которую решаем

Сейчас Power Plane уже содержит “Dock Power Bridge” (внешнее питание при `dock_connected=true`), но:
- нет отдельного слоя “механики” (порты A/B, состояние стыковки, выбранный порт);
- UI не может честно показать “стыковку как железо” без демо‑нулей/вымышленных статусов;
- нет управляемой команды “стыковать/расстыковать” как действие оператора (в рамках симуляции).

Нужно:
- добавить Docking Plane как отдельный слой виртуального железа (mechanical), который:
  - имеет порты (например A/B),
  - имеет состояние (`undocked/docked/disabled`),
  - даёт telemetry (`docking.*`) и управляется оператором,
  - **не** создаёт второй источник “подключённости” (не дублирует Power Plane truth).

---

## 3) Scope

### 3.1 Must‑have (обязательно в MVP)

1) **Docking Plane state в симуляции (`q_sim_service`)**
   - состояние `docking.state`: `disabled | undocked | docked`
   - выбранный порт `docking.port` (например `A|B`)
   - список доступных портов `docking.ports`
   - флаг `docking.enabled`
   - флаг `docking.connected` (должен быть согласован с существующим `power.dock_connected`)

2) **Единый источник параметров**
   - параметры Docking Plane живут в `bot_config.json` (секция `hardware_profile.docking_plane`)
   - нельзя держать “инициализацию подключённости” здесь же, если она уже существует в Power Plane (чтобы не было двух линий правды)

3) **Управление (no new proto)**
   - поддержать команды управления через `qiki.commands.control`:
     - `sim.dock.engage` (опционально `port`)
     - `sim.dock.release`
   - при `sim.dock.engage`:
     - выбирается порт (если задан, иначе default),
     - далее включается существующий power‑dock (`dock_connected=true`) как эффект “механически состыкованы”
   - при `sim.dock.release`:
     - отключается `dock_connected=false`

4) **ORION UI (no‑mocks)**
   - в Power/EPS экране (или отдельной панели Docking) отображать:
     - `power.dock_connected`
     - `docking.state`
     - `docking.port`
   - если телеметрии нет → `N/A`, никаких “0/OK” без источника

5) **Тесты**
   - unit‑тесты в `q_sim_service`:
     - `sim.dock.release` переключает `docking.state` и `docking.connected`
     - `sim.dock.engage` устанавливает `port` и включает `connected`
     - неверный порт → команда отклоняется
   - unit‑тесты в `operator_console`:
     - парсер CLI `dock.engage [port]` / `dock.release` корректен

---

## 4) Параметры в `bot_config.json` (без дублей)

Добавить/поддержать в `hardware_profile` секцию (пример):

- `docking_plane.enabled: bool`
- `docking_plane.ports: [str]` (например `["A","B"]`)
- `docking_plane.default_port: str` (например `"A"`)

Важно:
- статус “подключено/не подключено” остаётся единственным источником правды в Power Plane (`power.dock_connected` / `dock_connected_init`), Docking Plane не заводит второй `*_connected_init`.

---

## 5) Критерии приёмки (DoD)

Считаем задачу выполненной, если:
1) В Docker‑стеке `phase1` симуляция публикует телеметрию с `docking.*` (реальные состояния, не заглушки).
2) ORION отображает Docking state/port без моков: данные или `N/A`.
3) Команды `sim.dock.engage/release` работают и согласованы с Power Plane (`power.dock_connected`).
4) `pytest` для `q_sim_service` и `operator_console` зелёный, есть тесты на базовую логику докинга.
5) Не добавлены `*_v2.*`, не создано дублирующих источников правды.

