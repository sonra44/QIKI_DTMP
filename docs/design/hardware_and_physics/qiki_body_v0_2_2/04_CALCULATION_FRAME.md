# QIKI Body v0.2.2 — Расчётный каркас

## 0. Назначение документа

Этот документ задаёт расчётный каркас для **QIKI Body v0.2.2**.

Он переводит канон тела QIKI в набор таблиц, полей, статусов, проверок и шаблонов, через которые будущая runtime-реализация сможет работать с телом QIKI как с физической и проверяемой системой.

Этот документ не является финальным инженерным расчётом.

Этот документ не задаёт окончательные численные значения.

Этот документ не утверждает, что текущий runtime уже содержит эти таблицы, схемы или проверки.

Этот документ задаёт target structure: где должны жить значения, какие поля нужны, какие статусы допустимы и какие элементы требуют расчёта.

Главное правило:

Если элемент влияет на тело QIKI, он должен попасть в расчётную карту.

Если элемент не имеет массы, точки установки, питания, тепла, ограничений и reason_code, он не является runtime-модулем.

Если значение не рассчитано, нужно писать `TBD` или `calculation-required`.

Если таблица является целью, но ещё не существует в runtime, нужно писать `target-only`.

Если есть шаблон, но нет экземпляров, нужно писать `template-only`.

---

## 1. Статус документа

Файл:

`04_CALCULATION_FRAME.md`

Версия:

`v0.2.2`

Статус:

`calculation frame / target-only / documentation-only`

Runtime conformance:

`not claimed`

Primary source:

`01_BODY_CANON.md`

Related source files:

`00_INDEX.md`

`02_REQUIREMENTS.md`

`03_ARCHITECTURE_VIEWPOINTS.md`

`05_ENGINEERING_RATIONALE.md`

`06_INTERFACE_CONTROL.md`

`07_ADR/`

`08_IMPLEMENTATION_BRIDGE.md`

`09_ACCEPTANCE_CHECKS.md`

`10_READER_MANUAL.md`

---

## 2. Общие правила расчётного каркаса

Расчётный каркас QIKI работает на трёх уровнях.

Первый уровень — игровая инженерная правдоподобность.

На этом уровне не требуется промышленная точность, но требуется честная цена: масса, тепло, питание, инерция, расход, риск, ограничение, деградация и видимый reason_code.

Второй уровень — runtime-совместимость.

Поля должны быть такими, чтобы в будущем их можно было передать в симуляцию, телеметрию, ORION, audit, blackbox и command gating.

Третий уровень — расширяемость.

На v0.2.2 часть таблиц может быть заполнена грубыми статусами, классами и TBD. Позже эти же таблицы должны принять точные значения без смены архитектуры документа.

---

## 3. Базовые единицы

| Параметр | Единица | Назначение |
|---|---:|---|
| Масса | kg | Масса корпуса, модулей, баков, топлива, внешних блоков |
| Расстояние | m | Смещения, габариты, плечи сил, local position |
| Сила | N | Тяга сопел и внешние силовые эффекты |
| Момент | N·m | Управляющий момент RCS |
| Энергия | Wh / J | Запас батареи, supercap, расход команды |
| Мощность | W | Генерация, нагрузка, пиковое потребление |
| Температура | °C / K | Температура узлов и ограничения |
| Тепло | W / J | Тепловыделение, тепловой поток, cooldown |
| Скорость | m/s | Линейное движение |
| Угловая скорость | rad/s | Вращение тела |
| Время | s | Импульс, задержка, cooldown, duty-cycle |
| Доля заряда | % | SoC_bat, SoC_cap |
| Статус | enum | Состояние узла, команды, модуля или интерфейса |
| Доверие | enum | trusted / degraded / conflicting / stale / missing |

---

## 4. Координатная система

Координатная система должна быть зафиксирована до заполнения точных чисел.

### 4.1. Origin

`origin` — геометрический центр базового корпуса QIKI.

### 4.2. Body frame

`body_frame` — локальная система координат тела QIKI.

Оси X / Y / Z относятся к телу, а не к камере, экрану, ORION или текущему направлению взгляда оператора.

### 4.3. Face normal

`face_normal` — нормаль конкретной грани в body frame.

Нормаль нужна для:

сенсоров;

радиаторов;

антенн;

байонетов;

RCS plume-clearance;

выносных модулей;

защитных дефлекторов;

расчёта thrust / torque;

расчёта конфликтов обзора и сброса тепла.

### 4.4. CoM

`CoM` — центр масс текущей конфигурации.

`CoM_delta` — смещение центра масс относительно базового центра.

### 4.5. Правило

