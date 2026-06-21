# QIKI Body v0.2.2 — Управление интерфейсами

## 0. Назначение документа

Этот документ фиксирует целевой слой управления интерфейсами для **QIKI Body v0.2.2**.

Он описывает границы между подсистемами QIKI: какие данные, состояния, команды, события, разрешения, блокировки и evidence должны проходить между телом, байонетом, PDU, питанием, теплом, RCS, сенсорами, связью, NBL, модулями, command bus, ORION, audit, blackbox и SAFE.

Этот документ не является runtime-реализацией.

Этот документ не меняет proto, NATS, gRPC, telemetry paths, ORION UI или MFD.

Этот документ не утверждает, что описанные интерфейсы уже реализованы.

Он задаёт target interface records: какие интерфейсы должны существовать, какие поля им нужны, какие состояния разрешают обмен, какие состояния блокируют обмен и какие reason_codes должны появляться при отказе.

Главная формула:

Подсистема не считается подключённой, если не описан её интерфейс.

Интерфейс не считается безопасным, если не описаны разрешающие и запрещающие состояния.

Команда не считается доставленной, если нет publish / ACK.

Эффект не считается доказанным, если нет effect confirmation.

Данные не считаются доказательными, если неизвестны source, freshness и trust.

Bridge не считается активным, если не пройдены lock, safety, handshake и passport validation.

---

## 1. Статус документа

Файл:

`06_INTERFACE_CONTROL.md`

Версия:

`v0.2.2`

Статус:

`interface control / target-only / documentation-only`

Runtime conformance:

`not claimed`

Primary source:

`01_BODY_CANON.md`

Related source files:

`00_INDEX.md`

`02_REQUIREMENTS.md`

`03_ARCHITECTURE_VIEWPOINTS.md`

`04_CALCULATION_FRAME.md`

`05_ENGINEERING_RATIONALE.md`

`07_ADR/`

`08_IMPLEMENTATION_BRIDGE.md`

`09_ACCEPTANCE_CHECKS.md`

`10_READER_MANUAL.md`

---

## 2. Что такое interface

Interface — это граница между двумя или более подсистемами QIKI, через которую передаются:

состояние;

команда;

питание;

данные;

событие;

evidence;

audit record;

blackbox record;

физическое соединение;

разрешение;

запрет;

reason_code.

Интерфейс может быть:

механическим;

энергетическим;

информационным;

командным;

телеметрическим;

доказательным;

аудитным;

blackbox;

операторским;

репозиторным.

---

## 3. Что interface не делает

Interface record не является реализацией.

Описание интерфейса не означает, что runtime уже его поддерживает.

Описание required fields не означает, что telemetry path уже существует.

Описание reason_codes не означает, что code уже возвращает эти коды.

Описание ORION evidence не означает, что ORION UI уже показывает эти поля.

Описание audit requirements не означает, что audit stream уже реализован.

Описание blackbox relevance не означает, что blackbox уже пишет эти события.

Если runtime evidence отсутствует, статус должен оставаться `target-only`, `template-only`, `rules-only` или `not implemented`.

---

## 4. Минимальный interface record

Каждый interface record должен иметь следующие поля:

| Поле | Назначение |
|---|---|
| interface_id | Уникальный ID интерфейса |
| name | Человекочитаемое имя |
| purpose | Зачем нужен интерфейс |
| producer | Кто производит состояние / команду / данные |
| consumer | Кто потребляет состояние / команду / данные |
| direction | Направление обмена |
| trigger | Что запускает обмен |
| allowed_states | В каких состояниях обмен разрешён |
| blocked_states | В каких состояниях обмен запрещён |
| required_fields | Обязательные поля |
| optional_fields | Необязательные поля |
| units | Единицы измерения |
| status | Статус интерфейса |
| related_requirements | Связанные REQ-* |
| related_viewpoints | Связанные viewpoints |
| reason_codes | Коды причин отказа |
| failure_modes | Режимы отказа |
| ORION_evidence | Что должен видеть ORION |
| audit_requirements | Что должно попадать в audit |
| blackbox_relevance | Что критично для blackbox |
| open_issues | Открытые вопросы |

---

## 5. Статусы интерфейса

### 5.1. `canon`

Интерфейс принят как часть архитектуры.

Не означает implemented.

### 5.2. `target-only`

Интерфейс должен существовать в будущем, но runtime ещё не обязан его поддерживать.

### 5.3. `template-only`

