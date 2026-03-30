# ORION V Hardware View Model

## Зачем нужен этот слой

`hardware_view_model` — это единый слой нормализации аппаратной телеметрии для ORION V.
Он отделяет сбор и интерпретацию данных от экранов TUI.

Цели:
- один формат данных для F1/F2/F3/F4/F7;
- отсутствие дублирования пороговой логики в UI;
- добавление новых подсистем без переписывания экранов.

На этапе 8.3.1 слой подготовлен как фундамент и не меняет текущий UI.

## Контракт входа (`snapshot`)

Коллектор принимает словарь `dict[str, Any]` с сырыми значениями.

Поддерживаются:
- плоские ключи (`"power.soc"`, `"thermal.core_c"`);
- вложенные словари (`{"power": {"soc": 45.2}}`).

Пример:

```python
snapshot = {
    "power.soc": 45.2,
    "power.bus_v": 24.1,
    "thermal.core_c": 72.3,
    "comms.latency_ms": 120,
}
```

## Контракт выхода

`HardwareCollector.update(snapshot)` возвращает `HardwareViewModel`:
- `system_status` — агрегированный статус системы;
- `subsystems` — карта `dict[str, SubsystemView]`;
- `generated_at` — timestamp генерации.

`SubsystemView` содержит:
- `id`, `title`;
- `status`;
- `fields: list[TelemetryField]`;
- `summary` (короткая строка для F1).

`TelemetryField` содержит:
- `key`, `label`, `value`, `unit`, `status`, `hint`, `ts`.

## Статусы

Единый набор статусов:
- `НОРМА`
- `ПРЕДУПРЕЖДЕНИЕ`
- `КРИТИЧНО`
- `НЕТ_ДАННЫХ`

`НЕТ_ДАННЫХ` — отдельный технический статус, не равный `НОРМА`.

## Базовые подсистемы (этап 8.3.1)

Коллектор создаёт каркас для:
- `power`
- `thermal`
- `comms`
- `docking`
- `navigation`
- `compute`
- `sensors`
- `hull`
- `shields`
- `propulsion`

Для каждой подсистемы заполняются 2-3 базовых поля.
Если данные отсутствуют, поля получают статус `НЕТ_ДАННЫХ` и значение `Нет данных`.

## Пороги

Пороговая логика вынесена в `thresholds.py`:
- `status_by_min`
- `status_by_max`
- `status_by_range`

Это позволяет централизованно обновлять правила без правок экранов.

## Power/EPS (этап 8.3.2)

Подсистема `power` теперь строится как полноценное операторское представление Energy/EPS.

### Читаемые ключи (алиасы)

- SoC: `power.soc`, `power.soc_pct`, `eps.soc`
- Напряжение шины: `power.bus_v`, `power.bus_voltage_v`, `eps.bus_v`
- Ток шины: `power.bus_a`, `power.bus_current_a`, `eps.bus_a`
- Потребление: `power.draw_w`, `power.power_w`, `eps.draw_w`
- Доступная мощность: `power.available_w`, `eps.available_w`
- Режим ограничения: `power.limit_mode`, `power.limits_active`
- Аварийное отключение нагрузки: `power.load_shedding`, `power.load_shedding_active`
- Емкость батареи (Wh): `power.battery_wh`, `battery.capacity_wh`, `eps.capacity_wh`
- Системные состояния: `dock_power_bridge.state`/`power.dock_bridge_state`,
  `nbl_power_budgeter.state`/`power_budgeter.state`, `pdu.state`/`pdu.health`

### Производные метрики

- `power.draw_w`: если прямое поле отсутствует и доступны `bus_v` + `bus_a`,
  используется расчет `P = U * I`.
- `power.runtime_min`: best-effort расчет времени до разрядки:
  - `remaining_wh = capacity_wh * soc / 100`
  - `runtime_h = remaining_wh / power_w`
  - `runtime_min = runtime_h * 60`
  - если `power_w <= 0` или не хватает данных, runtime не вычисляется (`Нет данных`)