ORION может переводить body frame в человекочитаемое представление, но runtime не должен путать экранные направления с физическими осями тела.

---

## 5. Статусы расчётных элементов

### 5.1. `canon`

Принцип закреплён в каноне.

Не означает implemented.

### 5.2. `target-only`

Структура или правило являются целевыми, но runtime ещё не обязан их поддерживать.

### 5.3. `template-only`

Шаблон задан, но заполненные экземпляры отсутствуют.

### 5.4. `rules-only`

Правила заданы, но runtime enforcement или protocol не заявлены.

### 5.5. `calculation-required`

Нужен расчёт до утверждения значения.

### 5.6. `TBD`

Значение пока не определено.

### 5.7. `implemented`

Функция или таблица есть в runtime.

Запрещено использовать без evidence.

### 5.8. `verified`

Функция или таблица есть в runtime и прошла проверку.

Запрещено использовать без evidence и verification.

### 5.9. `superseded`

Старая формулировка или структура заменена.

### 5.10. `rejected`

Вариант рассмотрен и отклонён.

---

## 6. Face Map

Face Map — базовая карта двенадцати граней QIKI.

Без Face Map нельзя честно устанавливать модули, рассчитывать сенсорные зоны, проверять RCS plume-clearance, размещать радиаторы, проверять байонетные конфликты и показывать body configuration в ORION.

### 6.1. Минимальные поля Face Map

| Поле | Тип | Назначение | Статус v0.2.2 |
|---|---|---|---|
| face_id | enum/string | Постоянный идентификатор грани | canon |
| base_role | enum/string | Базовая роль грани | target-only |
| face_normal | vector3 | Нормаль грани в body frame | calculation-required |
| allowed_mount_classes | list | Что можно ставить | target-only |
| forbidden_mount_classes | list | Что нельзя ставить | target-only |
| neighbor_faces | list | Соседние грани | calculation-required |
| sensor_conflicts | list | Возможные конфликты сенсоров | target-only |
| rcs_plume_conflicts | list | Конфликты RCS plume | calculation-required |
| thermal_role | enum | Тепловая роль грани | target-only |
| comms_role | enum | Роль для связи / антенн | target-only |
| service_access | enum | Доступность обслуживания | target-only |
| runtime_status | enum | Статус готовности | target-only |

### 6.2. Минимальная таблица Face Map

| face_id | Базовая роль | Нормаль | Можно ставить | Нельзя ставить | Конфликты | Статус |
|---|---|---|---|---|---|---|
| F00 | Bayonet A | TBD | bayonet modules, bridge, docking | RCS cluster, large radiator | bridge vs aggressive burn | canon / geometry TBD |
| F01 | Bayonet B | TBD | bayonet modules, bridge, docking | RCS cluster, large radiator | bridge vs aggressive burn | canon / geometry TBD |
| F02 | RCS cluster candidate | TBD | RCS, small thermal panel | large sensor, large radiator | plume, heat, CoM | TBD |
| F03 | RCS cluster candidate | TBD | RCS, small thermal panel | large sensor, large radiator | plume, heat, CoM | TBD |
| F04 | RCS cluster candidate | TBD | RCS, small thermal panel | large sensor, large radiator | plume, heat, CoM | TBD |
| F05 | RCS cluster candidate | TBD | RCS, small thermal panel | large sensor, large radiator | plume, heat, CoM | TBD |
| F06 | sensor / mission slot | TBD | sensor, antenna, science module | hot thrust module | field, vibration, EMCON | TBD |
| F07 | sensor / mission slot | TBD | sensor, antenna, science module | hot thrust module | field, vibration, EMCON | TBD |
| F08 | thermal / radiator slot | TBD | radiator, thermal panel | clean-view sensor | sun angle, deployment | TBD |
| F09 | thermal / radiator slot | TBD | radiator, thermal panel | clean-view sensor | sun angle, deployment | TBD |
| F10 | utility / armor slot | TBD | armor, service, small module | heavy tank without compensation | CoM, access | TBD |
| F11 | utility / armor slot | TBD | armor, service, small module | heavy tank without compensation | CoM, access | TBD |

### 6.3. Правило Face Map

Пока `face_id` не имеет роли и ограничений, модуль на эту грань не должен считаться runtime-объектом.

Если нормаль грани не рассчитана, точные сенсорные и RCS-эффекты должны иметь статус `calculation-required`.

---

## 7. Mount Compatibility Matrix

Mount Compatibility Matrix задаёт, какие классы модулей могут устанавливаться на какие типы точек крепления.

### 7.1. Типы установки