Есть шаблон интерфейса, но нет конкретных экземпляров.

### 5.4. `rules-only`

Есть правила обмена, но нет утверждённого runtime protocol.

### 5.5. `calculation-required`

Нужны расчёты до реализации или проверки.

### 5.6. `implemented`

Интерфейс реализован в runtime.

Запрещено использовать без evidence.

### 5.7. `verified`

Интерфейс реализован и проверен.

Запрещено использовать без evidence и verification.

### 5.8. `superseded`

Интерфейс заменён новым.

### 5.9. `rejected`

Интерфейс рассмотрен и отклонён.

---

## 6. Типы блокировок

Интерфейс может быть заблокирован по причинам:

state missing;

safety missing;

passport missing;

thermal block;

power block;

authorization block;

EMCON block;

SAFE block;

stale data;

conflicting data;

unsupported mode;

calculation missing;

target-only;

not implemented.

Блокировка должна возвращать reason_code.

Немой отказ недопустим.

---

## 7. Interface catalog v0.2.2

Минимальный каталог интерфейсов QIKI Body v0.2.2:

| interface_id | Name | Status |
|---|---|---|
| IF-BAYONET-MECH-001 | Bayonet Mechanical State Interface | canon / target-only |
| IF-BAYONET-BRIDGE-001 | Bayonet Power/Data Bridge Interface | canon / target-only |
| IF-MODULE-PASSPORT-001 | Module Passport Handshake Interface | canon / template-only |
| IF-PDU-POWER-001 | PDU Load Permission Interface | canon / target-only |
| IF-POWER-TELEM-001 | Battery / Supercap Telemetry Interface | canon / target-only |
| IF-THERMAL-TELEM-001 | Thermal Node Telemetry Interface | canon / target-only |
| IF-RCS-CMD-001 | RCS Command Interface | canon / target-only |
| IF-SENSOR-TELEM-001 | Sensor Telemetry Interface | canon / target-only |
| IF-COMMS-001 | Normal Communication Interface | canon / target-only |
| IF-NBL-001 | NBL Emergency Packet Interface | rules-only / target-only |
| IF-CMD-BUS-001 | Command Bus / Lifecycle Interface | canon / target-only |
| IF-ORION-EVIDENCE-001 | ORION Evidence Feed Interface | canon / target-only |
| IF-AUDIT-001 | Audit Event Stream Interface | canon / target-only |
| IF-BLACKBOX-001 | Blackbox Record Interface | canon / target-only |
| IF-SAFE-001 | SAFE State Interface | canon / target-only |

---

## 8. IF-BAYONET-MECH-001 — Bayonet Mechanical State Interface

### 8.1. Purpose

Описать механическое состояние байонета и границу между свободным телом QIKI, сближением, soft capture, hard lock, degraded lock и emergency detach.

### 8.2. Producer

Bayonet controller.

Simulation / world model, если байонет пока моделируется симуляционно.

### 8.3. Consumers

PDU;

module passport handshake;

command gating;

RCS controller;

ORION;

audit;

blackbox.

### 8.4. Direction

Bayonet controller → system state consumers.

### 8.5. Allowed states

free;

approach;

alignment;

magnetic_pre_align;

soft_capture;

mechanical_hard_lock;

structural_check_passed;

structural_check_failed;

degraded_lock;

emergency_detach_pending;

detached;

unknown.

### 8.6. Blocked meanings

`soft_capture` не разрешает power bridge.

`soft_capture` не разрешает aggressive burn.

`magnetic_pre_align` не является lock.

`unknown` не разрешает bridge.

`degraded_lock` требует restricted motion.

`structural_check_failed` запрещает bridge allowed.

### 8.7. Required fields

bayonet_id;

state;

state_timestamp;

state_source;

lock_quality;

structural_rating;

degraded_reason;

connected_object_id;

mechanical_load_class;

emergency_detach_available.

### 8.8. Units

state_timestamp — timestamp;

lock_quality — enum или percentage;

mechanical_load_class — enum;

structural_rating — enum.

### 8.9. Reason codes

BAYONET_STATE_UNKNOWN;

BAYONET_SOFT_CAPTURE_ONLY;

BAYONET_HARD_LOCK_MISSING;

BAYONET_STRUCTURAL_CHECK_FAILED;

BAYONET_DEGRADED_LOCK;

BAYONET_EMERGENCY_DETACH_PENDING;

