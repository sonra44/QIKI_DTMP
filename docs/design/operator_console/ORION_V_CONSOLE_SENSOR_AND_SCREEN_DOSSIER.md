# ORION V Console Sensor And Screen Dossier

## Purpose

This document fixes the current factual shape of ORION V as implemented in code on `2026-03-29`.

It answers three questions:

1. What sensors ORION V currently knows about.
2. Which parameters are shown for each sensor.
3. What each ORION V screen actually does right now.

This is not a redesign document.
This is the implementation dossier for the current console.

## Canonical Entry Points

- App shell: `src/qiki/services/operator_console/orion_v/app.py`
- Header: `src/qiki/services/operator_console/orion_v/widgets/header.py`
- Safety chips: `src/qiki/services/operator_console/orion_v/widgets/status_bars.py`
- Action rail: `src/qiki/services/operator_console/orion_v/widgets/action_bar.py`
- F1: `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- F2: `src/qiki/services/operator_console/orion_v/screens/systems.py`
- F3: `src/qiki/services/operator_console/orion_v/screens/deep_dive.py`
- F4: `src/qiki/services/operator_console/orion_v/screens/raw.py`
- F6: `src/qiki/services/operator_console/orion_v/screens/audit.py`
- F7: `src/qiki/services/operator_console/orion_v/screens/system_health.py`
- Hardware projection owner: `src/qiki/services/operator_console/orion_v/hardware_view_model/collector.py`
- Data policy: `docs/operator_console/REAL_DATA_MATRIX.md`

## Console Topology

Current ORION V is a 4-layer terminal console:

1. `MISSION CONTROL STRIP`
   Global status line.
   Shows phase, mode, authority, link, freshness, latency, packet loss, event count, last RX time.

2. `SAFETY & HEALTH STRIP`
   Always-on health summary.
   Shows alert counts and compact chips for power, thermal, propulsion, hull, compute, QIKI.

3. Main level screen
   One of:
   - `F1 Кокпит`
   - `F2 Подсистемы`
   - `F3 Глубокий анализ`
   - `F4 Консоль`
   - `F6 Журнал`
   - `F7 Состояние системы`

4. `ACTION RAIL`
   Bottom operator loop rail.
   Shows mode, level, pending loop, last command summary, command input state, navigation buttons.

## Sensor Inventory

The current sensor subsystem is built in `HardwareCollector.build_sensors()`.

For each sensor ORION V projects the same logical field family:

- `status`
- `value`
- `confidence`
- `age_s`

Subsystem summary rule:

- summary text:
  `Сенсоры: {online} в работе, {degraded} деградации, {offline} отключены`
- subsystem escalates to `WARN` if at least one critical sensor is offline
- subsystem escalates to `CRIT` if at least two critical sensors are offline
- explicitly disabled `sensor_plane.*` devices must not escalate the subsystem by themselves

## Sensor Parameters By Device

### 1. `radar_360`

- Title: `Радар 360`
- Critical: `yes`
- Primary parameter:
  - label: `Ближайшая цель`
  - source keys:
    - `radar_360.closest_m`
  - unit: `м`
- Fallback keys:
  - `radar_360.targets`
- Rendered fields:
  - `sensors.radar_360.status`
  - `sensors.radar_360.value`
  - `sensors.radar_360.confidence`
  - `sensors.radar_360.age_s`

### 2. `lidar_front`

- Title: `Лидар фронт`
- Critical: `yes`
- Primary parameter:
  - label: `Ближайшее препятствие`
  - source keys:
    - `lidar_front.closest_m`
  - unit: `м`
- Rendered fields:
  - `sensors.lidar_front.status`
  - `sensors.lidar_front.value`
  - `sensors.lidar_front.confidence`
  - `sensors.lidar_front.age_s`

### 3. `lidar`

- Title: `Лидар`
- Critical: `no`
- Primary parameter:
  - label: `Ближайшее препятствие`
  - source keys:
    - `lidar.closest_m`
  - unit: `м`
- Fallback keys:
  - `lidar.points`
- Rendered fields:
  - `sensors.lidar.status`
  - `sensors.lidar.value`
  - `sensors.lidar.confidence`
  - `sensors.lidar.age_s`

### 4. `imu_main`

- Title: `IMU`
- Critical: `yes`
- Status aliases:
  - `imu_main`
  - `sensor_imu`
  - `imu`
- Primary parameter:
  - label: `Ускорение`
  - source keys:
    - `imu_main.accel_mps2`
    - `sensor_imu.accel_mps2`
    - `sensor_plane.imu.roll_rate_rps`
  - unit: `м/с²`
- Fallback keys:
  - `imu_main.gyro_dps`
  - `sensor_imu.gyro_dps`
  - `sensor_plane.imu.pitch_rate_rps`
- Rendered fields:
  - `sensors.imu_main.status`
  - `sensors.imu_main.value`
  - `sensors.imu_main.confidence`
  - `sensors.imu_main.age_s`

Note:
- Current implementation mixes legacy IMU acceleration keys with telemetry-native IMU rate keys.
- This is implementation reality, not ideal schema purity.

### 5. `sensor_thermal`

- Title: `Тепловой сенсор`
- Critical: `no`
- Primary parameter:
  - label: `Температура`
  - source keys:
    - `sensor_thermal.temp_c`
  - unit: `°C`
- Rendered fields:
  - `sensors.sensor_thermal.status`
  - `sensors.sensor_thermal.value`
  - `sensors.sensor_thermal.confidence`
  - `sensors.sensor_thermal.age_s`

### 6. `sensor_radiation`

- Title: `Радиационный сенсор`
- Critical: `yes`
- Status aliases:
  - `sensor_radiation`
  - `radiation`
- Primary parameter:
  - label: `Радиация`
  - source keys:
    - `sensor_radiation.level`
    - `radiation.uSv_h`
    - `sensor_plane.radiation.background_usvh`
  - unit: `µSv/h`
- Rendered fields:
  - `sensors.sensor_radiation.status`
  - `sensors.sensor_radiation.value`
  - `sensors.sensor_radiation.confidence`
  - `sensors.sensor_radiation.age_s`

### 7. `sensor_proximity`

- Title: `Сенсор сближения`
- Critical: `no`
- Status aliases:
  - `sensor_proximity`
  - `proximity`
- Primary parameter:
  - label: `Ближайший объект`
  - source keys:
    - `sensor_proximity.closest_m`
    - `sensor_plane.proximity.min_range_m`
  - unit: `м`
- Rendered fields:
  - `sensors.sensor_proximity.status`
  - `sensors.sensor_proximity.value`
  - `sensors.sensor_proximity.confidence`
  - `sensors.sensor_proximity.age_s`

### 8. `sensor_solar`

- Title: `Солнечный сенсор`
- Critical: `no`
- Status aliases:
  - `sensor_solar`
  - `solar`
- Primary parameter:
  - label: `Генерация`
  - source keys:
    - `sensor_solar.watts`
    - `sensor_solar.irradiance`
    - `sensor_plane.solar.illumination_pct`
  - unit: `Вт`
- Rendered fields:
  - `sensors.sensor_solar.status`
  - `sensors.sensor_solar.value`
  - `sensors.sensor_solar.confidence`
  - `sensors.sensor_solar.age_s`

### 9. `sensor_star_tracker`

- Title: `Star tracker`
- Critical: `yes`
- Status aliases:
  - `sensor_star_tracker`
  - `star_tracker`
- Primary parameter:
  - label: `Звезд в треке`
  - source keys:
    - `sensor_star_tracker.stars_tracked`
  - unit: empty
- Fallback keys:
  - `sensor_star_tracker.locked`
  - `sensor_plane.star_tracker.locked`
- Rendered fields:
  - `sensors.sensor_star_tracker.status`
  - `sensors.sensor_star_tracker.value`
  - `sensors.sensor_star_tracker.confidence`
  - `sensors.sensor_star_tracker.age_s`

### 10. `spectrometer`

- Title: `Спектрометр`
- Critical: `no`
- Primary parameter:
  - label: `Последний пик`
  - source keys:
    - `spectrometer.last_peak`
  - unit: empty
- Fallback keys:
  - `spectrometer.active`
- Rendered fields:
  - `sensors.spectrometer.status`
  - `sensors.spectrometer.value`
  - `sensors.spectrometer.confidence`
  - `sensors.spectrometer.age_s`

Note:
- This sensor is still structurally present in the console inventory.
- Live runtime source is currently not evidenced in the active contour.

### 11. `magnetometer`

- Title: `Магнитометр`
- Critical: `no`
- Primary parameter:
  - label: `Магнитное поле`
  - source keys:
    - `magnetometer.uT`
    - `sensor_plane.magnetometer.field_ut`
  - unit: `µT`
- Fallback keys:
  - `magnetometer.vector`
- Rendered fields:
  - `sensors.magnetometer.status`
  - `sensors.magnetometer.value`
  - `sensors.magnetometer.confidence`
  - `sensors.magnetometer.age_s`

## Sensor Support Rules

### Status resolution

Sensor status is derived through `_sensor_status(...)` and `_sensor_status_to_view_status(...)`.

Current status classes:

- `ONLINE`
- `DEGRADED`
- `OFFLINE`
- `NO_DATA`

### Confidence rule

Current confidence thresholds:

- `WARN` when confidence `< 0.5`
- `CRIT` when confidence `< 0.2`

### Age rule

The collector tries:

1. direct `{sensor_id}.age_s`
2. timestamp fallback:
   - `sensor.{sensor_id}.ts`
   - `sensor.{sensor_id}.last_update_ts`

If timestamp exists:
- age is derived as `now - ts`

### Disabled sensor rule

If a sensor is explicitly disabled in telemetry-native sensor-plane semantics, it must be presented as disabled and must not automatically escalate the whole subsystem to warning.

This is especially relevant for:

- `star_tracker`
- `magnetometer`
- other `sensor_plane.*.enabled=false` devices

## Screen Inventory

## `F1` Bridge / Cockpit

Owner:
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`