| mount_type | Смысл |
|---|---|
| face-mounted | Модуль установлен на конкретную грань |
| bayonet-mounted | Модуль подключён через байонет |
| internal | Модуль внутри тела |
| paired | Модуль требует парной установки или компенсации |
| deployable | Модуль меняет геометрию после раскрытия |
| external-tethered | Модуль связан внешним тросом / штангой / контуром |
| station-linked | Модуль или источник связан со станцией |
| sled-class external | Тяжёлый внешний блок / санный / буксируемый класс |
| Terta-exotic attachment | Экзотическое подключение, не baseline |

### 7.2. Совместимость классов модулей

| Класс модуля | face-mounted | bayonet-mounted | internal | paired | deployable | Комментарий |
|---|---:|---:|---:|---:|---:|---|
| sensor module | Да | Иногда | Иногда | Нет | Иногда | Требует обзора, калибровки, защиты от вибрации |
| radiator module | Да | Иногда | Нет | Иногда | Да | Требует геометрии теплового сброса |
| battery module | Иногда | Да | Да | Иногда | Нет | Влияет на массу, тепло, заряд/разряд |
| supercap module | Иногда | Да | Да | Иногда | Нет | Влияет на пики и boost-разрешения |
| working mass tank | Иногда | Да | Иногда | Иногда | Нет | Меняет массу по мере расхода |
| chemical thrust module | Да | Да | Нет | Часто | Нет | Требует plume-clearance и safety |
| electric thrust module | Да | Да | Нет | Иногда | Нет | Требует мощности и охлаждения |
| comms module | Да | Да | Иногда | Нет | Иногда | Конфликтует с EMCON |
| NBL module | Обычно нет | Да | Иногда | Нет | Иногда | Только emergency low-rate или Terta-exotic |
| radiation deflector | Обычно нет | Да | Нет | Часто | Да | Лучше как выносной / разворачиваемый контур |
| armor / shield plate | Да | Нет | Нет | Иногда | Нет | Закрывает поверхность, влияет на массу и сенсоры |
| compute module | Иногда | Да | Да | Нет | Нет | Греет core / compute node |
| reactor-class source | Нет | Только external / station / sled | Нет | Нет | Нет | Не является обычным face module |

### 7.3. Правило совместимости

Если модуль не имеет допустимого mount_type, он не является runtime-модулем.

Если модуль конфликтует с занятым face_id, RCS plume, радиатором, сенсором, байонетом или EMCON, установка должна быть rejected или помечена как calculation-required.

---

## 8. Mass / CoM / Inertia Sheet

Mass / CoM / Inertia Sheet описывает массу, центр масс и инерцию тела QIKI.

Если модуль не имеет массы, он не является физическим модулем.

Если модуль имеет массу, но не влияет на CoM и inertia, описание неполно.

### 8.1. Минимальные поля

| Поле | Тип | Назначение |
|---|---|---|
| entity_id | string | ID тела, подсистемы или модуля |
| entity_type | enum | body / subsystem / module / external |
| mass_kg | number / TBD | Масса |
| local_position_m | vector3 / TBD | Положение в body frame |
| mount_point | string / TBD | Грань, байонет, internal slot, external |
| CoM_impact | enum / vector | Влияние на центр масс |
| inertia_impact | enum / matrix / TBD | Влияние на момент инерции |
| dynamic_mass | bool | Меняется ли масса при расходе |
| restrictions | list | Ограничения манёвров / команд |
| status | enum | Статус значения |

### 8.2. Минимальная таблица

| entity_id | Тип | mass_kg | local_position_m | CoM impact | inertia impact | Status |
|---|---|---:|---|---|---|---|
| CORE_BODY | body | TBD | 0 / 0 / 0 | baseline | baseline | canon / value TBD |
| BAT_MAIN | battery | TBD | TBD | low / medium | medium | target-only |
| CAP_MAIN | supercap | TBD | TBD | low | low / medium | target-only |
| PDU_MAIN | PDU | TBD | TBD | low | low | target-only |
| BAYONET_A | bayonet | TBD | TBD | axis A | medium | canon |
| BAYONET_B | bayonet | TBD | TBD | axis B | medium | canon |
| RCS_C01 | RCS cluster | TBD | TBD | local | medium | geometry TBD |
| RCS_C02 | RCS cluster | TBD | TBD | local | medium | geometry TBD |
| RCS_C03 | RCS cluster | TBD | TBD | local | medium | geometry TBD |
| RCS_C04 | RCS cluster | TBD | TBD | local | medium | geometry TBD |
| SENSOR_HEAD | sensor node | TBD | TBD | local | low / medium | target-only |
| COMMS_MAIN | comms node | TBD | TBD | local | low | target-only |
| MODULE_X | external module | by passport | by passport | by passport | by passport | passport required |

