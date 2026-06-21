# QIKI Body v0.2.2 — Reader Manual

## 0. Статус документа

Файл:

`10_READER_MANUAL.md`

Версия:

`v0.2.2`

Статус:

`derived reader manual / documentation-only`

Runtime conformance:

`not claimed`

Этот документ является производной читательской сборкой QIKI Body v0.2.2.

Он нужен для цельного чтения пакета человеком.

Он не является главным source of truth.

Он не заменяет:

`01_BODY_CANON.md`

`02_REQUIREMENTS.md`

`03_ARCHITECTURE_VIEWPOINTS.md`

`04_CALCULATION_FRAME.md`

`05_ENGINEERING_RATIONALE.md`

`06_INTERFACE_CONTROL.md`

`07_ADR/`

`08_IMPLEMENTATION_BRIDGE.md`

`09_ACCEPTANCE_CHECKS.md`

Если этот reader manual конфликтует с primary source files, приоритет имеют primary source files.

Главное правило:

Reader manual не является evidence.

Reader manual не является runtime implementation.

Reader manual не должен превращать target-only в implemented.

---

## 1. Назначение reader manual

Этот документ собирает QIKI Body v0.2.2 в читаемую форму.

Primary source files нужны для точной работы: канон, требования, viewpoints, расчётный каркас, rationale, интерфейсы, ADR, мост внедрения и acceptance checks.

Reader manual нужен для другого: быстро понять, что такое QIKI Body v0.2.2, почему этот пакет существует, какие решения в нём приняты, где проходят границы честности и как читать всю систему как одно машинное тело.

Этот документ не добавляет новые модули.

Не добавляет новые технологии.

Не добавляет новые лорные расширения.

Не меняет runtime.

Не утверждает, что runtime уже соответствует QIKI Body v0.2.2.

---

## 2. Главная формула QIKI Body v0.2.2

QIKI — не ассистент внутри корпуса.

QIKI — машинное тело.

Голос QIKI объясняет.

Модель рассуждает.

ORION показывает evidence.

Симуляция задаёт состояние.

Телеметрия передаёт состояние.

ACK подтверждает приём или обработку команды, но не физический эффект.

Effect confirmation подтверждает изменение тела или мира.

Audit сохраняет цепочку действий.

Blackbox сохраняет критическую память тела.

Последняя физическая истина о QIKI должна приходить из runtime-данных, а не из красивого текста, голоса модели или интерфейсной панели.

Каноническая формула:

QIKI — постоянное машинное тело с переменной специализацией.

Каждая возможность имеет физическую цену.

Каждый модуль меняет тело.

Каждая команда проходит через тело.

Каждый важный факт должен иметь источник.

Каждый опасный эффект должен иметь подтверждение.

---

## 3. Почему QIKI должна быть телом, а не голосом модели

Главный риск проекта — превратить QIKI в говорящий интерфейс.

Если QIKI станет просто голосом модели, физическая причинность начнёт исчезать. Модель сможет сказать, что модуль активен. ORION сможет показать красивую панель. Команда сможет звучать как выполненная. Но без runtime state, telemetry, ACK, effect confirmation, audit and blackbox это не будет доказанным состоянием тела.

Поэтому QIKI Body v0.2.2 фиксирует жёсткое разделение:

тело QIKI — физическая и симуляционная сущность;

голос QIKI — слой объяснения;

модель — когнитивный и языковой слой;

ORION — операторская станция evidence;

runtime truth — последняя физическая истина.

Модель может помогать, объяснять, строить гипотезы и связывать факты.

Модель не подтверждает физический факт.

ORION может показывать состояние, подсвечивать риски и собирать evidence.

ORION не выдумывает реальность.

---

## 4. Runtime truth

Runtime truth — главный закон QIKI Body.

Физическое утверждение о QIKI должно иметь источник.

Источник может быть:

simulation state;

world model;

telemetry;

event;

ACK;

effect confirmation;

audit;

blackbox;