BAYONET_CONNECTED_OBJECT_UNKNOWN.

### 8.10. ORION evidence

ORION должен показывать:

bayonet_id;

state;

lock quality;

structural status;

connected object;

bridge availability;

motion restrictions;

reason_codes.

### 8.11. Audit requirements

Audit должен писать:

state transition;

source;

previous state;

new state;

connected object;

reason_codes;

operator confirmation, если была команда detach.

### 8.12. Blackbox relevance

Blackbox relevant:

hard_lock failure;

structural_check_failed;

emergency_detach;

unexpected detach;

degraded_lock during motion.

### 8.13. Status

`canon / target-only`

---

## 9. IF-BAYONET-BRIDGE-001 — Bayonet Power/Data Bridge Interface

### 9.1. Purpose

Описать разрешение power/data bridge через байонет.

Bridge не должен быть активен только потому, что объект физически приблизился или находится в soft capture.

### 9.2. Producer

Bayonet controller;

PDU;

module passport validator.

### 9.3. Consumers

PDU;

module runtime;

command gating;

ORION;

audit;

blackbox.

### 9.4. Direction

Bayonet controller + passport validator + PDU → bridge state.

### 9.5. Required validation chain

mechanical_hard_lock;

structural_check_passed;

electrical_safety_passed;

umbilical_mated;

module_handshake_passed;

passport_validated;

PDU_allowance;

thermal_clearance.

### 9.6. Allowed states

bridge_disallowed;

bridge_pending;

bridge_allowed;

bridge_active;

bridge_degraded;

bridge_shutdown;

bridge_failed.

### 9.7. Blocked states

free;

approach;

alignment;

magnetic_pre_align;

soft_capture;

electrical_unsafe;

passport_missing;

passport_invalid;

PDU_denied;

bayonet_thermal_block;

SAFE_block.

### 9.8. Required fields

bayonet_id;

connected_object_id;

bridge_state;

mechanical_state;

structural_check;

electrical_safety_state;

umbilical_state;

passport_state;

power_direction;

power_limit_W;

data_link_state;

thermal_node;

reason_codes.

### 9.9. Units

power_limit_W — W;

thermal_node — enum;

bridge_state — enum.

### 9.10. Reason codes

BRIDGE_HARD_LOCK_MISSING;

BRIDGE_STRUCTURAL_CHECK_MISSING;

BRIDGE_ELECTRICAL_UNSAFE;

BRIDGE_UMBILICAL_MISSING;

BRIDGE_PASSPORT_MISSING;

BRIDGE_PASSPORT_INVALID;

BRIDGE_PDU_DENIED;

BRIDGE_THERMAL_BLOCK;

BRIDGE_SAFE_BLOCK;

BRIDGE_ACTIVE_RESTRICTED_MOTION.

### 9.11. ORION evidence

ORION должен показывать:

bridge_state;

mechanical_state;

electrical_safety;

passport_state;

power_direction;

power_limit_W;

data link status;

thermal blockers;

motion restrictions;

reason_codes.

### 9.12. Audit requirements

Audit должен писать:

bridge state transition;

power direction changes;

PDU denial;

passport failure;

unsafe bridge attempt;

bridge shutdown.

### 9.13. Blackbox relevance

Blackbox relevant:

unsafe power attempt;

bridge failure;

unexpected detach while bridge active;

electrical unsafe state;

hard lock failure under bridge.

### 9.14. Status

`canon / target-only`

---

## 10. IF-MODULE-PASSPORT-001 — Module Passport Handshake Interface

### 10.1. Purpose

Описать проверку модуля перед тем, как он может считаться runtime-ready.

### 10.2. Producer

Module;

module registry;

bayonet module controller;

documentation package, если это template-only слой.

### 10.3. Consumers

command gating;

ORION;

PDU;

thermal model;

RCS controller;

sensor / comms subsystems;

audit;

blackbox.

### 10.4. Direction

Module / registry → body validation consumers.

### 10.5. Required validation chain

module detected;

mount point known;

module_class known;

mass provided;

power profile provided;

thermal profile provided;

capability list provided;

blocked commands provided;

failure modes provided;

reason_codes provided;

passport_validated.

### 10.6. Required fields

module_id;

module_class;

mount_type;

mount_point;

mass_kg;

local_position;

CoM_impact;

inertia_impact;

power_idle_W;

power_active_W;

peak_power_W;

thermal_node;

heat_idle_W;

heat_active_W;