### 8.3. CoM_delta classes

| Class | Смысл | Последствие |
|---|---|---|
| C0 nominal | Смещение пренебрежимо | Полные штатные манёвры, если остальные системы в норме |
| C1 minor | Небольшой перекос | Компенсация контроллером, предупреждение ORION |
| C2 restricted | Значимый перекос | Ограничение aggressive burn, docking caution |
| C3 unstable | Сильный перекос | Запрет опасных манёвров, требуется reconfiguration |
| C4 invalid | Конфигурация недопустима | Команды движения rejected |

### 8.4. Inertia classes

| Class | Смысл | Последствие |
|---|---|---|
| I0 baseline | Базовая инерция | Штатное управление |
| I1 light-shift | Небольшое изменение | Предупреждение |
| I2 heavy-axis | Перегружена одна ось | Ограничение вращения |
| I3 external-load | Внешний объект / tether / bridge | Restricted motion |
| I4 unmodeled | Инерция неизвестна | Dangerous motion rejected |

---

## 9. Power Budget Sheet

Power Budget Sheet описывает генерацию, запас, распределение, нагрузки и пиковые действия.

### 9.1. Основная формула

`source → battery → bus → supercap → peak consumers`

### 9.2. Минимальные поля

| Поле | Тип | Назначение |
|---|---|---|
| source_id | string | Источник энергии |
| source_class | enum | solar / chemical / RTG / external / Terta-exotic |
| generation_W | number / TBD | Средняя генерация |
| battery_soc_pct | number / TBD | Запас жизни |
| battery_capacity_Wh | number / TBD | Ёмкость батареи |
| battery_charge_W | number / TBD | Заряд батареи |
| battery_discharge_W | number / TBD | Разряд батареи |
| supercap_soc_pct | number / TBD | Готовность к пику |
| supercap_capacity_Wh | number / TBD | Ёмкость supercap |
| supercap_charge_W | number / TBD | Заряд supercap |
| supercap_discharge_W | number / TBD | Разряд supercap |
| bus_voltage_V | number / TBD | Напряжение шины |
| bus_current_A | number / TBD | Ток шины |
| load_W | number / TBD | Текущая нагрузка |
| peak_available | bool / TBD | Доступен ли пик |
| blocked_peak_commands | list | Заблокированные пиковые команды |
| reason_codes | list | Причины отказа |
| status | enum | Статус значения |

### 9.3. Классы источников

| source_class | Каноническая роль | Ограничение |
|---|---|---|
| solar | средняя генерация при освещении | не даёт мгновенный пик без буфера |
| battery | долгий запас жизни | не заменяет supercap |
| supercap | право на быстрые действия | не является долгой батареей |
| chemical / fuel-cell-class | энергия при наличии реагентов | масса, расход, тепло |
| RTG-class | heavy / trickle source | не boost-source |
| external reactor-class | external / station / sled | не face-mounted module |
| Terta-exotic | экзотический профиль | только с явной маркировкой и ценой |

### 9.4. Peak consumer table

| Команда / нагрузка | Требует SoC_cap | Требует PDU | Требует thermal clearance | Комментарий |
|---|---:|---:|---:|---|
| RCS boost | Да | Да | Да | Пик движения |
| emergency burn | Да | Да | Да | Может требовать working mass |
| high-power scan | Да | Да | Да | Греет sensor head |
| NBL emergency packet | Да | Да | Да | Только critical use |
| active field / deflector | Да | Да | Да | Если установлен |
| emergency detach | Иногда | Да | Да | Зависит от bayonet state |
| rapid compute burst | Да | Да | Да | Греет core |
| high-rate comms burst | Да | Да | Да | Греет comms |

### 9.5. Типовые reason_codes

`CAP_LOW`

`CAP_HOT`

`BAT_LOW`

`PDU_PEAK_DENIED`

`PDU_OVERLOAD`

`SOURCE_UNAVAILABLE`

`EXTERNAL_POWER_UNSAFE`

`BAYONET_POWER_UNSAFE`

`SAFE_LOCKED`

---

## 10. Thermal Budget Sheet

Thermal Budget Sheet описывает тепловые узлы, нагрузку, перегрев, cooldown и блокировки.

### 10.1. Минимальные thermal nodes

| thermal_node | Назначение |
|---|---|
| CORE | вычисления / базовая электроника |
| BATTERY | батарея |
| SUPERCAP | supercap |
| PDU | распределение питания |
| RCS_C01 | RCS cluster 01 |
| RCS_C02 | RCS cluster 02 |
| RCS_C03 | RCS cluster 03 |
| RCS_C04 | RCS cluster 04 |
| SENSOR_HEAD | сенсорный узел |
| COMMS | связь |
| BAYONET_A | байонет A |
| BAYONET_B | байонет B |
| MODULE_X | внешний модуль |
| FIELD_DEFLECTOR | поле / дефлектор, если установлен |

