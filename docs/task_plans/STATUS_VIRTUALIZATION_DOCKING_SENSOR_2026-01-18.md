# STATUS — Virtualization MVP: Docking Plane + Sensor Plane (2026-01-18)

Проект: `QIKI_DTMP`  
Репозиторий: `QIKI_DTMP`

Цель этого документа: зафиксировать *фактическое* состояние виртуализации (что реализовано в коде/доках/проверках) и определить следующий шаг без создания новых “линий правды”.

---

## 0) Жёсткие ограничения (контракты/процесс)

- **Rule B / Docker-first**: проверяем поведение только в Docker (compose phase1/operator).
- **Serena-first**: все правки по репо — через Serena/патчи, не “угадываем”.
- **No-mocks в UI/ORION**: если реальных данных нет/не доказано, UI обязан показывать `N/A`/`—`, а не “0/OK”.
- **Контракты**:
  - Никаких `*_v2` / новых параллельных subject’ов.
  - Расширяем существующую телеметрию `qiki.telemetry` **добавлением новых top-level блоков** (модель телеметрии допускает extra keys).
  - Стабильные subject’ы: `qiki.telemetry`, `qiki.events.v1.*`, `qiki.commands.control`.
- **Runtime Source of Truth (SoT)**: `src/qiki/services/q_core_agent/config/bot_config.json` — единственный машиночитаемый источник правды для профиля железа.

---

## 1) Что сделано: Docking Plane MVP

**Коммит:** `91b32af` — `Virtualize Docking Plane (telemetry + ORION controls)`

### 1.1 Симуляция (`q_sim_service`)

- В `WorldModel` добавлен top-level блок телеметрии: `docking.*`
  - `docking.enabled`
  - `docking.state`
  - `docking.connected`
  - `docking.port`
  - `docking.ports`
- **Ключевое решение: без дублирования истинности**
  - “механическая” состыковка *производная* от уже существующей истины `power.dock_connected` (чтобы не появилось двух независимых источников).
- Команды управления идут через `qiki.commands.control`:
  - `sim.dock.engage` (опционально `port`)
  - `sim.dock.release`

### 1.2 ORION / Operator Console

- На Power экране отображаются `docking.state` и `docking.port`.
- Добавлены команды:
  - `dock.engage [A|B]`
  - `dock.release`

### 1.3 Тесты и документы

- Добавлены тесты на парсинг docking-команд и на sim docking.
- Обновлён `docs/operator_console/REAL_DATA_MATRIX.md` (Docking — `частично`).
- Добавлен план/ТЗ: `docs/task_plans/TZ_DOCKING_PLANE_VIRTUALIZATION.md`.

---

## 2) Что сделано: Sensor Plane MVP

**Коммит:** `1abf456` — `Virtualize Sensor Plane (telemetry + ORION screen)`

### 2.1 Конфиг (SoT)

- `src/qiki/services/q_core_agent/config/bot_config.json`:
  - добавлен `hardware_profile.sensor_plane` (enabled + per-sensor flags).
- `src/qiki/shared/config/generator.py`:
  - добавлены дефолты для генерации `sensor_plane`.

### 2.2 Симуляция (`q_sim_service`)

- `WorldModel` читает `hardware_profile.sensor_plane` и публикует top-level блок: `sensor_plane.*`.
- Реализованные поля:
  - `sensor_plane.imu.*` — включённость/ok + угловые скорости `roll_rate_rad_s`, `pitch_rate_rad_s`, `yaw_rate_rad_s` (только если IMU включён).
  - `sensor_plane.radiation.*` — `dose_total_usv` как интегратор от `radiation_usvh`.
  - Для proximity/solar/star_tracker/magnetometer:
    - **без моков**: значения `None`, пока сценарий/мир не инициализирует реальные значения.
- В `QSimService._build_telemetry_payload()` добавлено пробрасывание блока:
  - `sensor_plane=state.get("sensor_plane", {})`.

### 2.3 ORION / Operator Console

- Добавлен экран `sensors` в `ORION_APPS`:
  - hotkey: `Ctrl+N`
  - алиасы: `imu/иму` и др.
- Добавлен `screen-sensors` + `sensors-table`.
- Добавлены методы:
  - `_seed_sensors_table()`
  - `_render_sensors_table()`
  - подключено в `handle_telemetry_data()`.
- Отрисовка строго по **no-mocks**:
  - `None` → `N/A` (а не “0” и не “OK”).

### 2.4 Тесты и документы

- Добавлены тесты:
  - `src/qiki/services/q_sim_service/tests/test_sensor_plane.py`
  - `src/qiki/services/operator_console/tests/test_sensors_screen_aliases.py`
- Обновлены документы:
  - `docs/operator_console/REAL_DATA_MATRIX.md` (Navigation/ADCS + Sensors)
  - `docs/design/hardware_and_physics/bot_source_of_truth.md` (BIOS/профили: runtime SoT = `bot_config.json`, без параллельных артефактов)
- Добавлен план/ТЗ: `docs/task_plans/TZ_SENSOR_PLANE_VIRTUALIZATION.md`.

---

## 3) Быстрые проверки (smoke) — что реально подтверждено

- В Docker-стеке телеметрия содержит:
  - top-level `docking` (меняется от команд engage/release)
  - top-level `sensor_plane` (появляется при включённом профиле)
- В ORION:
  - доступен экран `sensors` (горячая клавиша `Ctrl+N`)
  - `N/A` корректно показывается для неинициализированных сенсоров

---

## 4) Принятые ключевые решения (чтобы не вернуться к дублям)

1) **Не создавать вторую “истину”** для величин, которые уже есть в `power.* / thermal.* / docking.*`.  
2) **Расширение телеметрии через новые top-level блоки** в `qiki.telemetry`, без новых subject’ов и без `v2`.  
3) **No-mocks UI**: честное `N/A` лучше, чем “красивое” но ложное значение.  
4) **Документы синхронизируем с реальностью**: если дизайн расходится с тем, что в коде — правим дизайн (а не плодим вторую схему/файл).

---

## 5) Что дальше (следующий блок виртуализации)

Варианты следующего шага (выбираем один, чтобы не распыляться):

1) **Comms/XPDR plane**:
   - новый top-level блок `comms.*` (link status + режимы ON/OFF/SILENT/SPOOF + ошибки/причины)
   - ORION экран/виджет для статуса линка и режимов
2) **RLSM deeper** (lidar/spectrometer/magnetometer beyond current “partial radar”)
3) **Hardware profile hash tracing**:
   - вычислять hash из `bot_config.json` и публиковать в телеметрии/BIOS/логах (без новых версий контрактов)

---

## 6) Память (Sovereign Memory) — пруф фиксации

- Docking MVP: `STATUS id=777`, `TODO_NEXT id=778`, `DECISIONS id=779`
- SoT mapping: `STATUS id=780`, `TODO_NEXT id=781`, `DECISIONS id=782`
- Sensor Plane MVP: `STATUS id=783`, `TODO_NEXT id=784`, `DECISIONS id=785`