### Оценочный режим

Если емкость батареи не передана, используется
`DEFAULT_BATTERY_CAPACITY_WH = 500.0` (в `thresholds.py`).
Поле runtime в этом случае помечается как оценочное в `hint`.

### Пороговые правила Power/EPS

- SoC: `warn < 20%`, `crit < 15%`
- Напряжение шины: `warn < 22V`, `crit < 20V`
- Runtime (если вычислен): `warn < 20 мин`, `crit < 10 мин`
- `load_shedding=ON`: минимум `ПРЕДУПРЕЖДЕНИЕ`; если при этом SoC уже `WARN/CRIT`,
  статус усиливается до `КРИТИЧНО`.

`summary` для power формируется в операторском виде:
- `Заряд 42%, 24.1В, ~85 мин`
- или без runtime, если он недоступен
- или `Нет данных`, если входных значений нет

## Propulsion (этап 8.3.3)

Подсистема `propulsion` расширена до операторской модели RCS + wheel motors + топлива.

### Читаемые ключи (алиасы)

- Топливо: `propulsion.fuel_pct`, `propulsion.fuel_percent`, `rcs.fuel_pct`, `fuel.pct`
- Полная емкость топлива: `propulsion.fuel_total_g`, `fuel.total_g`, `fuel.capacity_g`
- Расход топлива: `propulsion.fuel_rate_gs`, `rcs.fuel_rate_gs`, `fuel.rate_gs`
- Агрегаты RCS: `rcs.active_count`, `rcs.total_thrust_n`, `propulsion.total_thrust_n`
- Thrusters (forward/aft/port/starboard/up/down):
  - state: `rcs.<name>.state`, `propulsion.rcs.<name>.state`, `thrusters.<name>.state`
  - thrust: `rcs.<name>.thrust_n`, `thrusters.<name>.thrust_n`
  - throttle: `rcs.<name>.throttle`
  - fault flags: `rcs.<name>.stuck`, `rcs.<name>.leak`, `rcs.<name>.fault`
- Моторы:
  - left/right rpm: `motor_left.rpm`/`motor_left.speed_rpm`, `motor_right.rpm`/`motor_right.speed_rpm`
  - left/right current: `motor_left.current_a`, `motor_right.current_a`
  - left/right temp: `motor_left.temp_c`, `motor_right.temp_c`
  - left/right fault: `motor_left.fault`, `motor_right.fault`

### Производные метрики

- `propulsion.total_thrust_n`: если агрегат отсутствует, суммируется из доступных thruster `*.thrust_n`.
- `propulsion.remaining_fuel_g`:
  - `remaining_g = fuel_total_g * fuel_pct / 100`
  - при отсутствии `fuel_total_g` используется `DEFAULT_FUEL_TOTAL_G = 10000.0` (оценка).
- `propulsion.burn_time_min`:
  - `burn_sec = remaining_g / fuel_rate_gs`
  - `burn_min = burn_sec / 60`
  - если `fuel_rate_gs` отсутствует или <=0, значение `Нет данных`.

### Пороги Propulsion

- Топливо: `warn < 20%`, `crit < 10%`
- Время до исчерпания: `warn < 20 мин`, `crit < 10 мин`
- Thruster fault rules:
  - `stuck=True` или `leak=True` -> `КРИТИЧНО`
  - `fault=True` -> `ПРЕДУПРЕЖДЕНИЕ`
- Моторы:
  - температура `>80°C` -> `ПРЕДУПРЕЖДЕНИЕ`, `>95°C` -> `КРИТИЧНО`
  - `fault=True` усиливает статус мотора до критичного

Итоговый `propulsion.status` вычисляется как максимальная критичность всех полей.
`summary` формируется в операторском виде:
- `Топливо 62%, тяга 0 Н, мот(L/R) 120/118 RPM`
- при отсутствии данных: `Нет данных`

## Navigation (этап 8.3.4)

Подсистема `navigation` расширена до операторской модели позиции/ориентации/скоростей/режима.