### 10.2. Минимальные поля

| Поле | Тип | Назначение |
|---|---|---|
| thermal_node | enum/string | ID теплового узла |
| temp_current | number / TBD | Текущая температура |
| temp_nominal_max | number / TBD | Номинальный верхний предел |
| temp_warning | number / TBD | Warning threshold |
| temp_critical | number / TBD | Critical threshold |
| heat_idle_W | number / TBD | Тепло в idle |
| heat_active_W | number / TBD | Тепло при активности |
| cooldown_rate | number / TBD | Скорость охлаждения |
| blocked_commands | list | Какие команды блокируются |
| reason_codes | list | Причины отказа |
| status | enum | Статус значения |

### 10.3. Thermal state classes

| Class | Смысл | Последствие |
|---|---|---|
| T0 nominal | Узел в норме | Команды не блокируются теплом |
| T1 warm | Узел тёплый | Предупреждение |
| T2 hot | Узел горячий | Ограничение duty-cycle |
| T3 critical | Критический перегрев | Команды rejected |
| T4 unknown | Температура неизвестна | Опасные команды rejected или require confirmation |

### 10.4. Типовые reason_codes

`THERMAL_NODE_HOT`

`THERMAL_NODE_CRITICAL`

`PDU_THERMAL_BLOCK`

`CAP_HOT`

`RCS_CLUSTER_HOT`

`SENSOR_HEAD_HOT`

`COMMS_HOT`

`BAYONET_THERMAL_BLOCK`

`MODULE_THERMAL_BLOCK`

---

## 11. Thrust Map

Thrust Map описывает, какие линейные силы может создать RCS-система.

### 11.1. Статус

На v0.2.2 Thrust Map имеет статус:

`calculation-required`

Нельзя заявлять доказанную равномерную тягу без заполненной карты.

### 11.2. Минимальные поля

| Поле | Тип | Назначение |
|---|---|---|
| thruster_id | string | ID сопла |
| cluster_id | string | ID RCS-кластера |
| mount_face | face_id / TBD | Грань установки |
| local_position_m | vector3 / TBD | Положение сопла |
| thrust_direction | vector3 / TBD | Направление тяги |
| thrust_N | number / TBD | Сила тяги |
| min_impulse | number / TBD | Минимальный импульс |
| max_duration_s | number / TBD | Максимальная длительность |
| working_mass_type | enum / TBD | Рабочее тело |
| working_mass_rate | number / TBD | Расход |
| heat_node | enum | Тепловой узел |
| plume_clearance | enum / TBD | Свободна ли зона выброса |
| status | enum | Статус значения |

### 11.3. Проверяемые режимы

| Режим | Требуется |
|---|---|
| +X translation | набор сопел и CoM check |
| -X translation | набор сопел и CoM check |
| +Y translation | набор сопел и CoM check |
| -Y translation | набор сопел и CoM check |
| +Z translation | набор сопел и CoM check |
| -Z translation | набор сопел и CoM check |
| safe-brake | доступная противоположная тяга |
| docking micro-burn | low impulse + sensor trust |
| emergency burn | SoC_cap + thermal + working mass |
| restricted burn | bridge / CoM / inertia restrictions |

---

## 12. Torque Map

Torque Map описывает, какие моменты может создать RCS-система.

### 12.1. Статус

На v0.2.2 Torque Map имеет статус:

`calculation-required`

Нельзя заявлять управляемость по всем осям без Torque Map.

### 12.2. Минимальные поля

| Поле | Тип | Назначение |
|---|---|---|
| torque_mode_id | string | ID режима момента |
| active_thrusters | list | Набор сопел |
| axis | enum/vector | Ось момента |
| torque_Nm | number / TBD | Величина момента |
| residual_translation | vector3 / TBD | Остаточная линейная тяга |
| residual_rotation | vector3 / TBD | Осточный момент |
| CoM_dependency | enum | Зависимость от центра масс |
| inertia_dependency | enum | Зависимость от класса инерции |
| thermal_nodes | list | Нагруженные тепловые узлы |
| status | enum | Статус значения |

### 12.3. Проверяемые режимы

| Режим | Требуется |
|---|---|
| yaw + | moment around axis |
| yaw - | moment around axis |
| pitch + | moment around axis |
| pitch - | moment around axis |
| roll + | moment around axis |
| roll - | moment around axis |
| attitude hold | sensor trust + torque authority |
| docking attitude correction | low impulse + fresh sensors |
| tumble recovery | high confidence + SAFE policy |