provided_capabilities;

removed_capabilities;

blocked_commands;

new_commands;

SAFE_interactions;

failure_modes;

degradation_modes;

reason_codes;

telemetry_fields;

audit_requirements;

blackbox_relevance;

status.

### 10.7. Blocked states

passport_missing;

passport_invalid;

mount_unknown;

mass_unknown;

power_profile_missing;

thermal_profile_missing;

capability_cost_missing;

reason_codes_missing;

status_unknown.

### 10.8. Reason codes

MODULE_PASSPORT_MISSING;

MODULE_PASSPORT_INVALID;

MODULE_MOUNT_UNKNOWN;

MODULE_MASS_UNKNOWN;

MODULE_POWER_PROFILE_MISSING;

MODULE_THERMAL_PROFILE_MISSING;

MODULE_COST_MISSING;

MODULE_REASON_CODES_MISSING;

MODULE_NOT_RUNTIME_READY.

### 10.9. ORION evidence

ORION должен показывать:

module_id;

passport status;

mount point;

mass impact;

power impact;

thermal impact;

new capabilities;

blocked commands;

failure modes;

runtime status.

### 10.10. Audit requirements

Audit должен писать:

module attach request;

passport validation result;

module rejected;

module accepted target-only;

module status change;

module detach.

### 10.11. Blackbox relevance

Blackbox relevant:

module attach failure;

module failure during command;

module causing SAFE;

module causing power / thermal fault;

unexpected module detach.

### 10.12. Status

`canon / template-only / target-only`

---

## 11. IF-PDU-POWER-001 — PDU Load Permission Interface

### 11.1. Purpose

Описать, как PDU разрешает или запрещает нагрузки.

### 11.2. Producer

PDU;

power model;

thermal model;

SAFE.

### 11.3. Consumers

command gating;

RCS controller;

sensor controller;

comms controller;

NBL controller;

module runtime;

ORION;

audit.

### 11.4. Direction

PDU → load consumers / command gating.

### 11.5. Required fields

load_id;

load_class;

requested_power_W;

peak_required;

duration_s;

SoC_bat;

SoC_cap;

bus_voltage_V;

bus_current_A;

PDU_state;

thermal_clearance;

SAFE_state;

allowance_state;

reason_codes.

### 11.6. Allowed states

load_allowed;

load_allowed_limited;

load_rejected;

load_shed;

load_degraded;

PDU_safe_mode.

### 11.7. Reason codes

PDU_DENIED;

PDU_OVERLOAD;

PDU_PEAK_DENIED;

CAP_LOW;

BAT_LOW;

BUS_UNSTABLE;

LOAD_SHED_ACTIVE;

THERMAL_BLOCK;

SAFE_LOCKED.

### 11.8. ORION evidence

ORION должен показывать:

PDU state;

requested load;

allowed / rejected;

blocked peak commands;

SoC_bat;

SoC_cap;

thermal blockers;

reason_codes.

### 11.9. Audit requirements

Audit должен писать:

PDU denial;

load shedding;

critical load allowed;

unsafe load rejected;

SAFE-triggered power block.

### 11.10. Status

`canon / target-only`

---

## 12. IF-POWER-TELEM-001 — Battery / Supercap Telemetry Interface

### 12.1. Purpose

Описать телеметрию батареи, supercap, источников и шины.

### 12.2. Producer

power model;

battery subsystem;

supercap subsystem;

PDU;

external source bridge.

### 12.3. Consumers

ORION;

command gating;

SAFE;

audit;

blackbox;

runtime diagnostics.

### 12.4. Required fields

battery_soc_pct;

battery_capacity_Wh;

battery_charge_W;

battery_discharge_W;

battery_temp_state;

supercap_soc_pct;

supercap_capacity_Wh;

supercap_charge_W;

supercap_discharge_W;

supercap_temp_state;

source_generation_W;

bus_voltage_V;

bus_current_A;

loads_W;

spill_W;

unserved_W;

timestamp;

freshness;

source;

trust_status.

### 12.5. Reason codes

POWER_TELEM_MISSING;

POWER_TELEM_STALE;

BAT_LOW;

CAP_LOW;

BAT_HOT;

CAP_HOT;

BUS_UNSTABLE;

SOURCE_UNAVAILABLE;

EXTERNAL_POWER_UNSAFE.

### 12.6. ORION evidence

ORION должен показывать battery и supercap отдельно.