проверяемый snapshot;

service response.

Если источник отсутствует, утверждение должно быть помечено как:

missing;

unknown;

hypothesis;

local reconstruction;

stale;

target-only;

not implemented;

calculation-required.

Лучше показать “данные отсутствуют”, чем выдумать уверенный статус.

Лучше показать “локальная реконструкция”, чем назвать гипотезу фактом.

Лучше показать “stale”, чем использовать старое значение как свежую истину.

---

## 5. Статусы пакета

QIKI Body v0.2.2 использует статусы, чтобы не смешивать канон, цель, шаблон, правило, расчёт и реализацию.

`canon` означает, что правило принято как часть канона.

`target-only` означает, что правило является целью, но runtime ещё не обязан его поддерживать.

`template-only` означает, что есть шаблон, но нет runtime schema или заполненных экземпляров.

`rules-only` означает, что есть правило, но не заявлен runtime protocol или enforcement.

`calculation-required` означает, что нужен расчёт до утверждения значения.

`implemented` означает, что функция есть в runtime. Этот статус требует evidence.

`verified` означает, что функция есть в runtime и проверена. Этот статус требует evidence и verification.

`superseded` означает, что старое утверждение заменено.

`rejected` означает, что вариант рассмотрен и отклонён.

Главное правило:

canon не означает implemented.

target-only не означает runtime-ready.

template-only не означает runtime schema.

rules-only не означает protocol implemented.

calculation-required не означает calculated.

implemented требует evidence.

verified требует evidence и verification.

---

## 6. Идентичность QIKI

QIKI остаётся одной и той же машинной единицей независимо от конфигурации.

Модульность не создаёт нового робота.

Модульность меняет эксплуатационный профиль одного и того же тела.

Базовая идентичность QIKI включает:

додекаэдрический корпус;

двенадцать функциональных граней;

два противоположных байонетных интерфейса;

распределённую RCS-логику;

энергетический контур;

battery;

supercap;

PDU;

node-based thermal model;

сенсорный контур;

связь;

SAFE;

command gating;

ORION Evidence;

audit;

blackbox;

module passport как обязательный контракт.

QIKI может быть разведчиком, ретранслятором, радиационным зондом, стыковочным узлом или аварийным буксиром.

Но это не разные роботы.

Это одно тело с разными ценами, ограничениями и рисками.

---

## 7. Геометрия тела

Базовая форма QIKI — додекаэдрическое машинное тело.

Двенадцать граней являются функциональными хардпоинтами.

Грань не является декором.

Грань является физическим и runtime-узлом.

Каждая грань должна иметь или получить:

face_id;

роль;

нормаль в body frame;

допустимые классы модулей;

запрещённые классы модулей;

конфликты с соседними гранями;

влияние на сенсоры;

влияние на RCS plume-clearance;

влияние на тепловой сброс;

влияние на связь;

runtime status.

Минимальный набор идентификаторов граней:

F00–F11.

Точные нормали, финальные роли и точная геометрия остаются calculation-required, пока расчёт не выполнен.

Нельзя писать так, будто точная геометрия уже доказана, если она не рассчитана.

---

## 8. Масса, центр масс и инерция

QIKI должна управляться как физическое тело, а не как абстрактная точка.

Любой модуль может менять:

массу;

центр масс;

момент инерции;

допустимые манёвры;

RCS-компенсацию;

тепло;

энергию;

байонетную нагрузку;

безопасность команды.

Базовый центр масс должен находиться близко к геометрическому центру корпуса.

Тяжёлые внешние устройства должны:

устанавливаться парно;

или компенсироваться противомассой;

или переводить QIKI в ограниченный режим движения;

или требовать отдельного расчёта;

или запрещать часть манёвров.

ORION должен показывать последствия реконфигурации: массу, CoM_delta, inertia class, ограничения манёвров и источник изменения.

---

## 9. Байонетный интерфейс

QIKI имеет два противоположных байонетных интерфейса.