---

## 13. Bayonet Bridge Sheet

Bayonet Bridge Sheet описывает механическое, энергетическое и информационное состояние байонета.

### 13.1. Состояния байонета

| State | Смысл | Bridge allowed |
|---|---|---:|
| free | свободен | Нет |
| approach | сближение | Нет |
| alignment | выравнивание | Нет |
| magnetic_pre_align | магнитное предварительное выравнивание | Нет |
| soft_capture | мягкий захват | Нет |
| mechanical_hard_lock | механический замок | Ещё нет |
| structural_check_passed | структурная проверка пройдена | Возможно после electrical safety |
| structural_check_failed | структурная проверка провалена | Нет |
| electrical_safety_passed | электрическая безопасность подтверждена | Возможно |
| umbilical_mated | umbilical подключён | Возможно |
| module_handshake_passed | handshake пройден | Возможно |
| passport_validated | паспорт подтверждён | Да, если PDU и thermal позволяют |
| bridge_allowed | bridge разрешён | Да |
| bridge_active | bridge активен | Да, restricted motion |
| bridge_degraded | bridge degraded | Ограниченно |
| emergency_detach_pending | аварийное отсоединение | Нет |
| detached | отсоединён | Нет |
| unknown | неизвестно | Нет |

### 13.2. Минимальные поля

| Поле | Тип | Назначение |
|---|---|---|
| bayonet_id | enum/string | BAYONET_A / BAYONET_B |
| connected_object_id | string / none | Подключённый объект |
| mechanical_state | enum | Механическое состояние |
| lock_quality | enum / % / TBD | Качество замка |
| structural_check | enum | structural status |
| electrical_safety | enum | electrical safety status |
| umbilical_state | enum | состояние umbilical |
| module_handshake | enum | handshake status |
| passport_state | enum | passport status |
| bridge_state | enum | bridge status |
| power_direction | enum | import / export / none |
| power_limit_W | number / TBD | Лимит мощности |
| data_link_state | enum | состояние data-link |
| thermal_node | enum | тепловой узел |
| motion_restrictions | list | ограничения движения |
| reason_codes | list | причины блокировки |

### 13.3. Типовые reason_codes

`BAYONET_STATE_UNKNOWN`

`BAYONET_SOFT_CAPTURE_ONLY`

`BAYONET_HARD_LOCK_MISSING`

`BAYONET_STRUCTURAL_CHECK_FAILED`

`BAYONET_ELECTRICAL_UNSAFE`

`BAYONET_UMBILICAL_MISSING`

`BAYONET_PASSPORT_MISSING`

`BAYONET_PASSPORT_INVALID`

`BAYONET_BRIDGE_DEGRADED`

`BAYONET_THERMAL_BLOCK`

`BRIDGE_ACTIVE_RESTRICTED_MOTION`

---

## 14. Module Passport Template

Module Passport Template описывает минимальный контракт модуля.

### 14.1. Минимальные поля паспорта

| Поле | Тип | Назначение |
|---|---|---|
| module_id | string | Уникальный ID модуля |
| module_name | string | Человекочитаемое имя |
| module_class | enum | sensor / power / thermal / thrust / comms / protection / compute / utility |
| status | enum | canon / target-only / template-only / implemented / verified |
| mount_type | enum | face / bayonet / internal / paired / deployable / external |
| mount_point | string / TBD | face_id / bayonet_id / slot_id |
| mass_kg | number / TBD | Масса |
| local_position_m | vector3 / TBD | Положение |
| CoM_impact | enum / vector / TBD | Влияние на центр масс |
| inertia_impact | enum / TBD | Влияние на инерцию |
| power_idle_W | number / TBD | Idle power |
| power_active_W | number / TBD | Active power |
| peak_power_W | number / TBD | Peak power |
| thermal_node | enum | Тепловой узел |
| heat_idle_W | number / TBD | Idle heat |
| heat_active_W | number / TBD | Active heat |
| cooldown_profile | string / TBD | Cooldown |
| provided_capabilities | list | Что модуль даёт |
| removed_capabilities | list | Что модуль забирает |
| blocked_commands | list | Какие команды блокирует |
| new_commands | list | Какие команды добавляет |
| risk_class | enum | Класс риска |
| SAFE_interactions | list | Как связан с SAFE |
| sensor_effects | list | Эффекты на сенсоры |
| comms_effects | list | Эффекты на связь |
| EMCON_effects | list | Эффекты на EMCON |
| bayonet_effects | list | Эффекты на байонеты |
| RCS_effects | list | Эффекты на RCS |
| failure_modes | list | Отказы |
| degradation_modes | list | Деградации |
| reason_codes | list | Коды отказа |
| telemetry_fields | list | Телеметрия |
| audit_requirements | list | Что писать в audit |
| blackbox_relevance | enum/list | Нужен ли blackbox |
| verification_status | enum | evidence status |