Одна общая energy bar не должна подменять power evidence.

### 12.7. Blackbox relevance

Blackbox relevant:

power loss;

critical low battery;

supercap failure;

bus fault;

unserved critical load.

### 12.8. Status

`canon / target-only`

---

## 13. IF-THERMAL-TELEM-001 — Thermal Node Telemetry Interface

### 13.1. Purpose

Описать телеметрию тепловых узлов.

### 13.2. Producer

thermal model;

subsystem thermal sensors;

module thermal profile.

### 13.3. Consumers

command gating;

PDU;

SAFE;

ORION;

audit;

blackbox.

### 13.4. Required fields

thermal_node_id;

temp_current;

thermal_state;

temp_warning;

temp_critical;

heat_active_W;

cooldown_state;

blocked_commands;

timestamp;

freshness;

source;

trust_status;

reason_codes.

### 13.5. Thermal states

nominal;

warm;

hot;

critical;

cooldown;

unknown.

### 13.6. Reason codes

THERMAL_TELEM_MISSING;

THERMAL_TELEM_STALE;

THERMAL_NODE_HOT;

THERMAL_NODE_CRITICAL;

PDU_THERMAL_BLOCK;

RCS_CLUSTER_HOT;

SENSOR_HEAD_HOT;

COMMS_HOT;

BAYONET_THERMAL_BLOCK;

MODULE_THERMAL_BLOCK.

### 13.7. ORION evidence

ORION должен показывать:

какой узел греется;

какие команды заблокированы;

какой cooldown нужен;

какой reason_code активен.

### 13.8. Blackbox relevance

Blackbox relevant:

critical overheating;

thermal shutdown;

SAFE due to thermal fault;

module thermal runaway.

### 13.9. Status

`canon / target-only`

---

## 14. IF-RCS-CMD-001 — RCS Command Interface

### 14.1. Purpose

Описать границу между command gating и RCS execution.

### 14.2. Producer

command gating;

autonomy controller;

SAFE routine.

### 14.3. Consumers

RCS controller;

ORION;

audit;

blackbox.

### 14.4. Required fields

command_id;

RCS_mode;

requested_delta_v;

requested_torque;

duration_s;

active_clusters;

required_thrusters;

SoC_cap_required;

thermal_nodes;

working_mass_required;

CoM_class;

inertia_class;

bayonet_state;

bridge_state;

Thrust_Map_status;

Torque_Map_status;

validation_status;

reason_codes.

### 14.5. Blocked states

Thrust_Map_missing;

Torque_Map_missing;

RCS_cluster_hot;

working_mass_low;

CoM_invalid;

inertia_unmodeled;

bayonet_soft_capture;

bridge_active_unrated;

SAFE_locked;

CAP_low.

### 14.6. Reason codes

RCS_UNAVAILABLE;

THRUST_MAP_MISSING;

TORQUE_MAP_MISSING;

RCS_CLUSTER_HOT;

WORKING_MASS_LOW;

COM_INVALID;

INERTIA_UNMODELED;

BAYONET_SOFT_CAPTURE_ONLY;

BRIDGE_ACTIVE_RESTRICTED_MOTION;

CAP_LOW;

SAFE_LOCKED.

### 14.7. ORION evidence

ORION должен показывать:

requested burn;

allowed / rejected;

active blockers;

map status;

thermal blockers;

CoM / inertia class;

expected effect;

effect confirmation state.

### 14.8. Audit requirements

Audit должен писать:

RCS command request;

validation result;

publish;

ACK;

effect confirmation;

partial effect;

failure;

abort.

### 14.9. Blackbox relevance

Blackbox relevant:

failed burn;

unexpected rotation;

tumble;

collision risk;

burn while bridge active;

SAFE intervention.

### 14.10. Status

`canon / target-only`

---

## 15. IF-SENSOR-TELEM-001 — Sensor Telemetry Interface

### 15.1. Purpose

Описать передачу сенсорных данных с source, freshness и trust.

### 15.2. Producer

sensor subsystem;

sensor fusion;

external module feed;

bayonet data-link;

local reconstruction;

blackbox replay.

### 15.3. Consumers

ORION;

command gating;

autonomy;

SAFE;

audit.

### 15.4. Required fields

sensor_id;

sensor_class;

measured_quantity;

value;

unit;

timestamp;

freshness;

latency;

accuracy;

source;

trust_status;

field_of_view;

mount_point;

blocked_by_module;

affected_by_motion;