Байонет — главный внешний интерфейс реконфигурации.

Он выполняет четыре роли:

механическую;

энергетическую;

информационную;

каскадную.

Через байонет QIKI может подключаться к станции, другому телу, внешнему источнику питания, модулю, ретранслятору или сервисному контуру.

Магнит не является основным силовым замком.

Магнит допустим как preliminary alignment.

Soft capture не разрешает power / data bridge.

Каноническая цепочка:

approach → alignment → magnetic pre-align → soft capture → mechanical hard lock → structural check → electrical safety → umbilical mate → module handshake → passport validation → bridge allowed.

До mechanical hard lock соединение не считается силовым.

До electrical safety питание не считается штатно разрешённым.

До passport validation модуль не считается runtime-ready.

До bridge allowed power / data bridge не считается активным.

---

## 10. RCS и движение

RCS является штатной основой движения QIKI.

Базовая схема:

четыре RCS-кластера;

по четыре сопла в кластере;

всего шестнадцать сопел.

RCS должна обеспечивать:

ориентацию;

микроманёвры;

стыковочные коррекции;

safe-brake;

стабилизацию;

компенсацию малых возмущений.

В базовой логике QIKI не имеет главного хвостового двигателя.

QIKI движется как многогранное тело с распределённой тягой.

Нельзя обещать balanced thrust, full maneuverability или all-axis authority без Thrust Map и Torque Map.

RCS-команды должны учитывать:

SoC_cap;

PDU allowance;

thermal nodes;

CoM class;

inertia class;

working mass;

bayonet state;

bridge state;

SAFE;

sensor trust, если манёвр зависит от восприятия.

Manual override отдельных RCS-сопел не является штатной игровой кнопкой.

Он может существовать только как debug-only или аварийный инженерный режим.

---

## 11. Энергетическая архитектура

Энергетика QIKI не является одной абстрактной шкалой.

Каноническая формула:

`source → battery → bus → supercap → peak consumers`

Источник энергии даёт среднюю мощность.

Батарея хранит долгий запас.

Шина распределяет питание.

Supercap закрывает быстрые пики.

PDU разрешает или запрещает нагрузки.

Thermal nodes задают физический предел.

SAFE может запретить действие даже при наличии энергии.

SoC_bat показывает запас жизни.

SoC_cap показывает готовность к краткому пиковому действию.

Высокий SoC_bat не означает право на boost.

Низкий SoC_cap означает, что QIKI может быть жива, но не готова к резкому действию.

Пиковые действия требуют SoC_cap, PDU allowance и thermal clearance.

---

## 12. Источники питания

QIKI может использовать разные классы источников, но каждый источник имеет цену и статус.

Допустимые классы:

solar source;

battery;

supercap;

chemical generator / fuel-cell-class source;

radioisotope trickle source;

external reactor-class source;

Terta-exotic source, если явно помечен.

Solar source подходит для средней генерации и восстановления, но не отменяет battery / supercap.

Battery — запас жизни, но не право на любой пик.

Supercap — буфер быстрых действий, но не долгий запас энергии.

Chemical / fuel-cell-class source требует реагентов, массы, тепла и расхода.

RTG-class source является heavy / trickle source, not boost-source.

Reactor-class source является external / station / sled / heavy infrastructure, not normal face module.

Terta-exotic source допустим только с явной маркировкой, ценой, ограничениями и evidence path.

---

## 13. Тепловая модель

Тепло является физическим ограничителем тела QIKI.

QIKI не должна иметь одну общую абстрактную температуру для серьёзных команд.

Минимально тепловая модель должна быть node-based.

Тепловые узлы могут включать:

core;

battery;

supercap;

PDU;

RCS clusters;

sensor head;

comms;

bayonet A;

bayonet B;

external module;

field / deflector module, если установлен.

Тепло влияет на:

разрешение команд;

частоту сенсорных операций;

доступность high-power scan;

доступность boost;

доступность NBL packet;

доступность active field / deflector;