### 14.2. Правило паспорта

Модуль без паспорта не является runtime-модулем.

Если паспорт существует только как шаблон, статус должен быть `template-only`.

Если паспорт заполнен, но runtime не поддерживает модуль, статус должен быть `target-only`.

Если runtime поддерживает модуль, нужен evidence для `implemented`.

Если модуль проверен, нужен verification для `verified`.

---

## 15. NBL Emergency Packet Rules

Baseline NBL является emergency low-rate channel.

### 15.1. Минимальные поля NBL packet

| Поле | Тип | Назначение |
|---|---|---|
| packet_id | string | ID пакета |
| criticality | enum | critical / emergency / non-critical |
| payload_class | enum | distress / minimal state / beacon / command ack |
| payload_size_bits | number / TBD | Размер пакета |
| transmit_attempts | number / TBD | Попытки передачи |
| power_cost | number / TBD | Стоимость по энергии |
| cap_cost | number / TBD | Стоимость по SoC_cap |
| thermal_node | enum | Тепловой узел |
| expected_latency | number / TBD | Ожидаемая задержка |
| delivery_confidence | enum / TBD | Уверенность доставки |
| audit_required | bool | Нужно ли audit |
| blackbox_relevance | bool | Нужно ли blackbox |
| reason_codes | list | Причины отказа |

### 15.2. Правила

NBL не используется для bulk telemetry.

NBL не используется как normal comms.

NBL packet требует criticality gating.

NBL packet требует SoC_cap, PDU allowance и thermal clearance.

NBL packet должен писать audit.

NBL packet может быть blackbox relevant.

### 15.3. Reason codes

`NBL_NOT_CRITICAL`

`NBL_PAYLOAD_TOO_LARGE`

`NBL_CAP_LOW`

`NBL_THERMAL_BLOCK`

`NBL_PDU_DENIED`

`NBL_NOT_IMPLEMENTED`

`NBL_RULES_ONLY`

---

## 16. Command Gating Matrix

Command Gating Matrix описывает, какие проверки должна пройти команда.

### 16.1. Минимальные поля команды

| Поле | Тип | Назначение |
|---|---|---|
| command_id | string | Уникальный ID команды |
| command_type | enum | burn / scan / transmit / attach / detach / module / safe |
| source | enum/string | operator / QIKI / SAFE / module / script |
| target_subsystem | enum | RCS / PDU / sensor / comms / bayonet / module |
| requested_mode | string | Режим |
| requested_intensity | number / enum | Интенсивность |
| duration_s | number / TBD | Длительность |
| priority | enum | normal / urgent / emergency |
| expected_effect | string | Ожидаемый эффект |
| risk_class | enum | low / medium / high / critical |
| expiry | timestamp / TBD | Срок действия |
| operator_confirmation | enum | none / required / confirmed |
| status | enum | requested / allowed / rejected / published / ACK / effect_confirmed / failed |

### 16.2. Минимальные проверки validation

| Проверка | Когда нужна |
|---|---|
| mission profile | всегда |
| body mode | всегда |
| SAFE state | всегда |
| module passport | если команда использует модуль |
| module status | если команда использует модуль |
| mount point | если команда использует модуль или грань |
| bayonet state | если команда связана с bayonet / bridge / detach |
| SoC_bat | если команда требует энергии |
| SoC_cap | если команда пиковая |
| PDU limits | если команда включает нагрузку |
| thermal nodes | если команда греет узел |
| CoM class | если команда двигает тело |
| inertia class | если команда двигает тело |
| RCS availability | если команда использует RCS |
| working mass | если команда требует расхода |
| sensor trust | если команда зависит от восприятия |
| comms state | если команда передаёт данные |
| EMCON state | если команда излучает |
| operator access | если команда опасная |
| operator confirmation | если требуется подтверждение |
| cooldown | если команда повторная |
| audit availability | если команда critical |
| blackbox relevance | если команда critical |

### 16.3. Command lifecycle states

