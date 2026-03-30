# QIKI_DTMP — аудит сенсоров и потоков данных

Сводка составлена по коду из архивов `QIKI_DTMP.zip` и `RE_QIKI_Active_Package.zip`, с упором на реальный runtime-путь данных.

## Короткий вывод

1. В `bot_config.json` объявлено 13 сенсорных устройств, но реально как gRPC `SensorReading` сейчас выдаются только **LIDAR**, **IMU** и **RADAR**.
2. Большая часть остальных измерений передаётся не как отдельные `SensorReading`, а через:
   - NATS telemetry snapshot `qiki.telemetry`
   - NATS events `qiki.events.v1.*`
   - support/status слой `q_bios_service`
3. В `q_core_agent` реальный world-model ingest сейчас делает только **RADAR**. Не-радарные gRPC-сенсоры агент получает, но его `world_model` их игнорирует.
4. Имена сенсоров из `bot_config.json` не используются как стабильные `sensor_id` в сообщениях: для LIDAR/IMU/RADAR в runtime чаще генерируются новые UUID.

## Где лежит истина

- Описание допустимого пакета сенсора: `protos/sensor_raw_in.proto`
- Общие типы сенсоров: `protos/common_types.proto`
- gRPC API между agent и sim: `protos/q_sim_api.proto`
- Реальная генерация сенсорных данных: `src/qiki/services/q_sim_service/service.py`
- Реальное состояние мира и большинства полей: `src/qiki/services/q_sim_service/core/world_model.py`
- Реальные NATS топики: `src/qiki/shared/nats_subjects.py`
- Реальный ingest агентом: `src/qiki/services/q_core_agent/core/world_model.py`
- Support/status слой: `src/qiki/services/q_bios_service/main.py`

## 1. Декларативный список сенсоров в bot_config

Файл: `src/qiki/services/q_core_agent/config/bot_config.json:145-158`

Объявлены устройства:
- `lidar_front` — `lidar`
- `imu_main` — `imu`
- `sensor_imu` — `imu`
- `sensor_thermal` — `thermal_sensors`
- `sensor_radiation` — `radiation_sensors`
- `sensor_docking` — `docking_sensors`
- `sensor_proximity` — `proximity_sensors`
- `sensor_solar` — `solar_sensor`
- `sensor_star_tracker` — `star_tracker`
- `radar_360` — `radar`
- `lidar` — `lidar`
- `spectrometer` — `spectrometer`
- `magnetometer` — `magnetometer`

Но это **не равно** реальным выходным потокам runtime.

## 2. Что вообще умеет protobuf-контракт

### 2.1 SensorReading
Файл: `protos/sensor_raw_in.proto:9-41`

Один пакет `SensorReading` может нести:
- `vector_data` — например IMU / GPS
- `scalar_data` — например температура / дистанция
- `binary_data` — например камера
- `radar_data` — `RadarFrame`
- `radar_track` — `RadarTrack`

Дополнительно несёт:
- `sensor_id`
- `sensor_type`
- `timestamp`
- `unit`
- `is_valid`
- `encoding`
- `signal_strength`
- `source_module`

### 2.2 Официальные sensor types в proto
Файл: `protos/common_types.proto:19-27`

Официальный enum `SensorType` содержит только:
- `LIDAR`
- `IMU`
- `CAMERA`
- `GPS`
- `THERMAL`
- `RADAR`

Важно: `spectrometer`, `radiation_sensors`, `docking_sensors`, `proximity_sensors`, `star_tracker`, `magnetometer` есть в конфиге как device-типы, но **нет** как отдельные protobuf sensor types.

## 3. Реальные каналы передачи данных в систему

### 3.1 gRPC сенсорный канал
Файл: `protos/q_sim_api.proto:10-21`, `src/qiki/services/q_sim_service/grpc_server.py:93-114`

Через gRPC доступны:
- `GetSensorData` -> один `SensorReading`
- `GetRadarFrame` -> отдельный `RadarFrame`
- `HealthCheck`