### Читаемые ключи (алиасы)

- Позиция:
  - `navigation.pos_x`/`navigation.x`/`nav.x`
  - `navigation.pos_y`/`navigation.y`/`nav.y`
  - `navigation.pos_z`/`navigation.z`/`nav.z`
  - вектор: `navigation.position` (list/tuple/dict `x,y,z`)
- Скорости:
  - `navigation.vel_x`/`nav.vx`
  - `navigation.vel_y`/`nav.vy`
  - `navigation.vel_z`/`nav.vz`
  - модуль: `navigation.speed_mps`/`nav.speed_mps`
- Курс: `navigation.heading_deg`/`nav.heading_deg`
- Ориентация:
  - `navigation.pitch_deg`/`nav.pitch_deg`
  - `navigation.yaw_deg`/`nav.yaw_deg`
  - `navigation.roll_deg`/`nav.roll_deg`
- Угловые скорости:
  - `navigation.p_rate_dps`/`nav.p_rate_dps`
  - `navigation.y_rate_dps`/`nav.y_rate_dps`
  - `navigation.r_rate_dps`/`nav.r_rate_dps`
- Режим/источник/доверие:
  - `navigation.mode`/`nav.mode`
  - `sensor_star_tracker.status`/`navigation.star_tracker_status`
  - `navigation.confidence`/`nav.confidence`

### Производные метрики

- `navigation.speed_mps`: если нет прямого speed, но есть `vx/vy/vz`,
  считается как `sqrt(vx^2 + vy^2 + vz^2)`.
- `navigation.quality`:
  - `Высокое` при `confidence >= 0.8`
  - `Среднее` при `0.5 <= confidence < 0.8`
  - `Низкое` при `confidence < 0.5`
  - если confidence отсутствует и star tracker offline -> `Низкое` (best-effort)

### Пороги Navigation

- `confidence < 0.2` -> `КРИТИЧНО`
- `0.2 <= confidence < 0.8` -> `ПРЕДУПРЕЖДЕНИЕ`
- `confidence >= 0.8` -> `НОРМА`
- `mode == IMU_ONLY` и star tracker offline -> минимум `ПРЕДУПРЕЖДЕНИЕ`

`summary` для navigation:
- `Скорость 2.4 м/с, курс 182°, P/Y/R 1/0/0°`
- при частичных данных: только доступные части
- при отсутствии данных: `Нет данных`

## Sensors (этап 8.3.5)

Подсистема `sensors` построена как единый реестр сенсоров с общим форматом:
статус, ключевое показание, доверие, возраст данных.

### Обязательный реестр сенсоров

- `radar_360`
- `lidar_front`
- `lidar`
- `imu_main`
- `sensor_thermal`
- `sensor_radiation`
- `sensor_proximity`
- `sensor_solar`
- `sensor_star_tracker`
- `spectrometer`
- `magnetometer`

### Нормализация статусов

Через `normalize_sensor_status(...)`:
- `true/1/online/up/ok` -> `ONLINE` (`В работе`)
- `degraded/warn` -> `DEGRADED` (`Снижение качества`)
- `false/0/offline/down/lost` -> `OFFLINE` (`Нет данных` или `Отключен` для enabled-флага)
- `None/empty` -> `UNKNOWN` (`Нет данных`)

### Читаемые ключи (best-effort)

Для каждого сенсора:
- статус: `sensor.<name>.status`, `<name>.status`, `sensor_plane.<name>.enabled`, `<name>.online`
- доверие: `sensor.<name>.confidence`, `<name>.confidence`, `sensor.<name>.quality`
- timestamp/age: `sensor.<name>.ts`, `sensor.<name>.last_update_ts`, `<name>.age_s`