доступность power import / export;

SAFE;

load shedding;

cooldown.

Тепловой отказ должен иметь reason_code.

Немой отказ недопустим.

---

## 14. Сенсоры

Сенсоры QIKI являются органами восприятия тела.

Сенсор не является просто числом на экране.

Сенсор должен иметь:

source;

freshness;

latency;

accuracy;

field_of_view;

mount point;

power profile;

thermal node;

trust status;

degradation modes;

failure modes;

reason_codes.

Сенсорные данные могут иметь статусы:

trusted;

degraded;

conflicting;

blind;

stale;

missing;

local_reconstruction;

hypothesis.

Видеть не значит знать.

Получить сигнал не значит иметь истину.

Синтаксически валидное значение может быть физически опасным или конфликтующим.

QIKI не должна строить опасные действия на stale или conflicting sensor data без подтверждения.

---

## 15. Связь

Связь QIKI не является просто состоянием “есть сигнал”.

Связь является каналом с:

source;

direction;

bandwidth;

latency;

power cost;

thermal cost;

signature;

EMCON status;

risk;

freshness;

delivery state;

audit relevance.

Связь может быть:

normal comms;

relay mode;

bayonet data-link;

emergency channel;

NBL emergency low-rate channel;

Terta-exotic channel, если явно помечен.

Связь не означает безопасность.

ORION должен показывать не только сигнал, но и состояние канала, ограничения, свежесть, стоимость и reason_codes.

---

## 16. NBL

Baseline NBL не является широкополосной связью.

NBL не является обычной телеметрией.

NBL не является интернетом через всё.

Baseline NBL — это emergency low-rate channel для коротких критических сообщений.

NBL должен иметь:

условия допуска;

критичность;

ограничение частоты;

стоимость по SoC_cap;

стоимость по thermal nodes;

payload limit;

delivery uncertainty;

reason_codes;

audit entry;

blackbox relevance.

Расширенный NBL выше emergency low-rate baseline допустим только как Terta-exotic.

---

## 17. Защита

Защита QIKI не является магическим щитом.

Защита должна быть конкретным механизмом против конкретного класса угроз.

Защита может снижать риск, но не должна давать неуязвимость.

Защита должна иметь:

геометрию;

массу;

энергию;

тепло;

деградацию сенсоров;

влияние на связь;

влияние на EMCON;

влияние на манёвры;

ограничения команд;

reason_codes;

evidence.

Radiation deflector / deployable deflector допустим как защитный механизм, но не как абсолютный пузырь.

Field-like protection не считается baseline и требует явной цены, статуса и evidence path.

---

## 18. Field drive и экзотическая тяга

Field drive не является baseline.

Baseline-движение QIKI должно опираться на RCS и физически ограниченные классы тяги.

Тяга не должна появляться “из чистой энергии” без рабочего тела, взаимодействия со средой или явной экзотической маркировки.

Если field drive используется, он должен быть:

Terta-exotic;

advanced speculative;

scenario-specific;

explicit-cost technology.

Он должен иметь:

энергетическую цену;

тепловую цену;

сигнатуру;

cooldown;

риски;

командный допуск;

evidence path;

audit / blackbox relevance.

---

## 19. Модульность

Модульность QIKI — это не магазин апгрейдов.

Модульность — это изменение тела под задачу.

Модуль не является бонусом.

Модуль является физическим вмешательством в тело.

Каждый модуль должен отвечать на два вопроса:

что он даёт;

что он забирает.

Если модуль даёт защиту, он может забрать массу, манёвренность, энергию, скрытность, сенсорную чистоту или тепловой запас.

Если модуль даёт тягу, он может забрать рабочее тело, тепло, сигнатуру, безопасность, доступность стыковки или ресурс.

Если модуль даёт связь, он может забрать мощность, тепло, EMCON, скрытность или приоритет канала.

Если модуль даёт сенсоры, он может забрать питание, охлаждение, время сканирования, стабильность ориентации или геометрию обзора.