### 3.2 NATS telemetry snapshot
Файл: `src/qiki/services/q_sim_service/service.py:548-561`, `src/qiki/services/q_sim_service/telemetry_publisher.py:69-86`, `src/qiki/shared/nats_subjects.py:25-27`

Топик:
- `qiki.telemetry`

Передаёт большую JSON-снимок-телеметрию со множеством полей, в том числе sensor-plane и subsystem-state.

### 3.3 NATS radar
Файл: `src/qiki/services/q_sim_service/service.py:542-546`, `src/qiki/services/q_sim_service/radar_publisher.py:21-23, 92-132`, `src/qiki/shared/nats_subjects.py:19-23`

Топики:
- `qiki.radar.v1.frames`
- `qiki.radar.v1.frames.lr`
- `qiki.radar.v1.tracks.sr`

### 3.4 NATS events
Файл: `src/qiki/services/q_sim_service/service.py:563-679`, `src/qiki/shared/nats_subjects.py:51-55`

Топики:
- `qiki.events.v1.sensor.thermal`
- `qiki.events.v1.sensor.thermal.trip`
- `qiki.events.v1.power.bus`
- `qiki.events.v1.power.pdu`

### 3.5 BIOS/status side-layer
Файл: `src/qiki/services/q_bios_service/main.py:21-53, 76-114`, `src/qiki/services/q_bios_service/handlers.py:40-64`

`q_bios_service`:
- читает `bot_config.json`
- делает `HealthCheck` в `q_sim_service`
- отдаёт HTTP:
  - `/bios/status`
  - `/bios/component/<id>`
  - `/bios/reload`
- может публиковать JSON в NATS

Это **не владелец физической истины**, а support/status слой.

## 4. Реально работающие сенсоры и что они отправляют

## 4.1 LIDAR (`lidar_front`, `lidar`)

Статус: **реально выдаётся в gRPC sensor cycle**.

Код:
- `src/qiki/services/q_sim_service/config.yaml:2-6` — primary sensor по умолчанию `sim_sensor_type: 1 # LIDAR`
- `src/qiki/services/q_sim_service/service.py:130-139` — формирование цикла
- `src/qiki/services/q_sim_service/service.py:322-332` — генерация пакета

Что реально считывает/генерирует:
- `scalar_data = world_state["position"]["x"]`
- `unit = METERS`

То есть это **не облако точек и не полноценный лидар**, а упрощённый скаляр: фактически только X-координата мира.

Как отправляется:
- gRPC `GetSensorData`

Кому уходит:
- `q_core_agent` через `grpc_data_provider.py:153-197`

Нюанс:
- `sensor_id` не равен `lidar_front`/`lidar`, а создаётся заново через UUID (`service.py:325-326`, fallback `369-374`).

## 4.2 IMU (`imu_main`, `sensor_imu`)

Статус: **реально выдаётся в gRPC sensor cycle**.

Код:
- `service.py:130-139`
- `service.py:333-351`
- `world_model.py:1654-1664`

Что реально считывает/генерирует:
- из `attitude` берёт:
  - `roll_rad`
  - `pitch_rad`
  - `yaw_rad`
- переводит их в градусы
- отправляет как `vector_data = [roll, pitch, yaw]`
- `unit = DEGREES`

Дополнительно в telemetry есть IMU-status блок:
- `ok`
- `status`
- `reason`
- `roll_rate_rps`
- `pitch_rate_rps`
- `yaw_rate_rps`

Как отправляется:
- gRPC `GetSensorData`
- плюс telemetry `sensor_plane.imu`

Нюанс:
- runtime `sensor_id` тоже UUID, а не стабильный `imu_main`/`sensor_imu`.

## 4.3 RADAR (`radar_360`)

Статус: **полностью реализован**, но включается по условию `RADAR_ENABLED`.

