# TASK (2026-02-02): Docking Plane parameter map (SoT → compute → telemetry → ORION)

Цель: сделать “карту истины” для стыковки, чтобы было понятно:
- какие параметры существуют и где они заданы (SoT),
- где они реально применяются в расчёте/управлении,
- какие telemetry keys рождаются,
- где и как это отображается в ORION,
- и какие gaps остаются (без моков).

Статус: DRAFT (живой документ).

---

## 0) Target task + DoD (MVP)

**Target:** `Docking Plane: SoT → Telemetry → ORION (no-mocks)`

**Definition of Done:**
1) Единственный SoT для docking: `src/qiki/services/q_core_agent/config/bot_config.json` (`hardware_profile.docking_plane` + `hardware_profile.power_plane.dock_*`).
2) `q_sim_service` публикует docking состояние в `docking.*` и power-bridge состояние в `power.dock_*` (без “нулей ради красоты”).
3) ORION показывает минимум: `Dock connected`, `Dock state`, `Dock port`, soft-start и dock power/VI.
4) Есть доказательство: unit test на `sim.dock.engage/release` и dictionary guard зелёный.

---

## 1) Single Source of Truth (SoT)

SoT конфиг: `src/qiki/services/q_core_agent/config/bot_config.json`

### 1.1 Mechanical docking plane

- `hardware_profile.docking_plane.enabled` (bool)
- `hardware_profile.docking_plane.ports` (list[str]) — доступные порты (обычно `["A","B"]`)
- `hardware_profile.docking_plane.default_port` (str)

### 1.2 Power dock bridge (Power Plane)

Подсистема питания содержит “Dock Power Bridge” (электрический мост/заряд/лимиты):
- `hardware_profile.power_plane.dock_connected_init` (bool)
- `hardware_profile.power_plane.dock_station_bus_v` (V)
- `hardware_profile.power_plane.dock_station_max_power_w` (W)
- `hardware_profile.power_plane.dock_current_limit_a` (A)
- `hardware_profile.power_plane.dock_soft_start_s` (s)
- `hardware_profile.power_plane.dock_temp_c_init` (°C)

---

## 2) Compute (q_sim_service)

Где применяется SoT:
- Конфиг читается: `src/qiki/services/q_sim_service/core/world_model.py` → `WorldModel._apply_bot_config()`.
- Mechanical docking state: `WorldModel.set_dock_connected()` и `WorldModel.set_docking_port()`.
- Control surface (сим-команды): `QSimService.apply_control_command()` поддерживает `sim.dock.engage` и `sim.dock.release`.

Важная связка (сейчас, MVP):
- `docking.connected` и `power.dock_connected` отражают один и тот же факт “стыковка подключена” (в `WorldModel` это единый флаг `dock_connected`).

---

## 3) Telemetry keys (payload)

### 3.1 Docking (mechanical)
- `docking.enabled`
- `docking.state` (`docked/undocked/disabled`)
- `docking.connected` (bool)
- `docking.port` (str | null)
- `docking.ports` (list[str])

### 3.2 Dock Power Bridge (power plane)
- `power.dock_connected`
- `power.dock_soft_start_pct`
- `power.dock_power_w`
- `power.dock_v`
- `power.dock_a`
- `power.dock_temp_c`

---

## 4) ORION mapping (UI)

- ORION показывает docking значения в Power экране:
  - `Dock` (power bridge): `power.dock_connected`, soft start %, P/V/A, temp.
  - `Dock state`, `Dock port`: `docking.state`, `docking.port`.
  - Код: `src/qiki/services/operator_console/main_orion.py` (`_render_power_table()`).
- Канонический словарь ключей: `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml` (`subsystems.docking` + часть `subsystems.power`).

---

## 5) Evidence

- Unit test: `src/qiki/services/q_sim_service/tests/test_docking_plane.py` доказывает `sim.dock.release/engage` и валидность `docking.*`.
- Dictionary guard: `tests/unit/test_telemetry_dictionary.py`.

---

## 6) Gaps / open questions (fill next)

1) Развести семантику “mechanical connected” и “power bridge connected” (сейчас это 1 флаг) — нужно ли моделировать раздельно?
2) Нужно ли публиковать `docking.reason`/`docking.faults` (например, “invalid port”, “disabled”) для лучшей объяснимости?
3) Нужно ли добавить отдельный ORION экран `Docking/Стыковка` (не в Power), если появятся процедуры/операции?