Ключевые primary значения:
- radar_360: `radar_360.targets`, `radar_360.closest_m`
- lidar_front: `lidar_front.closest_m`
- lidar: `lidar.closest_m`, `lidar.points`
- imu_main: `imu_main.accel_mps2`, `imu_main.gyro_dps`
- sensor_thermal: `sensor_thermal.temp_c`
- sensor_radiation: `sensor_radiation.level`, `radiation.uSv_h`
- sensor_proximity: `sensor_proximity.closest_m`
- sensor_solar: `sensor_solar.watts`, `sensor_solar.irradiance`
- sensor_star_tracker: `sensor_star_tracker.locked`, `sensor_star_tracker.stars_tracked`
- spectrometer: `spectrometer.active`, `spectrometer.last_peak`
- magnetometer: `magnetometer.uT`, `magnetometer.vector`

### Пороговые правила sensors

- confidence: `<0.5` -> `WARN`, `<0.2` -> `CRIT`
- если любой критически важный сенсор offline -> минимум `WARN`
- если offline у двух и более критически важных сенсоров -> `CRIT`

Критически важные сенсоры:
- `imu_main`
- `sensor_star_tracker`
- `radar_360`
- `lidar_front`
- `sensor_radiation`

### Summary

Формируется агрегат:
- `Сенсоры: X в работе, Y деградации, Z отключены`
- при полном отсутствии данных: `Нет данных`

## Docking (этап 8.3.6)

Подсистема `docking` расширена до операторского режима сближения:
состояние, дистанция, относительная скорость, ошибка выравнивания,
захват/замки, статус docking-сенсора и ETA до контакта.

### Читаемые ключи (алиасы)

- состояние: `docking.state`, `docking.phase`, `dock.state`
- цель: `docking.target`, `docking.target_id`, `dock.target`
- дистанция: `docking.distance_m`, `dock.distance_m`, `sensor_docking.distance_m`
- скорость сближения: `docking.approach_mps`, `docking.relative_speed_mps`, `dock.rel_speed_mps`
- ошибка выравнивания: `docking.alignment_error_deg`, `dock.align_err_deg`, `sensor_docking.alignment_error_deg`
- замки/захват: `docking.lock_state`, `docking.latch_state`, `dock.locked`, `docking.capture`
- датчик стыковки: `sensor_docking.status`, `sensor_docking.online`, `sensor_plane.sensor_docking.enabled`

### Derived

- ETA до контакта:
  - `eta_sec = distance_m / approach_mps` при `approach_mps > 0`
  - если `approach_mps <= 0` или входных данных нет -> `Нет данных`
  - отображение: `мин:сек` (например `0:50`)

### Пороговые правила

- alignment error:
  - warn > `DOCK_MAX_ALIGN_WARN_DEG` (5°)
  - crit > `DOCK_MAX_ALIGN_CRIT_DEG` (10°)
- approach speed:
  - warn > `DOCK_MAX_SPEED_WARN_MPS` (0.20 м/с)
  - crit > `DOCK_MAX_SPEED_CRIT_MPS` (0.40 м/с)
- если docking sensor offline при `state != idle` -> минимум `WARN`
- если state в `approach/align/capture`, но нет distance/speed/alignment -> минимум `WARN`
- если lock_state=`locked` (или `dock.locked=true`) и нет иных критичных параметров -> `OK`

### Summary

- рабочий формат: `Стыковка: <state>, <distance> м, <speed> м/с, <align>°`
- locked: `Стыковка: ЗАФИКСИРОВАНО`
- при отсутствии данных: `Нет данных`

## Hull + Shields (этап 8.3.7)

Добавлены отдельные подсистемы `hull` и `shields` с операторскими порогами
и короткими summary для будущего F1.

### Hull — ключи и трактовка

Читаемые ключи:
- целостность: `hull.integrity_pct`, `hull.integrity`, `hull.hp_pct`
- альтернативно через абсолютные значения: `hull.hp`, `hull.hp_max`
- секторные повреждения:
  - `hull.sector_damage` (dict sector->damage_pct)
  - `hull.damage_sectors` (dict sector->damage_pct)
  - `hull.sector_<name>_pct`
  - `sensor_mounts.damage` (best-effort, если структура совпадает)
- нагрузка/стресс: `hull.stress`, `hull.structural_stress`, `hull.g_load`