Код:
- включение: `service.py:81-89`
- добавление в sensor cycle: `service.py:132-139`
- gRPC `SensorReading`: `service.py:352-365`
- построение кадра: `service.py:383-443`
- proto контракт: `protos/radar/v1/radar.proto:49-101`
- NATS публикация: `radar_publisher.py:92-132`

Что реально считывает/генерирует:
- берёт позицию цели из `world_state.position.{x,y,z}`
- переводит в полярные координаты:
  - `range_m`
  - `bearing_deg`
  - `elev_deg`
- задаёт:
  - `vr_mps`
  - `snr_db`
  - `rcs_dbsm`
- формирует две детекции:
  - LR detection — дальняя, без ID, `transponder_on=False`
  - SR detection — ближняя, может нести `transponder_mode` и `transponder_id`

Как отправляется:
- gRPC `GetSensorData` как `SensorReading.radar_data`
- gRPC `GetRadarFrame`
- NATS:
  - `qiki.radar.v1.frames`
  - `qiki.radar.v1.frames.lr`
  - `qiki.radar.v1.tracks.sr`

Особенности:
- в `radar_publisher.py:103-112` LR-детекциям ID принудительно убирается
- SR-детекции могут нести IFF/XPDR ID
- `sensor_id` кадра снова генерируется как новый UUID (`service.py:438-440`)

## 4.4 Radiation (`sensor_radiation`)

Статус: **включён в active hardware profile**, но не как отдельный gRPC sensor packet.

Код:
- enable в конфиге: `bot_config.json:118-123`
- применение конфига: `world_model.py:357-390`
- экспорт в state: `world_model.py:1665-1687`

Что реально передаёт:
- `background_usvh`
- `dose_total_usv`
- `status`
- `reason`
- `limits.warn_usvh`
- `limits.crit_usvh`

Как отправляется:
- в telemetry как `sensor_plane.radiation`
- top-level `radiation_usvh` тоже есть в snapshot

Не отправляется как:
- отдельный `SensorReading` по gRPC

## 4.5 Thermal (`sensor_thermal`)

Статус: **реально работает**, но в subsystem/telemetry/event форме.

Код:
- включение thermal plane: `bot_config.json:39-99`
- thermal nodes в state: `world_model.py:1496-1515`, `1588-1590`
- thermal event: `service.py:575-591`
- thermal trip edge: `service.py:642-679`

Что реально передаёт:
- per-node:
  - `id`
  - `temp_c`
  - `tripped`
  - `warned`
  - `warn_c`
  - `trip_c`
  - `hys_c`
- top-level:
  - `temp_core_c`
  - `temp_external_c`
- события:
  - текущее значение core temperature
  - edge-события trip/clear

Как отправляется:
- telemetry `thermal.nodes`
- top-level `temp_core_c`, `temp_external_c`
- NATS events:
  - `qiki.events.v1.sensor.thermal`
  - `qiki.events.v1.sensor.thermal.trip`

## 4.6 Docking (`sensor_docking`)

Статус: **реально работает как telemetry block**, не как отдельный gRPC sensor packet.

Код:
- конфиг: `bot_config.json:110-114`
- применение: `world_model.py:330-356`
- экспорт: `world_model.py:1647-1653`

Что реально передаёт:
- `enabled`
- `state`
- `connected`
- `port`
- `ports`

Как отправляется:
- telemetry `docking`
- часть power dock data идёт в `power.*`

## 4.7 Power / EPS measurements

Статус: **реально работает**, это один из самых насыщенных источников данных.

Код:
- power block в state: `world_model.py:1591-1625`
- power bus/pdu events: `service.py:593-627`

Что реально передаёт:
- `soc_pct`
- `sources_w`
- `loads_w`
- `power_in_w`
- `power_out_w`
- `battery_charge_w`
- `battery_discharge_w`
- `battery_spill_w`
- `battery_unserved_w`
- `bus_v`
- `battery_1_voltage_v`
- `battery_2_voltage_v`
- `bus_a`
- `load_shedding`
- `shed_loads`
- `shed_reasons`
- `pdu_limit_w`
- `pdu_throttled`
- `throttled_loads`
- `faults`
- `supercap_*`
- dock power fields
- NBL fields