Если модуль только добавляет возможность и ничего не ухудшает, он подозрителен и не должен автоматически попадать в runtime.

---

## 20. Паспорт модуля

Модуль без паспорта не является runtime-модулем.

Паспорт модуля является контрактом между модулем, телом QIKI, command gating, ORION, audit и blackbox.

Минимально паспорт модуля должен описывать:

module_id;

module_class;

mount_type;

mount_point;

mass_kg;

local_position;

CoM impact;

inertia impact;

power_idle;

power_active;

peak_power;

thermal_node;

heat_idle;

heat_active;

cooldown;

provided capabilities;

removed capabilities;

blocked commands;

new commands;

risk class;

SAFE interactions;

sensor effects;

comms effects;

EMCON effects;

bayonet effects;

RCS effects;

failure modes;

degradation modes;

reason_codes;

telemetry fields;

audit requirements;

blackbox relevance;

status.

Название модуля не доказывает его существование.

Runtime-ready требует паспорта.

Implemented требует evidence.

Verified требует evidence и verification.

---

## 21. Command gating

Команда QIKI не является прямой кнопкой “сделай”.

Команда является запросом к телу.

Каноническая цепочка:

request → validation → allowed / rejected → publish → ACK → effect confirmation → audit

Request не является действием.

Allowed не является выполнением.

Publish не является эффектом.

ACK не является effect confirmation.

Effect confirmation не является audit, но должен попадать в audit.

Validation должна проверять:

mission profile;

body mode;

SAFE state;

module passport;

module status;

mount point;

bayonet state;

SoC_bat;

SoC_cap;

PDU limits;

thermal nodes;

CoM class;

inertia class;

RCS availability;

working mass;

sensor trust;

comms state;

EMCON state;

operator access;

operator confirmation;

cooldown;

risk policy;

audit availability;

blackbox relevance.

Отказ команды не является ошибкой, если он физически обоснован.

Отказ должен возвращать reason_codes.

---

## 22. SAFE

SAFE — режим физического выживания тела.

SAFE не является декоративной красной лампой.

SAFE может быть активирован из-за:

низкого SoC_bat;

низкого SoC_cap;

перегрева;

потери ориентации;

сенсорного blind / conflicting состояния;

критического повреждения;

ошибки байонетного соединения;

опасного bridge state;

PDU fault;

comms failure;

командного риска;

blackbox-critical event.

SAFE должен иметь право запрещать команды даже при наличии энергии.

SAFE должен быть видимым в ORION.

SAFE должен объяснять причину, заблокированные команды, разрешённые команды и условия выхода.

---

## 23. ORION Evidence

ORION является операторской станцией доказательств.

ORION не должен быть декоративным HUD.

ORION должен помогать оператору понимать:

что QIKI может сейчас;

что QIKI не может сейчас;

почему команда запрещена;

какой модуль мешает;

какой узел перегрет;

какой сенсор stale;

какой источник trusted;

какой источник missing;

где target-only;

где not implemented;

где calculation-required;

где ACK;

где effect confirmation;

где audit trail.

ORION может упрощать и группировать, но не имеет права выдумывать физику.

---

## 24. Audit и blackbox

Audit фиксирует цепочку действий.

Audit должен сохранять:

request;

validation result;

reason_codes;

publish;

ACK;

effect confirmation;

operator confirmation;

SAFE intervention;

failure;

timeout;

abort;

state transition.

Blackbox является последней памятью тела.

Blackbox нужен для критических отказов, потери QIKI, аварийного detach, hard lock failure, SAFE escalation, опасных command chains, сенсорного конфликта, критического перегрева, потери питания и postmortem-разбора.

Audit нужен для трассировки.

Blackbox нужен для критической памяти.

---

## 25. Расчётный каркас

Расчётный каркас переводит канон в таблицы.

Он не обязан сразу содержать финальные числа.

Он обязан сказать, где значения будут жить и какие поля нужны.

Основные таблицы:

