# TASK (2026-02-02): Sensor Plane parameter map (SoT → compute → telemetry → ORION)

Цель: сделать “карту истины” для Sensor Plane, чтобы было понятно:
- какие параметры существуют и где они заданы (SoT),
- где они применяются/обновляются в симуляции,
- какие telemetry keys рождаются,
- где и как это отображается в ORION,
- и что ещё нужно добавить/уточнить (без моков).

Статус: DRAFT (живой документ).

---

## 0) Target task + DoD (MVP)

**Target:** `Sensor Plane: SoT → Telemetry → ORION (no-mocks)`

**Definition of Done:**
1) Единственный SoT параметров сенсоров: `src/qiki/services/q_core_agent/config/bot_config.json` (`hardware_profile.sensor_plane`).
2) `q_sim_service` публикует `sensor_plane.*` только как sim-truth (или `None`/`na`, если отключено/нет измерения).
3) ORION экран `Sensors/Сенсоры` показывает эти значения и честно рендерит `N/A`.
4) Telemetry Dictionary покрывает ключи, которые ORION использует в provenance.
5) Есть доказательство: unit tests + dictionary guard зелёный.

---

## 1) Single Source of Truth (SoT)

SoT конфиг: `src/qiki/services/q_core_agent/config/bot_config.json`

### 1.1 Sensor plane switches

- `hardware_profile.sensor_plane.enabled` (bool)
- `hardware_profile.sensor_plane.imu.enabled` (bool)
- `hardware_profile.sensor_plane.radiation.enabled` (bool)
- `hardware_profile.sensor_plane.radiation.limits.warn_usvh` (µSv/h)
- `hardware_profile.sensor_plane.radiation.limits.crit_usvh` (µSv/h)
- `hardware_profile.sensor_plane.proximity.enabled` (bool)
- `hardware_profile.sensor_plane.solar.enabled` (bool)
- `hardware_profile.sensor_plane.star_tracker.enabled` (bool)
- `hardware_profile.sensor_plane.magnetometer.enabled` (bool)

Примечание: некоторые сенсоры имеют init-поля (scenario), которые могут быть заданы в SoT, но не являются обязательными:
- `solar.illumination_pct_init`
- `proximity.min_range_m_init`, `proximity.contacts_init`
- `star_tracker.locked_init`, `star_tracker.attitude_err_deg_init`
- `magnetometer.field_ut_init` (`{x,y,z}`)

---

## 2) Compute (q_sim_service)

Где применяется SoT:
- Конфиг загружается: `src/qiki/services/q_sim_service/core/world_model.py` → `WorldModel._apply_bot_config()`.

Как считаются/обновляются значения (sim-truth):
- IMU: в `WorldModel.step()` вычисляются roll/pitch/yaw rates (если IMU enabled и `dt>0`), иначе `None`.
- Radiation: `dose_total_usv` интегрируется в `WorldModel.step()` при enabled.
- Radiation status/limits: в `WorldModel.get_state()` формируется `status/reason/limits` по `warn_usvh/crit_usvh`.
- Proximity/Solar/Star tracker/Magnetometer: на текущем этапе — значения из init-сценария (или `None`, если нет).

---

## 3) Telemetry keys (payload)

Payload строится из `WorldModel.get_state()` и содержит:

### 3.1 Root
- `sensor_plane.enabled`

### 3.2 IMU
- `sensor_plane.imu.enabled`
- `sensor_plane.imu.ok`
- `sensor_plane.imu.roll_rate_rps`, `pitch_rate_rps`, `yaw_rate_rps`
- `sensor_plane.imu.status`, `sensor_plane.imu.reason`

### 3.3 Radiation
- `sensor_plane.radiation.enabled`
- `sensor_plane.radiation.background_usvh`
- `sensor_plane.radiation.dose_total_usv`
- `sensor_plane.radiation.status`, `sensor_plane.radiation.reason`
- `sensor_plane.radiation.limits.warn_usvh`, `sensor_plane.radiation.limits.crit_usvh` (если сконфигурировано)

### 3.4 Proximity
- `sensor_plane.proximity.enabled`
- `sensor_plane.proximity.min_range_m`
- `sensor_plane.proximity.contacts` (count)

### 3.5 Solar
- `sensor_plane.solar.enabled`
- `sensor_plane.solar.illumination_pct`

### 3.6 Star tracker
- `sensor_plane.star_tracker.enabled`
- `sensor_plane.star_tracker.locked`
- `sensor_plane.star_tracker.attitude_err_deg`
- `sensor_plane.star_tracker.status`, `sensor_plane.star_tracker.reason`

### 3.7 Magnetometer
- `sensor_plane.magnetometer.enabled`
- `sensor_plane.magnetometer.field_ut` (`{x,y,z}` in µT) or `None`

---

## 4) ORION mapping (UI)

- ORION Sensors screen: `src/qiki/services/operator_console/main_orion.py` (`_render_sensors_table()`).
- Канонический словарь ключей: `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml` (`subsystems.sensors`).

---

## 5) Gaps / open questions (fill next)

1) Нужно ли сделать proximity/solar/magnetometer динамическими (не только init)?
2) Нужно ли вводить единый `status/reason` для proximity/solar/magnetometer (как у IMU/radiation/star_tracker)?
3) Нужны ли фильтры/агрегации (например, “контакты за окно времени”) или это отдельный Perception слой?