Как отправляется:
- telemetry `power`
- events:
  - `qiki.events.v1.power.bus`
  - `qiki.events.v1.power.pdu`

## 4.8 Propulsion / RCS telemetry

Статус: **реально работает**.

Код:
- propulsion in state: `world_model.py:1626-1645`

Что реально передаёт:
- `fuel_pct`
- `fuel_total_g`
- `fuel_rate_gs`
- `remaining_fuel_g`
- `propellant_tank_pressure_pa`
- `oxidizer_mass_kg`
- `rcs.enabled`
- `rcs.active`
- `rcs.throttled`
- `rcs.axis`
- `rcs.command_pct`
- `rcs.time_left_s`
- `rcs.propellant_kg`
- `rcs.power_w`
- `rcs.net_force_n`
- `rcs.net_torque_nm`
- `rcs.thrusters[]`

Как отправляется:
- telemetry `propulsion`

## 4.9 Comms / XPDR telemetry

Статус: **реально работает**, источник для radar-ID и канального состояния.

Код:
- config read: `service.py:111-127`
- comms block build: `service.py:719-787`

Что реально передаёт:
- `enabled`
- `xpdr.mode`
- `xpdr.active`
- `xpdr.allowed`
- `xpdr.id`
- `link`
- `latency_ms`
- `packet_loss_pct`
- `rssi_dbm`
- `snr_db`
- `tx_power_w`
- `data_rate_kbps`
- `antenna_status`
- `last_seen_ts`
- `age_s`

Как отправляется:
- telemetry `comms`
- часть данных проходит косвенно в radar SR detections

## 4.10 MCQPU / virtual compute telemetry

Статус: **реально работает**, но это не внешний физический сенсор, а виртуальное hardware-метрическое состояние.

Код:
- модель: `src/qiki/services/q_sim_service/core/mcqpu_telemetry.py:1-196`
- интеграция: `world_model.py:212-215`, `941-950`, `1586-1587`

Что реально передаёт:
- `cpu_usage`
- `memory_usage`

Как отправляется:
- telemetry snapshot top-level fields

Важно:
- это **не метрики VPS/OS**, а simulation-truth виртуального MCQPU.

## 5. Сенсоры, которые объявлены, но сейчас либо выключены, либо почти не реализованы

## 5.1 Proximity (`sensor_proximity`)

Статус: **framework есть, но в active config выключен**.

Код:
- config: `bot_config.json:125`
- state: `world_model.py:1688-1692`

Поля:
- `min_range_m`
- `contacts`

Канал:
- только telemetry `sensor_plane.proximity`

## 5.2 Solar (`sensor_solar`)

Статус: **framework есть, но выключен**.

Код:
- config: `bot_config.json:126`
- state: `world_model.py:1693-1696`

Поле:
- `illumination_pct`

Канал:
- только telemetry `sensor_plane.solar`

## 5.3 Star tracker (`sensor_star_tracker`)

Статус: **framework есть, но выключен**.

Код:
- config: `bot_config.json:127`
- state: `world_model.py:1697-1707`

Поля:
- `status`
- `reason`
- `locked`
- `attitude_err_deg`

Канал:
- telemetry `sensor_plane.star_tracker`

## 5.4 Magnetometer (`magnetometer`)

Статус: **framework есть, но выключен**.

Код:
- config: `bot_config.json:128`
- state: `world_model.py:1708-1710`

Поле:
- `field_ut`

Канал:
- telemetry `sensor_plane.magnetometer`

## 5.5 Spectrometer (`spectrometer`)

Статус: **объявлен в конфиге, но генерации данных в q_sim_service не найдено**.