affected_by_field;

affected_by_emcon;

thermal_state;

reason_codes.

### 15.5. Trust states

trusted;

degraded;

conflicting;

blind;

stale;

missing;

local_reconstruction;

hypothesis.

### 15.6. Reason codes

SENSOR_MISSING;

SENSOR_STALE;

SENSOR_CONFLICTING;

SENSOR_BLIND;

SENSOR_DEGRADED;

SENSOR_BLOCKED_BY_MODULE;

SENSOR_THERMAL_BLOCK;

SENSOR_AFFECTED_BY_FIELD;

SENSOR_AFFECTED_BY_MOTION.

### 15.7. ORION evidence

ORION должен показывать:

source;

freshness;

trust;

conflict;

missing status;

hypothesis / reconstruction marking.

### 15.8. Status

`canon / target-only`

---

## 16. IF-COMMS-001 — Normal Communication Interface

### 16.1. Purpose

Описать обычные каналы связи QIKI.

### 16.2. Producer

comms subsystem;

bayonet data-link;

relay module;

operator station.

### 16.3. Consumers

ORION;

command bus;

audit;

SAFE;

external receivers.

### 16.4. Required fields

channel_id;

channel_class;

direction;

bandwidth_class;

latency;

power_cost_W;

thermal_node;

signature_class;

EMCON_state;

delivery_state;

timestamp;

freshness;

trust_status;

reason_codes.

### 16.5. Blocked states

EMCON_block;

power_block;

thermal_block;

SAFE_block;

channel_degraded;

authorization_missing;

not_implemented.

### 16.6. Reason codes

COMMS_UNAVAILABLE;

COMMS_DEGRADED;

EMCON_BLOCK;

COMMS_POWER_BLOCK;

COMMS_THERMAL_BLOCK;

COMMS_UNAUTHORIZED;

COMMS_NOT_IMPLEMENTED.

### 16.7. ORION evidence

ORION должен показывать:

active channel;

delivery state;

latency;

EMCON;

thermal / power blockers;

reason_codes.

### 16.8. Status

`canon / target-only`

---

## 17. IF-NBL-001 — NBL Emergency Packet Interface

### 17.1. Purpose

Описать baseline NBL как emergency low-rate interface.

NBL не является normal comms.

NBL не является wideband.

NBL не является bulk telemetry.

### 17.2. Producer

NBL controller;

emergency handler;

SAFE;

operator emergency command.

### 17.3. Consumers

NBL transmitter;

ORION;

audit;

blackbox;

external receiver, если применимо.

### 17.4. Required fields

packet_id;

criticality;

payload_class;

payload_size_bits;

transmit_attempts;

SoC_cap_cost;

power_cost;

thermal_node;

expected_latency;

delivery_confidence;

audit_required;

blackbox_relevance;

reason_codes.

### 17.5. Allowed states

critical_only;

emergency_only;

packet_allowed;

packet_rejected;

packet_sent;

packet_failed;

delivery_unknown.

### 17.6. Blocked states

non_critical;

payload_too_large;

CAP_low;

PDU_denied;

thermal_block;

SAFE_conflict;

not_implemented;

rules_only.

### 17.7. Reason codes

NBL_NOT_CRITICAL;

NBL_PAYLOAD_TOO_LARGE;

NBL_CAP_LOW;

NBL_PDU_DENIED;

NBL_THERMAL_BLOCK;

NBL_NOT_IMPLEMENTED;

NBL_RULES_ONLY.

### 17.8. ORION evidence

ORION должен показывать:

criticality;

payload class;

cost;

status;

delivery uncertainty;

reason_codes.

### 17.9. Blackbox relevance

Blackbox relevant:

distress packet;

loss of comms;

emergency beacon;

last state packet;

failure to send emergency packet.

### 17.10. Status

`rules-only / target-only`

---

## 18. IF-CMD-BUS-001 — Command Bus / Lifecycle Interface

### 18.1. Purpose

Описать жизненный цикл команды.

### 18.2. Producer

operator;

QIKI autonomy;

SAFE routine;

module;

scripted scenario;

external connected object.

### 18.3. Consumers

command gating;

subsystem controllers;

ORION;

audit;

blackbox.

### 18.4. Required lifecycle

request;

validation;

allowed / rejected;

publish;

ACK;

effect confirmation;

audit.

### 18.5. Required fields

command_id;

command_type;

source;

target_subsystem;

requested_mode;