Face Map;

Mount Compatibility Matrix;

Mass / CoM / Inertia Sheet;

Power Budget Sheet;

Thermal Budget Sheet;

Thrust Map;

Torque Map;

Bayonet Bridge Sheet;

Module Passport Template;

NBL Emergency Packet Rules;

Command Gating Matrix;

ORION Evidence Checklist.

Расчётный каркас нужен, чтобы каждый важный элемент тела получил место в таблице, статусе, проверке и reason_code.

Если значения нет, оно должно оставаться TBD или calculation-required.

---

## 26. Инженерное обоснование

Инженерное обоснование защищает канон от обратного размягчения.

Ключевые решения:

battery и supercap разделены;

RTG не является boost-source;

reactor-class source external / station / sled;

NBL emergency low-rate only;

protection is not absolute shield;

field drive not baseline;

bayonet requires mechanical hard lock;

RCS requires Thrust Map and Torque Map;

module passport mandatory;

ACK is not effect confirmation;

ORION evidence station;

first repository patch documentation-only.

Эти решения не закрывают фантастику.

Они запрещают бесплатную фантастику.

Если технология сильная, она должна иметь цену.

Если технология нарушает baseline, она должна быть явно помечена.

---

## 27. Interface Control

Interface Control описывает границы между подсистемами.

Минимальный каталог интерфейсов:

IF-BAYONET-MECH-001;

IF-BAYONET-BRIDGE-001;

IF-MODULE-PASSPORT-001;

IF-PDU-POWER-001;

IF-POWER-TELEM-001;

IF-THERMAL-TELEM-001;

IF-RCS-CMD-001;

IF-SENSOR-TELEM-001;

IF-COMMS-001;

IF-NBL-001;

IF-CMD-BUS-001;

IF-ORION-EVIDENCE-001;

IF-AUDIT-001;

IF-BLACKBOX-001;

IF-SAFE-001.

Interface record не является runtime protocol.

Он задаёт target boundary.

Runtime implementation требует отдельной задачи и evidence.

---

## 28. ADR

ADR фиксирует архитектурные решения, которые нельзя молча откатывать.

Начальный набор:

ADR-0001 — QIKI is a machine body, not a model voice;

ADR-0002 — Body canon is separated from old game GDD;

ADR-0003 — Battery and supercap are separated;

ADR-0004 — RTG is a trickle source, not boost-source;

ADR-0005 — Reactor-class source is external / station / sled;

ADR-0006 — Baseline NBL is emergency low-rate only;

ADR-0007 — Protection is deployable deflector, not absolute shield;

ADR-0008 — Field drive is not baseline;

ADR-0009 — Bayonet requires mechanical hard lock;

ADR-0010 — RCS requires Thrust Map and Torque Map;

ADR-0011 — Module passport is mandatory;

ADR-0012 — First repository patch is documentation-only;

ADR-0013 — Reader manual is derived;

ADR-0014 — ORION is evidence station;

ADR-0015 — ACK is not effect confirmation.

Если решение меняется, должен появиться новый ADR или старый должен быть superseded.

Нельзя переписывать историю решений задним числом.

---

## 29. Репозиторное внедрение

Пакет должен быть внесён как documentation-only.