| State | Смысл |
|---|---|
| requested | запрос создан |
| validation_pending | идёт проверка |
| allowed | команда разрешена |
| rejected | команда запрещена |
| publish_pending | ожидает отправки |
| published | отправлена |
| publish_failed | отправка не удалась |
| ACK_accepted | нижний слой принял |
| ACK_rejected | нижний слой отклонил |
| ACK_timeout | ACK не получен |
| effect_pending | эффект ожидается |
| effect_confirmed | эффект подтверждён |
| effect_partial | эффект частичный |
| effect_timeout | эффект не подтверждён |
| aborted | команда прервана |
| audited | событие записано |

### 16.4. Reason codes

`CMD_VALIDATION_FAILED`

`CMD_UNAUTHORIZED`

`CMD_CONFIRMATION_REQUIRED`

`SAFE_LOCKED`

`CAP_LOW`

`PDU_DENIED`

`THERMAL_BLOCK`

`SENSOR_STALE`

`SENSOR_CONFLICTING`

`BAYONET_UNSAFE`

`BRIDGE_ACTIVE_RESTRICTED_MOTION`

`MODULE_PASSPORT_MISSING`

`MODULE_NOT_READY`

`RCS_UNAVAILABLE`

`THRUST_MAP_MISSING`

`TORQUE_MAP_MISSING`

`CALCULATION_REQUIRED`

`NOT_IMPLEMENTED`

---

## 17. ORION Evidence Checklist

ORION Evidence Checklist задаёт, что должен видеть оператор для важных утверждений и команд.

### 17.1. Минимальные поля evidence card

| Поле | Тип | Назначение |
|---|---|---|
| claim_id | string | ID утверждения |
| claim_text | string | Что утверждается |
| source_type | enum | telemetry / event / ACK / effect / audit / hypothesis / missing |
| source_id | string / TBD | ID источника |
| freshness | enum | fresh / acceptable / stale / expired / unknown |
| trust_status | enum | trusted / degraded / conflicting / blind / missing / hypothesis |
| status | enum | canon / target-only / implemented / verified / missing |
| related_command_id | string / none | Связанная команда |
| related_module_id | string / none | Связанный модуль |
| reason_codes | list | Причины предупреждений или отказов |
| audit_link | string / TBD | Ссылка на audit |
| blackbox_relevance | bool | Важно ли для blackbox |
| operator_action | string / none | Что может сделать оператор |

### 17.2. Что нельзя скрывать

ORION не должен скрывать:

missing source;

stale data;

conflicting sensor data;

target-only status;

not implemented status;

calculation-required status;

reason_codes;

ACK without effect confirmation;

partial effect;

SAFE block;

thermal block;

PDU block;

module passport missing;

bayonet unsafe state.

---

## 18. Open calculation-required list

Следующие элементы требуют отдельного расчёта или формализации:

точная геометрия додекаэдра QIKI;

нормали F00–F11;

соседство граней;

финальная Face Map;

точные mount constraints;

масса базового тела;

масса подсистем;

масса модулей;

local_position подсистем;

CoM_delta thresholds;

inertia matrix или inertia classes;

RCS thrust values;

RCS directions;

Thrust Map;

Torque Map;

plume-clearance zones;

working mass consumption;

battery capacity;

supercap capacity;

PDU limits;

source generation profiles;

thermal thresholds;

cooldown profiles;

bayonet structural rating;

bayonet power limits;

bridge data limits;

NBL packet size;

NBL cost;

sensor range;

sensor accuracy;

sensor update rate;

comms bandwidth;

radiation deflector effectiveness;

field / Terta-exotic effects, если они используются.

---

## 19. Acceptance for this document

`04_CALCULATION_FRAME.md` считается готовым для documentation-only package, если:

есть общие правила расчёта;

есть единицы измерения;

есть координатная система;

есть статусы;

есть Face Map skeleton;

есть Mount Compatibility Matrix;

есть Mass / CoM / Inertia Sheet;

есть Power Budget Sheet;

есть Thermal Budget Sheet;

есть Thrust Map target;

есть Torque Map target;

есть Bayonet Bridge Sheet;

есть Module Passport Template;

есть NBL Emergency Packet Rules;

есть Command Gating Matrix;

есть ORION Evidence Checklist;

все неизвестные значения помечены TBD или calculation-required;

нет invented numbers;

нет implemented claims;

нет verified claims без evidence;

нет runtime conformance claims.

---

## 20. Итоговая формула

Расчётный каркас не делает QIKI менее игровой.

Он делает игру проверяемой.

Таблица не равна реализации.

Шаблон не равен runtime schema.

TBD не равен числу.

Target-only не равен runtime-ready.

Calculation-required не равен calculated.

Implemented требует evidence.

Verified требует evidence и verification.

Если элемент влияет на тело QIKI, он должен попасть в расчётную карту.

Если элемент не попал в расчётную карту, он не должен управлять телом.