requested_intensity;

duration_s;

priority;

expected_effect;

risk_class;

validation_state;

publish_state;

ACK_state;

effect_state;

audit_state;

reason_codes.

### 18.6. Reason codes

CMD_VALIDATION_FAILED;

CMD_UNAUTHORIZED;

CMD_CONFIRMATION_REQUIRED;

CMD_REJECTED;

PUBLISH_FAILED;

ACK_TIMEOUT;

EFFECT_TIMEOUT;

EFFECT_PARTIAL;

SAFE_ABORTED;

AUDIT_UNAVAILABLE.

### 18.7. ORION evidence

ORION должен отличать:

allowed;

published;

ACK accepted;

effect confirmed;

failed;

partial;

timeout.

### 18.8. Status

`canon / target-only`

---

## 19. IF-ORION-EVIDENCE-001 — ORION Evidence Feed Interface

### 19.1. Purpose

Описать, какие evidence-данные должны передаваться в ORION.

### 19.2. Producer

runtime state;

telemetry;

events;

command lifecycle;

audit;

blackbox;

module passport;

calculation status;

documentation status.

### 19.3. Consumers

ORION UI;

operator;

AI assistant;

QA tools, если применимо.

### 19.4. Required fields

claim_id;

claim_text;

source_type;

source_id;

freshness;

trust_status;

status;

related_command_id;

related_module_id;

reason_codes;

audit_link;

blackbox_relevance;

operator_action.

### 19.5. Reason codes

ORION_SOURCE_MISSING;

ORION_DATA_STALE;

ORION_TRUST_CONFLICT;

ORION_TARGET_ONLY;

ORION_NOT_IMPLEMENTED;

ORION_CALCULATION_REQUIRED;

ORION_EFFECT_UNCONFIRMED.

### 19.6. ORION display rules

ORION не должен показывать уверенное состояние без source.

ORION должен помечать target-only.

ORION должен помечать not implemented.

ORION должен показывать stale.

ORION должен показывать conflicting.

ORION должен отличать ACK от effect confirmation.

### 19.7. Status

`canon / target-only`

---

## 20. IF-AUDIT-001 — Audit Event Stream Interface

### 20.1. Purpose

Описать события, которые должны попадать в audit.

### 20.2. Producer

command bus;

command gating;

subsystem controllers;

PDU;

bayonet controller;

module validator;

SAFE;

ORION actions.

### 20.3. Consumers

audit log;

ORION;

blackbox selector;

QA replay;

postmortem tools.

### 20.4. Required fields

event_id;

event_type;

timestamp;

source;

command_id;

previous_state;

new_state;

reason_codes;

operator_id, если применимо;

module_id, если применимо;

bayonet_id, если применимо;

effect_state;

severity;

blackbox_relevance.

### 20.5. Audit event classes

command_request;

validation_result;

command_rejected;

publish;

ACK;

effect_confirmation;

effect_partial;

effect_timeout;

SAFE_intervention;

module_attach;

module_detach;

passport_validation;

bayonet_state_transition;

PDU_denial;

thermal_block;

sensor_conflict;

comms_failure;

NBL_packet_attempt.

### 20.6. Status

`canon / target-only`

---

## 21. IF-BLACKBOX-001 — Blackbox Record Interface

### 21.1. Purpose

Описать, какие события должны попадать в blackbox как последнюю память тела.

### 21.2. Producer

audit;

SAFE;

critical event detector;

runtime state snapshot;

telemetry snapshot;

command lifecycle.

### 21.3. Consumers

blackbox storage;

postmortem reader;

ORION recovery view;

QA replay.

### 21.4. Required fields

record_id;

timestamp;

trigger_event;

severity;

body_state_snapshot;

power_snapshot;

thermal_snapshot;

motion_snapshot;

sensor_snapshot;

command_chain;

audit_refs;

reason_codes;

loss_context;

recovery_notes.

### 21.5. Blackbox triggers

critical power loss;

critical thermal event;

loss of QIKI;

death of body;

hard lock failure;

emergency detach;

unsafe bridge failure;

SAFE escalation;

failed critical command;

sensor conflict during critical command;

NBL emergency packet;

unexpected motion;

collision / impact;

postmortem marker.

### 21.6. Status

`canon / target-only`

---

## 22. IF-SAFE-001 — SAFE State Interface

### 22.1. Purpose

Описать состояние SAFE и его влияние на команды.

