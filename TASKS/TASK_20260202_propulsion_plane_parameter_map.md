# TASK (2026-02-02): Propulsion Plane parameter map (SoT → compute → telemetry → ORION)

Цель: сделать “карту истины” для Propulsion/RCS, чтобы было понятно:
- какие параметры существуют и где они заданы (SoT),
- где они реально применяются в расчёте/управлении,
- какие telemetry keys публикуются,
- где и как это отображается в ORION,
- и какие gaps остаются (без моков).

Статус: DRAFT (живой документ).

---

## 0) Target task + DoD (MVP)

**Target:** `Propulsion Plane (RCS): SoT → sim truth → telemetry → ORION (no-mocks)`

**Definition of Done:**
1) Единственный SoT для RCS: `src/qiki/services/q_core_agent/config/bot_config.json` (`hardware_profile.propulsion_plane.*`) + `config/propulsion/thrusters.json`.
2) `q_sim_service` публикует `propulsion.rcs.*` (включая thrusters duty/valve) без “демо‑нулей”.
3) ORION экран `Propulsion/Двигатели` работает на реальной телеметрии и честно показывает `N/A/—`, если блока нет.
4) Есть доказательство: unit tests по RCS и dictionary guard зелёный.

---

## 1) Single Source of Truth (SoT)

### 1.1 Bot config (главный SoT)

Файл: `src/qiki/services/q_core_agent/config/bot_config.json`

`hardware_profile.propulsion_plane`:
- `enabled` (bool)
- `thrusters_path` (path) — по умолчанию `config/propulsion/thrusters.json`
- `propellant_kg_init` (kg)
- `isp_s` (s)
- `rcs_power_w_at_100pct` (W)
- `heat_fraction_to_hull` (0..1) — доля тепла, уходящая в корпус (thermal coupling)
- `pulse_window_s` (s) — окно PWM для “valve_open” (детерминированно)
- `ztt_torque_tol_nm` (Nm) — допуск для Zero‑Torque Thruster группировки

### 1.2 Thrusters layout (геометрия + тяга)

Файл: `config/propulsion/thrusters.json`

Каждый thruster:
- `index` (int)
- `cluster_id` (string) — группа механики/кластер
- `position_m` ([x,y,z] meters)
- `direction` ([x,y,z] unit-ish vector)
- `f_max_newton` (N)

Производная проверка (конфиг‑качество):
- `thruster_allocation_rank(thrusters) == 6` (полный 6DoF ранг матрицы распределения).
  - Код: `src/qiki/shared/config/loaders.py` (`build_thruster_allocation_matrix`, `_matrix_rank`).

---

## 2) Compute (q_sim_service)

### 2.1 Где применяется SoT

- Конфиг читается: `src/qiki/services/q_sim_service/core/world_model.py` → `WorldModel._apply_bot_config()`:
  - включает/выключает RCS, читает параметры,
  - загружает thrusters и предвычисляет осевые группы (ZTT).

### 2.2 Control surface (как оператор управляет)

**NATS control (ORION → q_sim_service):**
- `sim.rcs.fire` (`axis`, `pct`, `duration_s`) → `WorldModel.set_rcs_command(axis, pct, duration_s)`
- `sim.rcs.stop` → `WorldModel.set_rcs_command(None, 0, 0)`
  - Код: `src/qiki/services/q_sim_service/service.py` (`apply_control_command()`).

**Actuator commands (gRPC path / internal):**
- `receive_actuator_command(ActuatorCommand)` может конвертировать команды в RCS (через actuator role mapping из `bot_config.json`).
  - Доказательство: тест `src/qiki/services/q_sim_service/tests/test_rcs_propulsion.py`.

### 2.3 Simulation truth (что реально считается в каждом тике)

RCS‑шаг: `src/qiki/services/q_sim_service/core/world_model.py` → `WorldModel._rcs_step(delta_time)`:
- Ставит `rcs_active`, вычисляет net force/torque и thrusters state.
- Расход топлива: пропорционален суммарной тяге `|F|` через `mdot = F_total / (Isp * g0)`.
- Электропотребление: `rcs_w` зависит от команды (`rcs_power_w_at_100pct * pct`) и доли открытых клапанов в текущем PWM окне.
- При “закончилась длительность” или “топливо=0” команда сбрасывается (без бесконечного горения).

### 2.4 Power‑gating / throttling (PDU)

RCS — часть Power Plane нагрузки и может быть “троттлено” при PDU overcurrent:
- `WorldModel.step()` при превышении `pdu_limit_w` сначала сбрасывает не критические нагрузки (NBL/radar/xpdr),
  затем троттлит motion, затем (если нужно) троттлит RCS.
- Троттлинг отображается в `propulsion.rcs.throttled` + scaled `thrusters[*].duty_pct`.
  - Код: `WorldModel._rcs_apply_throttle_ratio(reason="pdu_overcurrent")`.

---

## 3) Telemetry keys (payload)

### 3.1 Propulsion/RCS (operator-facing)

- `propulsion.rcs.enabled`
- `propulsion.rcs.active`
- `propulsion.rcs.throttled`
- `propulsion.rcs.axis`
- `propulsion.rcs.command_pct`
- `propulsion.rcs.time_left_s`
- `propulsion.rcs.propellant_kg`
- `propulsion.rcs.power_w`
- `propulsion.rcs.net_force_n` (vector3)
- `propulsion.rcs.net_torque_nm` (vector3)
- `propulsion.rcs.thrusters[]`:
  - `index`, `cluster_id`, `duty_pct`, `valve_open`, `f_max_newton` (+ опционально `status/reason` при throttling)

### 3.2 Связанные power‑ключи (explainability)

- `power.loads.rcs` (W) — RCS вклад в общую нагрузку шины
- `power.pdu_throttled`, `power.throttled_loads`, `power.faults` — почему и что было ограничено

---

## 4) ORION mapping (UI)

- ORION рендерит RCS на экране `Propulsion/Двигатели`:
  - Код: `src/qiki/services/operator_console/main_orion.py` (`_render_propulsion_table()`).
  - Источник: `qiki.telemetry` → `TelemetrySnapshotModel.normalize_payload(payload)` → `payload["propulsion"]["rcs"]`.
- Канонический словарь ключей: `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml` (`subsystems.propulsion`).

---

## 5) Evidence

- Unit tests:
  - `src/qiki/services/q_sim_service/tests/test_rcs_propulsion.py`
- Dictionary guard:
  - `tests/unit/test_telemetry_dictionary.py`

---

## 6) Gaps / open questions (fill next)

1) Нужно ли документировать оси (`forward/aft/port/starboard/up/down`) как канон управления (аналог `SIMULATION_CONTROL_CONTRACT.md`)?
2) Нужно ли добавить thermal coupling от RCS к конкретным thermal nodes (не только “heat_fraction_to_hull”)?
3) Когда появится мир/динамика: как net force/torque будет интегрироваться в движение/ориентацию (сейчас RCS — “виртуальная правда” для телеметрии/питания/тепла).

