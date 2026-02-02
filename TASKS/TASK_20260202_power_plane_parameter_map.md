# TASK (2026-02-02): Power Plane parameter map (SoT → compute → telemetry → ORION)

Цель: сделать “карту истины” для питания/батареи, чтобы:
- было понятно, **какие параметры существуют** и где они заданы (SoT),
- где они **реально применяются** в расчёте,
- какие **telemetry keys** рождаются,
- где и как это **отображается в ORION**,
- и какие поля ещё **нужно добавить/уточнить** (без моков).

Статус: DRAFT (живой документ; дополняется по мере закрытия пунктов).

---

## 0) Target task + DoD (MVP)

**Target:** `Power Plane: SoT → Telemetry → ORION (no-mocks)`

**Definition of Done:**
1) Единственный SoT параметров питания/батареи: `src/qiki/services/q_core_agent/config/bot_config.json`.
2) `q_sim_service` читает SoT и детерминированно считает энергетику (никаких “красивых чисел” в UI).
3) `qiki.telemetry` содержит согласованный набор `power.*` + faults/shedding.
4) ORION показывает эти значения и честно рендерит `N/A`, если ключа нет/нет данных.
5) Есть доказательство: unit/integration test или docker-smoke на ключевое поведение (минимум SoC update).

---

## 1) Single Source of Truth (SoT)

SoT конфиг: `src/qiki/services/q_core_agent/config/bot_config.json`

### 1.1 Battery capacity / energy

- `hardware_profile.power_capacity_wh` (Wh)
  - Смысл: сколько Wh соответствует 100% SoC.
- `hardware_profile.battery_soc_init_pct` (%)
  - Смысл: стартовый SoC батареи при инициализации симуляции (clamp 0..100).
  - Примечание: если ключ отсутствует, используется дефолт модели.

### 1.2 Power Plane parameters (consumers + limits)

Ключи в `hardware_profile.power_plane`:

- `bus_v_nominal` (V), `bus_v_min` (V)
- `max_bus_a` (A) → косвенно задаёт PDU лимит по мощности (`pdu_limit_w ≈ max_bus_a * bus_v`)
- `base_power_in_w` (W) — базовый “вход” энергии (пока константа)
- `base_power_out_w` (W) — базовый “выход” (фоновые потребители)
- `motion_power_w_per_mps` (W / (m/s))
- `mcqpu_power_w_at_100pct` (W)
- `radar_power_w` (W)
- `transponder_power_w` (W)
- `soc_shed_low_pct`, `soc_shed_high_pct` (%)

### 1.3 Supercap (peak buffer)

- `supercap_capacity_wh` (Wh)
- `supercap_soc_pct_init` (%)
- `supercap_max_charge_w` (W)
- `supercap_max_discharge_w` (W)

### 1.4 Dock Power Bridge

- `dock_connected_init` (bool)
- `dock_station_bus_v` (V)
- `dock_station_max_power_w` (W)
- `dock_current_limit_a` (A)
- `dock_soft_start_s` (s)
- `dock_temp_c_init` (°C)

### 1.5 NBL Power Budgeter

- `nbl_active_init` (bool)
- `nbl_max_power_w` (W)
- `nbl_soc_min_pct` (%)
- `nbl_core_temp_max_c` (°C)

### 1.6 Other planes that affect power

- `propulsion_plane.rcs_power_w_at_100pct` (W) — учитывается как нагрузка RCS.

---

## 2) Compute (q_sim_service)

Где применяется SoT:
- Конфиг загружается и применяется: `src/qiki/services/q_sim_service/core/world_model.py` → `WorldModel._apply_bot_config()`.

Как считается SoC:
- На каждом step вычисляется `net_w = power_in_w - power_out_w`,
  затем `delta_wh = net_w * dt / 3600`,
  и SoC обновляется через `power_capacity_wh`.

Логика PDU (при перегрузе):
1) shed: `nbl`, `radar`, `transponder`
2) throttle `motion`
3) throttle `rcs`
4) если всё равно overcurrent → fault `PDU_OVERCURRENT`

---

## 3) Telemetry keys (payload)

Фактический payload строится из `WorldModel.get_state()` и содержит блок:

### 3.1 Battery (legacy + power.soc_pct)

- `battery_level` (top-level) — SoC, %
- `power.soc_pct` — SoC, % (дублирует смысл)

### 3.2 Power core

- `power.power_in_w`
- `power.power_out_w`
- `power.bus_v`
- `power.bus_a`
- `power.sources_w` (dict[str, watt]) — breakdown источников мощности
- `power.loads_w` (dict[str, watt]) — breakdown потребителей мощности

### 3.3 Protection / diagnostics

- `power.load_shedding` (bool)
- `power.shed_loads` (list[str])
- `power.shed_reasons` (list[str])
- `power.pdu_limit_w` (W)
- `power.pdu_throttled` (bool)
- `power.throttled_loads` (list[str])
- `power.faults` (list[str])

### 3.4 Supercap

- `power.supercap_soc_pct`
- `power.supercap_charge_w`
- `power.supercap_discharge_w`

### 3.5 Dock

- `power.dock_connected`
- `power.dock_soft_start_pct`
- `power.dock_power_w`
- `power.dock_v`
- `power.dock_a`
- `power.dock_temp_c`

### 3.6 NBL

- `power.nbl_active`
- `power.nbl_allowed`
- `power.nbl_power_w`
- `power.nbl_budget_w`

---

## 4) ORION mapping (UI)

Ключевые места в коде ORION:
- Power Systems screen/rows: `src/qiki/services/operator_console/main_orion.py` (использует keys вида `power.soc_pct`, `power.power_in_w`, `power.bus_v`, …).
- `TELEMETRY_DICTIONARY.yaml` уже содержит paths для большинства `power.*` ключей: `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml`.

Канонический UI-SoT по источникам: `docs/operator_console/REAL_DATA_MATRIX.md` (нужно убедиться, что Power Plane покрыт полностью).

---

## 5) Gaps / open questions (fill next)

1) **Init SoC**: сейчас старт SoC = 100% (в модели). Нужен ли параметр `battery_soc_init_pct` в SoT?
2) **Meaning of base_power_in_w**: что именно моделируем (solar/RTG/фон/только dock)?
3) **Per-load breakdown**: хотим ли явный breakdown нагрузок как словарь/таблица (`loads_w`) для инспектора?
4) **Battery constraints**: max charge/discharge W, КПД, политика при 0% (что отключаем первым).
5) **bus sag model**: как именно использовать `bus_v_nominal/bus_v_min` (если хотим реалистичнее).

---

## 6) Next steps (proposed)

Минимальный следующий инкремент (рекомендуется):
1) Добавить `battery_soc_init_pct` в SoT и применить в `_apply_bot_config()` (с тестом).
2) Добавить 1 unit test: SoC корректно уменьшается при `power_out_w > power_in_w` и увеличивается при профиците.
