# TASK (2026-02-02): Thermal Plane parameter map (SoT → compute → telemetry → ORION)

Цель: сделать “карту истины” для тепловой подсистемы, чтобы было понятно:
- какие параметры существуют и где заданы (SoT),
- где они реально применяются в расчёте,
- какие telemetry keys рождаются,
- где и как это отображается в ORION,
- и что ещё нужно добавить/уточнить (без моков).

Статус: DRAFT (живой документ).

---

## 0) Target task + DoD (MVP)

**Target:** `Thermal Plane: SoT → Telemetry → ORION (no-mocks)`

**Definition of Done:**
1) Единственный SoT параметров тепла: `src/qiki/services/q_core_agent/config/bot_config.json` (`hardware_profile.thermal_plane`).
2) `q_sim_service` детерминированно считает температуры и состояния trip (hysteresis), без “красивых чисел”.
3) `qiki.telemetry` содержит `thermal.nodes[*]` с `id/temp_c/tripped/trip_c/hys_c`.
4) ORION показывает температуры узлов и статус перегрева:
   - предпочитает `thermal.nodes[*].tripped`,
   - fallback на legacy `power.faults` (`THERMAL_TRIP:<node>`).
5) Есть доказательство: unit tests на trip/hysteresis + dictionary guard зелёный.

---

## 1) Single Source of Truth (SoT)

SoT конфиг: `src/qiki/services/q_core_agent/config/bot_config.json`

### 1.1 Thermal plane global

- `hardware_profile.thermal_plane.enabled` (bool)
- `hardware_profile.thermal_plane.ambient_exchange_w_per_c` (W/°C)

### 1.2 Thermal nodes

`hardware_profile.thermal_plane.nodes[]`:
- `id` (str)
- `heat_capacity_j_per_c` (J/°C)
- `cooling_w_per_c` (W/°C)
- `t_init_c` (°C)
- `t_max_c` (°C) → в runtime используется как `trip_c`
- `t_hysteresis_c` (°C) → в runtime используется как `hys_c`

### 1.3 Thermal couplings

`hardware_profile.thermal_plane.couplings[]`:
- `a`, `b` (node id)
- `k_w_per_c` (W/°C)

---

## 2) Compute (q_sim_service)

Где применяется SoT:
- Конфиг загружается и применяется: `src/qiki/services/q_sim_service/core/world_model.py` → `WorldModel._apply_bot_config()`.
- Расчёт температуры: `WorldModel._thermal_step()` (узловая сеть + explicit Euler).
- Trip/hysteresis: `WorldModel._thermal_trip_state` обновляется в `_thermal_step()`.

Как влияет на Power (важно для оператора):
- `THERMAL_TRIP:pdu` отключает `radar/transponder` (shedding).
- `THERMAL_TRIP:core` отключает `nbl` (shedding).
Реализация: `WorldModel.step()` проверяет `_thermal_trip_state` (power plane часть).

---

## 3) Telemetry keys (payload)

Фактический payload строится из `WorldModel.get_state()` и содержит блок:

### 3.1 Thermal nodes

- `thermal.nodes[*].id`
- `thermal.nodes[*].temp_c`
- `thermal.nodes[*].tripped`
- `thermal.nodes[*].trip_c`
- `thermal.nodes[*].hys_c`

### 3.2 Legacy compatibility

- `power.faults` может содержать `THERMAL_TRIP:<node>` (исторический канал для ORION fallback).

---

## 4) ORION mapping (UI)

- Thermal screen: `src/qiki/services/operator_console/main_orion.py` (`_render_thermal_table()`).
- Канонический словарь ключей: `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml`.

---

## 5) Gaps / open questions (fill next)

1) Нужно ли отдельное поле `thermal.nodes[*].status` (ok/warn/crit) вместо/в дополнение к `tripped`?
2) Нужно ли показывать “источники тепла” (например, `q_w`) для объяснимости (как breakdown в power)?
3) Нужно ли отделить “trip по температуре” и “warn” уровни (двухпороговая система)?