### 22.2. Producer

SAFE controller;

power model;

thermal model;

sensor trust model;

command risk policy;

damage model;

bayonet safety;

blackbox-critical event detector.

### 22.3. Consumers

command gating;

PDU;

RCS controller;

sensor controller;

comms controller;

module runtime;

ORION;

audit;

blackbox.

### 22.4. Required fields

SAFE_state;

SAFE_reason;

blocked_commands;

allowed_commands;

exit_conditions;

power_state;

thermal_state;

sensor_state;

bayonet_state;

damage_state;

timestamp;

reason_codes;

blackbox_relevance.

### 22.5. SAFE states

safe_inactive;

safe_monitoring;

safe_warning;

safe_limited;

safe_lockdown;

safe_recovery;

safe_unknown.

### 22.6. Reason codes

SAFE_POWER_LOW;

SAFE_CAP_LOW;

SAFE_THERMAL_CRITICAL;

SAFE_SENSOR_CONFLICT;

SAFE_ORIENTATION_LOST;

SAFE_BAYONET_UNSAFE;

SAFE_PDU_FAULT;

SAFE_COMMS_LOSS;

SAFE_DAMAGE_CRITICAL;

SAFE_BLACKBOX_CRITICAL.

### 22.7. ORION evidence

ORION должен показывать:

SAFE state;

главный reason_code;

blocked commands;

allowed commands;

exit conditions;

missing data;

degraded nodes.

### 22.8. Audit / blackbox requirements

Audit должен писать SAFE activation, escalation, recovery и command block.

Blackbox должен получать SAFE escalation и critical SAFE events.

### 22.9. Status

`canon / target-only`

---

## 23. Cross-interface rules

### 23.1. Command path

Опасная команда должна проходить цепочку:

request → validation → publish → ACK → effect confirmation → audit

Если цепочка оборвана, ORION должен показать место разрыва.

### 23.2. Module attach path

Подключение модуля должно проходить цепочку:

mount detected → bayonet / mount state checked → passport received → passport validated → power profile checked → thermal profile checked → command restrictions updated → ORION evidence updated → audit written

### 23.3. Bayonet bridge path

Bridge должен проходить цепочку:

mechanical_hard_lock → structural_check_passed → electrical_safety_passed → umbilical_mated → module_handshake_passed → passport_validated → PDU_allowance → thermal_clearance → bridge_allowed

### 23.4. Peak action path

Пиковая команда должна проверять:

SoC_cap;

PDU allowance;

thermal clearance;

SAFE state;

module / subsystem status;

command risk;

audit availability for critical commands.

### 23.5. Evidence path

Важное утверждение должно иметь:

source;

freshness;

trust;

status;

reason_codes, если есть ограничения;

audit link, если это действие;

blackbox relevance, если событие критическое.

---

## 24. Acceptance for this document

`06_INTERFACE_CONTROL.md` считается готовым для documentation-only package, если:

есть общие правила interface control;

есть минимальный interface record;

есть статусы интерфейса;

есть типы блокировок;

есть interface catalog;

описан Bayonet Mechanical State Interface;

описан Bayonet Power/Data Bridge Interface;

описан Module Passport Handshake Interface;

описан PDU Load Permission Interface;

описана Battery / Supercap Telemetry;

описана Thermal Node Telemetry;

описан RCS Command Interface;

описан Sensor Telemetry Interface;

описан Normal Communication Interface;

описан NBL Emergency Packet Interface;

описан Command Bus / Lifecycle Interface;

описан ORION Evidence Feed Interface;

описан Audit Event Stream Interface;

описан Blackbox Record Interface;

описан SAFE State Interface;

есть cross-interface rules;

нет implemented claims без evidence;

нет verified claims без verification;

нет proto / NATS / gRPC / telemetry path изменений;

нет runtime conformance claims.

---

## 25. Итоговая формула

Interface Control нужен, чтобы QIKI не распалась на подсистемы, которые “как-то” связаны.

Граница должна быть описана.

Состояние должно быть явно названо.

Разрешение должно быть проверяемым.

Запрет должен иметь reason_code.

Команда должна иметь lifecycle.

ACK не должен подменять effect confirmation.

ORION должен получать evidence.

Audit должен хранить след.

Blackbox должен сохранить критическую память.

Target-only не означает implemented.

Interface record не означает runtime protocol.

Документ не является кодом.

Документ задаёт границу, которую будущая реализация должна будет доказать.