Role:
- 3-5 second operator situation awareness
- current mission state
- immediate intervention lane

Current content families:

- mission context
- guidance / movement
- mission incident focus
- mode / context
- route / intent
- spatial telemetry
- mission support truth
- observation objective
- right lane:
  - QIKI recommendation
  - operator intervention
  - available actions
  - current process
  - QIKI interpretation
  - procedure

Current issue:
- F1 is structurally strong but still too verbose in nominal state.

## `F2` Systems

Owner:
- `src/qiki/services/operator_console/orion_v/screens/systems.py`

Role:
- subsystem decision screen
- not raw telemetry dump

Current card order:

1. `docking`
2. `power`
3. `propulsion`
4. `navigation`
5. `sensors`
6. `comms`
7. `safety`

Each card currently contains:

- title
- severity
- `Status`
- `Summary`
- `Effect`
- `Next`
- optional `Hint`

Important:
- F2 currently has no dedicated `shields` card
- this matches current implementation reality

## `F3` Deep Dive

Owner:
- `src/qiki/services/operator_console/orion_v/screens/deep_dive.py`

Role:
- incidents
- safe mode authority
- filtered event stream

Current structure:

- incident list with selection
- safe mode block
- event lines

## `F4` Console

Owner:
- `src/qiki/services/operator_console/orion_v/screens/raw.py`