Трактовка `sector_damage` на этом этапе:
- значение считается **процентом повреждения** (а не остатком прочности).
- худший сектор определяется как максимум damage_pct.

Derived:
- если процента целостности нет, но есть `hp/hp_max`, вычисляется:
  `integrity_pct = 100 * hp / hp_max`
- формируются:
  - `Худший сектор` (пример: `nose (85%)`)
  - `Повреждения по секторам` (top-3, компактная строка)

Пороги Hull:
- integrity: `<70%` -> `ПРЕДУПРЕЖДЕНИЕ`, `<40%` -> `КРИТИЧНО`
- секторное повреждение: `>60%` -> `ПРЕДУПРЕЖДЕНИЕ`, `>80%` -> `КРИТИЧНО`
- stress (опционально): warn/crit по внутренним порогам (`HULL_STRESS_WARN/CRIT`)

Summary Hull:
- `Корпус 92%, худший сектор: нос 12%`
- при отсутствии данных: `Нет данных`

### Shields — ключи и пороги

Читаемые ключи:
- уровень щита: `shields.level_pct`, `shields.level`, `shield.pct`
- альтернативно: `shields.hp`, `shields.hp_max` (с расчетом процента)
- потребление: `shields.draw_w`, `shields.consumption_w`, `shield.power_w`
- восстановление: `shields.recharge_w`, `shields.recharge_rate_w`, `shields.recharge_pct_s`
- состояние/режим: `shields.state`, `shields.active`, `shields.mode`
- энергия на щит (best-effort): `shields.energy_wh`, `shield.energy_wh`, `shields.energy_j`

Derived:
- `level_pct` вычисляется из `hp/hp_max`, если прямого процента нет.
- восстановление выводится либо в `Вт`, либо в `%/с` в зависимости от доступного источника.

Пороги Shields:
- уровень: `<30%` -> `ПРЕДУПРЕЖДЕНИЕ`, `<10%` -> `КРИТИЧНО`
- состояние: `OFFLINE/FAULT` не считается `НОРМА` (эскалация до warn/crit по типу значения)

Summary Shields:
- `Щит 45%, расход 120 Вт`
- при отсутствии данных: `Нет данных`

## Операционная заметка (проверки)

На этом этапе unit-проверки (`ruff` + `pytest`) подтверждены локально.
Docker-проверка `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest ...`
может требовать предварительного старта `qiki-dev`; при не поднятом сервисе compose вернет:
`service "qiki-dev" is not running`.

## Как добавить новое поле

1. Добавить чтение значения в `collector.py` (`_v(...)`).
2. Создать `TelemetryField` через `mk_field(...)`.
3. Назначить статус через helper из `thresholds.py`.
4. Проверить, что подсистема корректно агрегирует статус через `merge_status`.
5. Добавить/обновить unit-тест.

## Как добавить новую подсистему

1. Добавить `title` в `_SUBSYSTEM_TITLES`.
2. Реализовать метод `_new_subsystem(...)` в `collector.py`.
3. Подключить его в `update(...)`.
4. Обновить тест на наличие подсистем.

## UI integration (этап 8.3.8)

Экран `F2` (Системы) переключен на единый источник `hardware_view_model`.

- Источник данных в приложении:
  - `OrionVApp.hardware_collector: HardwareCollector`
  - `OrionVApp.hardware_model: HardwareViewModel | None`
  - `OrionVApp._snapshot: dict[str, Any]`
- На каждом telemetry update:
  - входящий payload мерджится в `_snapshot`
  - вызывается `hardware_collector.update(_snapshot)`
  - актуальная модель передается в `screens/systems.py`
- `F2` больше не строит сводку из разрозненных `modules/*`;
  вместо этого рендерит карточки из `hardware_model.subsystems`.
- В `F2` всегда отображается фиксированный операторский список подсистем.
  Если подсистема/поле отсутствует в модели, выводится `НЕТ_ДАННЫХ` и значение `Нет данных`.