Рекомендуемый путь:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/`

Первый patch может:

создать markdown files;

создать ADR files;

создать local index;

обновить documentation indexes;

добавить old GDD alignment note;

пометить старые конфликтующие statements как superseded;

добавить acceptance checklist.

Первый patch не должен:

менять runtime code;

менять simulation code;

менять ORION UI;

менять MFD;

менять proto;

менять NATS subjects;

менять gRPC contracts;

менять telemetry paths;

менять generated files;

добавлять tests that imply runtime conformance;

добавлять fake evidence;

писать implemented без evidence.

---

## 30. Отношение к старому GDD

Старый GDD не должен удаляться первым documentation-only patch.

Он сохраняется как game-design / historical layer.

Но по вопросам body hardware / physics приоритет имеет QIKI Body v0.2.2.

Критичные superseded-зоны:

магнитный замок как основной силовой байонет;

RTG как обычная батарейка;

реактор как обычный модуль на грань;

NBL как широкий канал данных;

щит как абсолютная защита;

field drive как baseline;

равномерная RCS без Thrust Map / Torque Map;

модуль без паспорта;

команда как мгновенный эффект;

ACK как effect confirmation;

ORION как decorative HUD.

---

## 31. Acceptance checks

Acceptance checks проверяют, что пакет не врёт о runtime.

Пакет должен иметь:

все expected files;

начальный ADR set;

source priority;

status legend;

documentation-only boundary;

old GDD relationship;

reader manual marked as derived;

no runtime code changes;

no proto changes;

no NATS changes;

no gRPC changes;

no telemetry path changes;

no ORION UI changes;

no MFD changes;

no generated file changes;

no fake evidence;

no implemented without evidence;

no verified without verification;

no invented numbers;

no target-only as runtime-ready;

no calculation-required as calculated.

Если эти правила нарушены, пакет нельзя считать корректно принятым.

---

## 32. Что может остаться TBD

QIKI Body v0.2.2 не обязан решать всё сразу.

Могут оставаться TBD:

точная геометрия;

нормали граней;

соседство граней;

массы;

локальные позиции;

CoM thresholds;

inertia classes;

RCS thrust values;

Thrust Map;

Torque Map;

thermal thresholds;

cooldown profiles;

battery capacity;

supercap capacity;

PDU limits;

bayonet structural rating;

NBL limits;

sensor ranges;

comms bandwidth;

deflector effectiveness;

Terta-exotic effects, если они используются.

TBD — честный статус.

Выдуманное число — плохой статус.

---

## 33. Минимальный MVP-смысл документации

MVP справочника — это не полнота мира.

MVP справочника — это отсутствие лжи.

Минимально должны быть зафиксированы:

QIKI как машинное тело;

runtime truth;

статусы;

геометрия тела;

Face Map skeleton;

масса / CoM / inertia как обязательные сущности;

байонетная цепочка;

RCS baseline;

battery / supercap split;

node-based thermal model;

сенсоры с source / freshness / trust;

связь с ограничениями;

NBL emergency low-rate only;

protection not absolute shield;

module passport;

command lifecycle;

SAFE;

ORION Evidence;

audit / blackbox;

documentation-only repository boundary.

Этого достаточно, чтобы не строить дальнейшую работу на ложной физике.

---

## 34. Как читать этот пакет

Читать пакет лучше так:

сначала `00_INDEX.md`;

затем `01_BODY_CANON.md`;

затем `02_REQUIREMENTS.md`;

затем `03_ARCHITECTURE_VIEWPOINTS.md`;

затем `04_CALCULATION_FRAME.md`;

затем `05_ENGINEERING_RATIONALE.md`;

затем `06_INTERFACE_CONTROL.md`;

затем `07_ADR/`;

затем `08_IMPLEMENTATION_BRIDGE.md`;

затем `09_ACCEPTANCE_CHECKS.md`;

после этого читать `10_READER_MANUAL.md` как цельную сборку.

Reader manual удобен для понимания.

Source files нужны для точной работы.

---

## 35. Итоговая формула

QIKI Body v0.2.2 фиксирует QIKI как машинное тело.

Тело важнее голоса.

Runtime truth важнее текста.

Evidence важнее уверенности.

Паспорт важнее названия модуля.

SoC_cap важнее иллюзии полной батареи для пиковых действий.

Hard lock важнее soft capture.

Effect confirmation важнее ACK.

Audit важнее красивого отчёта.

Blackbox важнее посмертной догадки.

Если данных не хватает, нужно писать TBD, target-only, template-only, rules-only или calculation-required.

Если evidence нет, нельзя писать implemented.

Если verification нет, нельзя писать verified.

Это минимальная честность тела QIKI.