Role:
- literal command / response history

Important:
- body is intentionally rendered literally
- payload-like strings must not become Rich markup

## `F6` Audit

Owner:
- `src/qiki/services/operator_console/orion_v/screens/audit.py`

Role:
- audit trail
- filtered action history

Current structure:

- title
- active filter summary
- audit lines

## `F7` System Health

Owner:
- `src/qiki/services/operator_console/orion_v/screens/system_health.py`

Role:
- runtime health metrics
- NATS/runtime/operator loop diagnostics

Current fields:

- `NATS`
- `events_per_sec`
- `queue_depth`
- `bounded_store`
- `procedure_latency_ms`
- `ack_time_ms`
- `cpu_percent`
- `memory_mb`
- `active_subscriptions`
- `replay_mode`

## Header And Rails

### Header

Owner:
- `widgets/header.py`

Current fields:

- level
- phase
- mode
- authority
- link status
- freshness
- latency
- packet loss
- events count
- RX timestamp
- data freshness state

### Safety chips

Owner:
- `widgets/status_bars.py`

Current chips:

- power
- thermal
- propulsion
- hull
- compute
- qiki

### Action rail

Owner:
- `widgets/action_bar.py`

Current controls:

- F1
- F2
- F3
- F4
- F6
- F7
- incident prev/next
- acknowledge / clear
- page prev/next
- command open/input

## Current UX Diagnosis

The current console already has a good operator skeleton:

- named zones
- stable screen map
- truthful runtime-first status model
- clear separation between global strip, health strip, main screen, action rail

Its main UX weakness is not missing data.
Its main UX weakness is text density and uneven visual rhythm inside otherwise good structural boundaries.

In short:

- architecture is stronger than presentation
- information model is stronger than wording
- screen skeleton is better than block density