## Key aliases (binding layer, этап 8.3.9)

Для первичной привязки реальной телеметрии добавлен слой канонизации ключей:
`src/qiki/services/operator_console/orion_v/hardware_view_model/key_aliases.py`.

- `KEY_ALIASES` описывает алиасы для канонических ключей hardware view model.
- `canonicalize_snapshot(snapshot)`:
  - выбирает первое найденное значение по списку алиасов;
  - добавляет канонический ключ в снимок;
  - не удаляет исходные ключи (обратная совместимость).

Это позволяет быстро закрывать расхождения имён ключей без изменений UI/подсистем.

## Diagnostics (этап 8.3.12)

В `hardware_view_model` добавлена диагностическая связка для ответа на вопрос
`почему Нет данных`:

- единый реестр алиасов/канонических ключей: `key_aliases.py`;
- coverage-отчёт по полям подсистем;
- missing-keys отчёт (top-N) по каноническим ключам.

### Как включить

Только через ENV-флаг:

- `ORIONV_HWM_DIAG=1` — включает диагностику;
- `ORIONV_HWM_DIAG_PERIOD_S` (опц., default `10`) — период логов (rate-limit);
- `ORIONV_HWM_DIAG_TOP_N` (опц., default `3`) — сколько missing-ключей показывать на подсистему.

Без `ORIONV_HWM_DIAG=1` runtime поведение не меняется.

### Что считается filled в coverage

Coverage считается по `SubsystemView.fields` (не по raw snapshot).

Поле считается заполненным, если `TelemetryField.status != НЕТ_ДАННЫХ`.

### Формат логов

Coverage:

`HWM coverage: comms 3/9 power 6/11 sensors 14/44 ...`

Missing (с накоплением частоты отсутствий):

`HWM missing(comms): comms.age_s(18), comms.snr_db(15), comms.rssi_dbm(11)`

`HWM missing(power): power.draw_w(12), power.bus_v(7), power.soc(3)`

### Как расширять

В `key_aliases.py`:

- `CANONICAL_KEYS` — канонический реестр алиасов (normalization layer);
- `SUBSYSTEM_KEYSETS` — ключи, которые ожидаются для каждой подсистемы в missing-репорте.

Правило: канонизация snapshot добавляет канонические ключи, но не удаляет исходные.

## Comms: age rules and thresholds (этап 8.3.9)

Подсистема `comms` переведена на операторскую модель качества канала.

### Канонические ключи

- `comms.link_state`
- `comms.latency_ms`
- `comms.packet_loss_pct`
- `comms.rssi_dbm`
- `comms.snr_db`
- `comms.last_seen_ts`
- `comms.age_s`
- `comms.plane_enabled`
- `comms.plane_profile`

### Правило вычисления возраста данных (`age_s`)

1. Если есть `comms.last_seen_ts`, то `age_s = now_ts - last_seen_ts` (приоритетный путь).
2. Иначе, если есть `comms.age_s`, используется оно.
3. Иначе `age_s = Нет данных` и статус поля `НЕТ_ДАННЫХ` (не `НОРМА`).

### Пороги Comms (thresholds.py)

- `COMMS_LAT_WARN_MS`, `COMMS_LAT_CRIT_MS`
- `COMMS_LOSS_WARN_PCT`, `COMMS_LOSS_CRIT_PCT`
- `COMMS_AGE_WARN_S`, `COMMS_AGE_CRIT_S`

Итоговый статус `comms` определяется по максимальной критичности latency/loss/age/link-state.
Если все ключевые сигналы отсутствуют, подсистема остаётся `НЕТ_ДАННЫХ`.

### Summary

- при наличии latency/loss: `Связь: НОРМА, 45мс, loss 0.2%, age 1с`
- при деградации/критике — префикс меняется на `ПЛОХО`/`КРИТИЧНО`
- при отсутствии данных: `Нет данных`

## Thermal (этап 8.3.10)

Подсистема `thermal` переведена на операторскую модель с core/delta/trend/age.

### Канонические ключи и алиасы