То есть:
- в `bot_config.json` он есть;
- в operator UI есть ожидание его ключей;
- но реального генератора/издателя спектральных данных в runtime я не нашёл.

## 5.6 CAMERA / GPS / THERMAL как proto sensor types

Статус: **поддержаны схемой, но не реализованы как реальные q_sim источники**.

Деталь:
- `SensorType` proto знает `CAMERA`, `GPS`, `THERMAL`;
- но `q_sim_service.generate_sensor_data()` генерирует только LIDAR / IMU / RADAR.
- Более того, в converter слой `binary_data` пока игнорируется: `protobuf_pydantic.py:321-343`.

## 6. Кто реально потребляет эти данные

## 6.1 q_core_agent

Путь:
- `grpc_data_provider.py:153-197` — читает `GetSensorData`
- `agent.py:140-162` — ingests data into bot_core and world_model
- `q_core_agent/core/world_model.py:26-75`

Критическая правда:
- `world_model.ingest_sensor_data()` сразу делает `return`, если `sensor_type != RADAR`
- то есть world model агента реально строится на radar data
- LIDAR/IMU сейчас в agent world-model не используются

## 6.2 operator_console / ORION

Путь:
- `nats_realtime_client.py:93-97` — подписывается на все потоки
- `nats_realtime_client.py:147-149` — radar frames
- `nats_realtime_client.py:203-205` — telemetry
- `nats_realtime_client.py:243-246` — events wildcard

То есть UI реально питается от:
- radar
- telemetry
- events

## 6.3 q_bios_service

Путь:
- `q_bios_service/main.py:31-44`

Питается от:
- `bot_config.json`
- `HealthCheck` q_sim_service

И отдаёт support/status картину оборудования.

## 7. Активность по compose-стекам

### docker-compose.phase1.yml
Файл: `docker-compose.phase1.yml:107-116`

В active phase1 стеке включены:
- `RADAR_ENABLED=1`
- `RADAR_NATS_ENABLED=1`
- `TELEMETRY_NATS_ENABLED=1`
- `RADAR_SR_THRESHOLD_M=5000.0` (по умолчанию)

А значит там реально активны:
- radar gRPC + NATS
- telemetry NATS
- events NATS (потому что `EVENTS_NATS_ENABLED` по умолчанию наследуется от telemetry flag)

### docker-compose.yml / minimal
Там явно включён radar, но telemetry/events могут не быть активны без дополнительных env.

## 8. Самые важные выводы для проекта

1. **Главный mismatch проекта**: конфиг и UI обещают больше сенсоров, чем реально генерирует runtime.
2. **Реальный ingest агента сейчас почти полностью radar-centric.**
3. **LIDAR сейчас заглушечный**: это фактически `position.x`, а не лидарная геометрия.
4. **IMU реален, но operational impact у него пока слабый**, потому что agent world-model его не использует.
5. **Radiation / Thermal / Docking / Power / Propulsion / Comms** живут в telemetry/event слоях, а не в protobuf `SensorReading` как самостоятельные сенсоры.
6. **Spectrometer, solar, proximity, star tracker, magnetometer** частично присутствуют в модели/UX, но не доведены до полноценного runtime-data source.
7. **`q_bios_service` — это не сенсорный владелец истины**, а support/status projection.

## 9. Итоговый точный список по статусам

### Реально генерируют отдельные sensor packets
- LIDAR
- IMU
- RADAR

### Реально отправляют данные, но через telemetry/events
- Radiation
- Thermal
- Docking
- Power/EPS
- Propulsion/RCS
- Comms/XPDR
- MCQPU CPU/RAM
- Orbit / hull / temperatures / position / speed

### Есть в модели, но сейчас выключены в active config
- Proximity
- Solar
- Star tracker
- Magnetometer

### Объявлены, но полноценного runtime source не найдено
- Spectrometer
- CAMERA (schema only)
- GPS (schema only)
- THERMAL как отдельный protobuf sensor type (schema only; фактически thermal идёт через telemetry/events)