- `thermal.core_c`:
  - `thermal.core_c`, `sensor_thermal.core_c`, `sensor_thermal.temp_c`, `thermal.temp_c`, `temp_core_c`
- `thermal.radiator_c`:
  - `thermal.radiator_c`, `thermal.ambient_c`, `sensor_thermal.ambient_c`
- `thermal.last_seen_ts`:
  - `thermal.last_seen_ts`, `thermal.ts`
- `thermal.age_s`:
  - `thermal.age_s`

### Derived

- `ΔT`: `core_c - radiator_c` (если доступны оба значения).
- `trend`: только по правилу `current-prev` (без истории N):
  - `prev` хранится в collector как последнее `thermal.core_c`;
  - `diff > +0.2` -> `растёт`;
  - `diff < -0.2` -> `падает`;
  - иначе `стабильно`;
  - если предыдущего значения нет -> `Нет данных`.

### Age rule

Как в Comms:
1. приоритет `thermal.last_seen_ts` (`age = now - ts`);
2. fallback `thermal.age_s`;
3. иначе `Нет данных`.

### Пороги THERMAL_*

- `THERMAL_CORE_WARN_C`, `THERMAL_CORE_CRIT_C`
- `THERMAL_DELTA_WARN_C`, `THERMAL_DELTA_CRIT_C`
- `THERMAL_TREND_WARN_C` (зарезервирован для будущего использования)

### Summary

- `Тепло: 72°C, ΔT 12°C, (растёт)`
- при отсутствии значений: `Нет данных`

## Compute (этап 8.3.11)

Подсистема `compute` строится вокруг heartbeat-age как главного индикатора живости.

### Канонические ключи и алиасы

- `compute.last_seen_ts`:
  - `compute.last_seen_ts`, `compute.heartbeat_last_seen_ts`,
    `mcqpu.heartbeat_ts`, `mainboard.heartbeat_ts`
- `compute.heartbeat_age_s`:
  - `compute.heartbeat_age_s`, `mcqpu.age_s`, `mainboard.age_s`
- `compute.cpu_pct`:
  - `compute.cpu_pct`, `mcqpu.cpu_pct`, `mainboard.cpu_pct`, `cpu_usage`
- `compute.ram_pct`:
  - `compute.ram_pct`, `mcqpu.ram_pct`, `mainboard.ram_pct`, `memory_usage`, `compute.memory_pct`
- `compute.temp_c`:
  - `compute.temp_c`, `mcqpu.temp_c`, `mainboard.temp_c`
- `compute.protocol_errors`:
  - `compute.protocol_errors`, `compute.proc_errors`, `mainboard.protocol_errors`, `mcqpu.protocol_errors`

### Heartbeat priority rule

1. Если есть `last_seen_ts`, heartbeat-age считается как `now - last_seen_ts`.
2. Иначе используется `compute.heartbeat_age_s`.
3. Если heartbeat-age > `COMPUTE_HEARTBEAT_CRIT_S`, подсистема `compute` считается `КРИТИЧНО`
   даже при отсутствии CPU/RAM.
4. Если heartbeat-age > `COMPUTE_HEARTBEAT_WARN_S`, минимум `ПРЕДУПРЕЖДЕНИЕ`.
5. Отсутствие heartbeat не повышает статус до `НОРМА`.

### Пороги COMPUTE_*

- `COMPUTE_HEARTBEAT_WARN_S`, `COMPUTE_HEARTBEAT_CRIT_S`
- `COMPUTE_CPU_WARN_PCT`, `COMPUTE_CPU_CRIT_PCT`
- `COMPUTE_RAM_WARN_PCT`, `COMPUTE_RAM_CRIT_PCT`
- `COMPUTE_TEMP_WARN_C`, `COMPUTE_TEMP_CRIT_C`

### Summary

- норма: `Compute: heartbeat 2с, CPU 55%`
- критичный heartbeat: `Compute: heartbeat 45с (КРИТИЧНО)`
- при отсутствии данных: `Нет данных`
