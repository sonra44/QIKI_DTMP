# QIKI Body v0.2.2 — Реестр требований

## 0. Назначение документа

Этот документ переводит канон тела QIKI в проверяемый слой требований.

`02_REQUIREMENTS.md` не вводит новый канон и не добавляет новые технологии, модули, лорные расширения или runtime-фичи.

Документ берёт правила из `01_BODY_CANON.md` и оформляет их как трассируемые требования с идентификаторами, статусами, приоритетами, способами проверки и evidence status.

Этот документ является частью documentation-only пакета.

Он не утверждает, что текущий runtime уже реализует перечисленные требования.

Главное правило:

Canon не означает implemented.

Target-only не означает runtime-ready.

Template-only не означает, что runtime schema уже существует.

Rules-only не означает, что protocol уже реализован.

Calculation-required не означает, что расчёт уже выполнен.

Implemented требует evidence.

Verified требует evidence и verification.

---

## 1. Статус документа

Файл:

`02_REQUIREMENTS.md`

Версия:

`v0.2.2`

Статус:

`requirements register / target canon`

Тип:

`documentation-only`

Runtime conformance:

`not claimed`

Primary source:

`01_BODY_CANON.md`

Назначение:

зафиксировать проверяемые требования QIKI Body v0.2.2 без объявления runtime-реализации.

---

## 2. Как читать требования

Каждое требование имеет идентификатор вида:

`REQ-NAMESPACE-###`

Где `NAMESPACE` указывает область требования, а `###` — порядковый номер внутри области.

Требование должно быть проверяемым.

Плохая формулировка:

“QIKI должна быть реалистичной.”

Это не требование, а намерение.

Корректная формулировка:

“QIKI SHALL NOT classify a module as runtime-ready unless the module has a validated module passport.”

Это требование можно проверить: есть паспорт или нет, валидирован он или нет, показывается ли модуль как runtime-ready.

---

## 3. Обязательные поля требования

Каждое требование должно иметь следующие поля:

ID;

Title;

Statement;

Rationale;

Priority;

Status;

Verification method;

Evidence status;

Related documents;

Notes, если нужны.

---

## 4. Нормативные слова

В requirement statements используются следующие ключевые слова:

`SHALL` — обязательно.

`SHALL NOT` — запрещено.

`MAY` — разрешено, но не обязательно.

`SHOULD` — рекомендуется, но не является жёстким обязательством.

В каноническом слое QIKI Body v0.2.2 предпочтительны `SHALL` и `SHALL NOT`.

---

## 5. Статусы требований

### 5.1. `canon`

Требование принято как закон проекта.

Canon не означает implemented.

### 5.2. `target-only`

Требование является целевым, но текущий runtime ещё не обязан его поддерживать.

### 5.3. `template-only`

Есть обязательный шаблон, но нет утверждения, что runtime schema или runtime instances уже существуют.

### 5.4. `rules-only`

Есть правила, но нет утверждения, что protocol или runtime enforcement уже реализованы.

### 5.5. `calculation-required`

Нужен расчёт до утверждения чисел, карт, матриц, порогов или коэффициентов.

### 5.6. `implemented`

Требование реализовано в runtime.

Этот статус запрещено ставить без evidence.

### 5.7. `verified`

Требование реализовано и прошло принятый метод проверки.

Этот статус запрещено ставить без evidence и verification.

### 5.8. `superseded`

Требование заменено новым.

### 5.9. `rejected`

Требование рассмотрено и отклонено.

---

## 6. Методы проверки

Допустимые методы проверки:

review;

inspection;

static check;

schema validation;

unit test;

integration test;

simulation test;

telemetry check;

UI evidence check;

command rejection scenario;

audit replay;

blackbox replay;

manual scenario;

documentation diff check.

На текущей стадии большинство требований имеет evidence status:

`documentation-only`

Это нормально. Документ фиксирует целевой канон и требования, а не runtime-реализацию.

---

## 7. Namespace требований

`REQ-BODY` — тело, идентичность, runtime truth.

`REQ-GEOM` — геометрия, грани, Face Map.

`REQ-MASS` — масса, центр масс, инерция.

`REQ-BAYONET` — байонетный интерфейс.

`REQ-RCS` — RCS и движение.

`REQ-POWER` — питание и пиковая мощность.

`REQ-THERMAL` — тепловая модель.

`REQ-SENSOR` — сенсоры и доверие к данным.

`REQ-COMMS` — связь.

`REQ-NBL` — NBL.

`REQ-PROTECT` — защита.

`REQ-FIELD` — field drive и Terta-exotic движение.

`REQ-MODULE` — модульность и паспорт модуля.

`REQ-CMD` — command gating.

`REQ-SAFE` — SAFE.

`REQ-ORION` — ORION Evidence.

`REQ-AUDIT` — ACK, effect confirmation, audit, blackbox.

`REQ-REPO` — репозиторное внедрение.

`REQ-ADR` — архитектурные решения.

---

# 8. REQ-BODY — тело, идентичность, runtime truth

## REQ-BODY-001 — QIKI как машинное тело

Statement:

QIKI SHALL be treated as a machine body, not as a model voice, interface panel, character or generic assistant.

Rationale:

Главный риск проекта — превратить QIKI в говорящий интерфейс без физической причинности.

Priority:

P0.

Status:

canon.

Verification method:

review; future runtime state inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-BODY-002 — Приоритет runtime truth

Statement:

Physical truth about QIKI SHALL come from runtime state, simulation, telemetry, events, ACK, effect confirmation, audit and blackbox.

Rationale:

Текст, голос и интерфейс не должны подменять физическое состояние тела.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future telemetry check; audit replay; blackbox replay.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

## REQ-BODY-003 — Модель не является физической истиной

Statement:

The language model SHALL NOT be treated as the final source of physical truth about QIKI body state.

Rationale:

Модель может объяснять, связывать факты и строить гипотезы, но не подтверждать физический факт.

Priority:

P0.

Status:

canon.

Verification method:

review; future ORION evidence check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `07_ADR/ADR-0001-machine-body-not-model-voice.md`

## REQ-BODY-004 — Возможность не появляется бесплатно

Statement:

QIKI SHALL NOT gain a physical capability without an associated cost, limitation, status and evidence path.

Rationale:

Каждая возможность должна иметь цену: массу, питание, тепло, риск, ограничения, телеметрию и доказательный след.

Priority:

P0.

Status:

canon.

Verification method:

review; module passport inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`

## REQ-BODY-005 — Постоянная идентичность QIKI

Statement:

QIKI SHALL remain one persistent machine body across module configurations.

Rationale:

Модульность меняет эксплуатационный профиль, но не создаёт нового робота.

Priority:

P1.

Status:

canon.

Verification method:

review; future body configuration snapshot.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-BODY-006 — Маркировка неполных данных

Statement:

Missing, stale, hypothetical, local reconstruction, target-only and calculation-required data SHALL be explicitly marked.

Rationale:

Неполнота допустима; ложная уверенность недопустима.

Priority:

P0.

Status:

canon / target-only.

Verification method:

review; future ORION evidence check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `03_ARCHITECTURE_VIEWPOINTS.md`; `06_INTERFACE_CONTROL.md`

---

# 9. REQ-GEOM — геометрия и Face Map

## REQ-GEOM-001 — Додекаэдрическое тело

Statement:

QIKI body SHALL be represented as a dodecahedral machine body with twelve functional faces.

Rationale:

Двенадцать граней являются основой хардпоинтов, модульности, сенсоров, RCS, радиаторов, байонетов и ограничений.

Priority:

P0.

Status:

canon.

Verification method:

review; future body schema inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`

## REQ-GEOM-002 — Постоянные face_id

Statement:

Each QIKI face SHALL have a persistent face_id from F00 to F11.

Rationale:

Runtime не должен зависеть от камеры, UI или текущей ориентации QIKI в мире.

Priority:

P0.

Status:

target-only.

Verification method:

future schema validation; inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`

## REQ-GEOM-003 — Face Map обязательна

Statement:

A Face Map SHALL exist before modules are treated as runtime-mounted on body faces.

Rationale:

Без Face Map модульность превращается в произвольную установку “на корпус”.

Priority:

P0.

Status:

target-only / calculation-required.

Verification method:

future schema validation; documentation review.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`

## REQ-GEOM-004 — Нормали граней требуют расчёта

Statement:

Face normals SHALL be marked TBD or calculation-required until explicitly defined in body frame.

Rationale:

Без нормалей нельзя честно рассчитать сенсоры, радиаторы, RCS, байонеты, выносные модули, Thrust Map и Torque Map.

Priority:

P1.

Status:

calculation-required.

Verification method:

calculation review; future geometry validation.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`

## REQ-GEOM-005 — Запрет произвольной установки

Statement:

A module SHALL NOT be mounted on an arbitrary body location without mount point, face_id or approved external interface.

Rationale:

Модуль без точки установки не является физическим runtime-модулем.

Priority:

P0.

Status:

canon / target-only.

Verification method:

module passport inspection; future runtime validation.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `06_INTERFACE_CONTROL.md`

---

# 10. REQ-MASS — масса, центр масс, инерция

## REQ-MASS-001 — Масса обязательна для физического модуля

Statement:

Any runtime module SHALL define mass or explicitly declare mass as TBD / calculation-required before runtime readiness.

Rationale:

Модуль без массы не является физической частью тела.

Priority:

P0.

Status:

canon / target-only.

Verification method:

module passport inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`

## REQ-MASS-002 — CoM и inertia обязательны для реконфигурации

Statement:

Any body reconfiguration SHALL account for CoM impact and inertia impact or mark them calculation-required.

Rationale:

QIKI должна управляться как физическое тело, а не как абстрактная точка.

Priority:

P0.

Status:

canon / calculation-required.

Verification method:

calculation review; future simulation test.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`

## REQ-MASS-003 — Тяжёлые асимметричные модули ограничивают движение

Statement:

Heavy or asymmetric modules SHALL trigger paired mounting, compensation, restricted motion, calculation-required status or command restrictions.

Rationale:

Смещение центра масс и инерции должно иметь операционные последствия.

Priority:

P1.

Status:

canon / target-only.

Verification method:

module passport inspection; future command rejection scenario.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`

## REQ-MASS-004 — ORION показывает последствия массы

Statement:

ORION SHALL show mass, CoM, inertia and movement restrictions when they are known or explicitly mark them missing / TBD.

Rationale:

Оператор должен понимать, как конфигурация изменила тело.

Priority:

P1.

Status:

target-only.

Verification method:

future UI evidence check.

Evidence status:

documentation-only.

Related documents:

`03_ARCHITECTURE_VIEWPOINTS.md`; `04_CALCULATION_FRAME.md`

---

# 11. REQ-BAYONET — байонетный интерфейс

## REQ-BAYONET-001 — Два противоположных байонета

Statement:

QIKI SHALL define two opposite bayonet interfaces as the primary external reconfiguration interfaces.

Rationale:

Байонеты являются главным механическим, энергетическим, информационным и каскадным интерфейсом тела.

Priority:

P0.

Status:

canon.

Verification method:

review; future body schema inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-BAYONET-002 — Магнит не является силовым замком

Statement:

Magnetic pre-align SHALL NOT be treated as a mechanical hard lock.

Rationale:

Магнитное выравнивание допустимо как предварительная стадия, но не как силовое соединение.

Priority:

P0.

Status:

canon.

Verification method:

review; future interface state validation.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `05_ENGINEERING_RATIONALE.md`; `07_ADR/ADR-0009-bayonet-mechanical-hard-lock.md`

## REQ-BAYONET-003 — Последовательность подключения обязательна

Statement:

Bayonet connection SHALL follow approach → alignment → magnetic pre-align → soft capture → mechanical hard lock → structural check → electrical safety → umbilical mate → module handshake → passport validation → bridge allowed.

Rationale:

Power/data bridge не должен активироваться из soft capture или непроверенного соединения.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future interface state validation; command rejection scenario.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

## REQ-BAYONET-004 — Bridge запрещён до проверки

Statement:

Power/data bridge SHALL NOT be treated as active before hard lock, structural check, electrical safety, handshake and passport validation.

Rationale:

Физическая близость или soft capture не доказывают безопасное соединение.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future interface validation; audit replay.

Evidence status:

documentation-only.

Related documents:

`06_INTERFACE_CONTROL.md`

## REQ-BAYONET-005 — Bridge ограничивает burn

Statement:

Aggressive burn SHALL be blocked during bridge active unless the connection is explicitly structural-rated for that maneuver.

Rationale:

Пристыкованный объект меняет нагрузку, инерцию и риск разрушения соединения.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future command rejection scenario.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

---

# 12. REQ-RCS — RCS и движение

## REQ-RCS-001 — Базовая RCS-схема

Statement:

QIKI baseline RCS SHALL define four clusters with four nozzles each, for sixteen nozzles total.

Rationale:

Распределённая RCS является штатной основой движения QIKI.

Priority:

P0.

Status:

canon / geometry TBD.

Verification method:

review; future body schema inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`

## REQ-RCS-002 — Нет главного хвостового двигателя как baseline

Statement:

QIKI SHALL NOT treat a main tail engine as the baseline movement model.

Rationale:

QIKI движется как многогранное тело с распределённой тягой.

Priority:

P1.

Status:

canon.

Verification method:

review.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-RCS-003 — Thrust Map обязательна

Statement:

RCS maneuver capability SHALL NOT be considered proven until a Thrust Map exists or is marked calculation-required.

Rationale:

Управляемость нельзя объявлять без карты тяги.

Priority:

P0.

Status:

calculation-required.

Verification method:

calculation review; future simulation test.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`; `07_ADR/ADR-0010-rcs-thrust-torque-maps-required.md`

## REQ-RCS-004 — Torque Map обязательна

Statement:

RCS rotational control SHALL NOT be considered proven until a Torque Map exists or is marked calculation-required.

Rationale:

Остаточные моменты, плечи сил и влияние CoM должны быть проверяемыми.

Priority:

P0.

Status:

calculation-required.

Verification method:

calculation review; future simulation test.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`; `07_ADR/ADR-0010-rcs-thrust-torque-maps-required.md`

## REQ-RCS-005 — Manual override только debug-only

Statement:

Manual control of individual RCS nozzles SHALL be debug-only or emergency engineering mode, not a normal gameplay command.

Rationale:

Ручное управление отдельными соплами ломает safety controller и компенсационную логику.

Priority:

P1.

Status:

canon.

Verification method:

review; future UI evidence check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-RCS-006 — RCS команды проходят gating

Statement:

RCS commands SHALL pass command gating before execution.

Rationale:

Манёвр может быть опасен из-за SoC_cap, тепла, CoM, inertia, bayonet state, bridge state, sensor trust or SAFE.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future command rejection scenario; audit replay.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

---

# 13. REQ-POWER — питание и пиковая мощность

## REQ-POWER-001 — Каноническая энергетическая цепочка

Statement:

QIKI power architecture SHALL follow source → battery → bus → supercap → peak consumers.

Rationale:

Энергия должна быть разделена по ролям: средняя генерация, запас жизни, распределение, пики и потребители.

Priority:

P0.

Status:

canon / target-only.

Verification method:

review; future telemetry check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `07_ADR/ADR-0003-battery-supercap-split.md`

## REQ-POWER-002 — SoC_bat и SoC_cap разделены

Statement:

SoC_bat and SoC_cap SHALL be treated as separate quantities.

Rationale:

Батарея показывает запас жизни; supercap показывает готовность к краткому пику.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future telemetry check; UI evidence check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `05_ENGINEERING_RATIONALE.md`

## REQ-POWER-003 — Пиковые действия требуют cap, PDU и thermal clearance

Statement:

Peak actions SHALL require sufficient SoC_cap, PDU allowance and thermal clearance.

Rationale:

Заряженная батарея не означает право на boost, NBL packet, high-power scan or active field.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future command rejection scenario; telemetry check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

## REQ-POWER-004 — RTG не boost-source

Statement:

RTG-class source SHALL be treated as heavy / trickle source and SHALL NOT be treated as boost-source.

Rationale:

RTG даёт постоянную мощность и тепло, но не должен отменять supercap, PDU и thermal model.

Priority:

P0.

Status:

canon.

Verification method:

review.

Evidence status:

documentation-only.

Related documents:

`05_ENGINEERING_RATIONALE.md`; `07_ADR/ADR-0004-rtg-trickle-not-boost.md`

## REQ-POWER-005 — Reactor-class source external

Statement:

Reactor-class source SHALL be treated as external / station / sled / heavy infrastructure, not as a normal face-mounted QIKI module.

Rationale:

Реакторный источник не должен становиться обычным апгрейдом маленького тела QIKI.

Priority:

P0.

Status:

canon.

Verification method:

review.

Evidence status:

documentation-only.

Related documents:

`05_ENGINEERING_RATIONALE.md`; `07_ADR/ADR-0005-reactor-external-source.md`

---

# 14. REQ-THERMAL — тепловая модель

## REQ-THERMAL-001 — Node-based thermal model

Statement:

QIKI SHALL use node-based thermal model for body-critical systems.

Rationale:

Одна общая температура не объясняет локальные перегревы PDU, battery, supercap, RCS, sensor head, comms, bayonet or external module.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future telemetry check; simulation test.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`

## REQ-THERMAL-002 — Действия создают тепло

Statement:

Power-consuming or high-load actions SHALL account for heat generation or mark heat as TBD / calculation-required.

Rationale:

Команды должны иметь тепловую цену.

Priority:

P0.

Status:

canon / calculation-required.

Verification method:

calculation review; future simulation test.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`

## REQ-THERMAL-003 — Тепловой отказ возвращает reason_code

Statement:

Thermal command rejection SHALL return a reason_code and blocking thermal node when known.

Rationale:

Оператор должен понимать, какой узел блокирует команду.

Priority:

P1.

Status:

target-only.

Verification method:

future command rejection scenario; UI evidence check.

Evidence status:

documentation-only.

Related documents:

`06_INTERFACE_CONTROL.md`; `09_ACCEPTANCE_CHECKS.md`

---

# 15. REQ-SENSOR — сенсоры и доверие

## REQ-SENSOR-001 — Сенсорное значение имеет источник

Statement:

Every sensor value used for decision-making SHALL have a source or be marked missing / unknown / hypothesis / local reconstruction.

Rationale:

Видеть не значит знать; значение без source не должно быть физической истиной.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future telemetry check; ORION evidence check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

## REQ-SENSOR-002 — Freshness обязательна

Statement:

Sensor values SHALL expose freshness, timestamp or freshness class before being used for dangerous commands.

Rationale:

Stale data can be physically dangerous.

Priority:

P0.

Status:

target-only.

Verification method:

future telemetry check; command rejection scenario.

Evidence status:

documentation-only.

Related documents:

`03_ARCHITECTURE_VIEWPOINTS.md`; `06_INTERFACE_CONTROL.md`

## REQ-SENSOR-003 — Trust status обязателен

Statement:

Sensor data SHALL expose trust status such as trusted, degraded, conflicting, blind, stale, missing, local_reconstruction or hypothesis.

Rationale:

Сенсор может быть валидным, но физически недостоверным или конфликтующим.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future telemetry check; ORION evidence check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `03_ARCHITECTURE_VIEWPOINTS.md`

## REQ-SENSOR-004 — Dangerous commands cannot rely on stale/conflicting data

Statement:

Dangerous commands SHALL NOT rely on stale or conflicting sensor data without additional confirmation or explicit override policy.

Rationale:

Опасные действия не должны строиться на недостоверной картине мира.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future command rejection scenario.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

---

# 16. REQ-COMMS — связь

## REQ-COMMS-001 — Связь не равна безопасности

Statement:

Communication availability SHALL NOT be treated as communication safety.

Rationale:

Канал может быть активен, но опасен по EMCON, теплу, питанию, задержке, сигнатуре или stale data.

Priority:

P1.

Status:

canon.

Verification method:

review; future ORION evidence check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-COMMS-002 — Канал связи имеет стоимость и состояние

Statement:

Communication channels SHALL define or mark TBD their bandwidth, latency, power cost, thermal cost, signature, EMCON state and delivery state.

Rationale:

Связь является физическим и операционным каналом, а не абстрактной лампочкой “signal”.

Priority:

P1.

Status:

target-only.

Verification method:

future telemetry check; interface inspection.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`; `06_INTERFACE_CONTROL.md`

---

# 17. REQ-NBL — NBL

## REQ-NBL-001 — Baseline NBL emergency low-rate only

Statement:

Baseline NBL SHALL be treated as emergency low-rate channel only.

Rationale:

NBL не должен быть обычной широкополосной связью.

Priority:

P0.

Status:

canon.

Verification method:

review.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `05_ENGINEERING_RATIONALE.md`; `07_ADR/ADR-0006-nbl-emergency-low-rate.md`

## REQ-NBL-002 — NBL не передаёт bulk telemetry

Statement:

Baseline NBL SHALL NOT be used for bulk telemetry, normal comms or wideband data transfer.

Rationale:

Baseline NBL предназначен для коротких критических пакетов.

Priority:

P0.

Status:

canon.

Verification method:

review; future command rejection scenario.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `05_ENGINEERING_RATIONALE.md`

## REQ-NBL-003 — NBL требует criticality gating

Statement:

NBL emergency packet SHALL require criticality gating, SoC_cap check, thermal check and audit entry.

Rationale:

NBL-пакет должен быть дорогим, ограниченным и доказательным.

Priority:

P0.

Status:

rules-only / target-only.

Verification method:

future command rejection scenario; audit replay.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`; `06_INTERFACE_CONTROL.md`

## REQ-NBL-004 — Расширенный NBL только Terta-exotic

Statement:

Any NBL capability above emergency low-rate baseline SHALL be explicitly marked Terta-exotic.

Rationale:

Экзотические возможности не должны притворяться baseline engineering.

Priority:

P0.

Status:

canon.

Verification method:

review.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `05_ENGINEERING_RATIONALE.md`

---

# 18. REQ-PROTECT — защита

## REQ-PROTECT-001 — Нет абсолютного щита

Statement:

QIKI protection SHALL NOT be described as an absolute shield.

Rationale:

Защита снижает конкретный риск за конкретную цену, но не даёт неуязвимость.

Priority:

P0.

Status:

canon.

Verification method:

review.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `05_ENGINEERING_RATIONALE.md`; `07_ADR/ADR-0007-deflector-not-absolute-shield.md`

## REQ-PROTECT-002 — Защита имеет цену

Statement:

Protective systems SHALL define or mark TBD their mass, power cost, thermal cost, sensor impact, comms impact, EMCON impact and maneuver restrictions.

Rationale:

Защитный модуль не должен быть бесплатной магией.

Priority:

P0.

Status:

canon / target-only / calculation-required.

Verification method:

module passport inspection; calculation review.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`

---

# 19. REQ-FIELD — field drive и Terta-exotic движение

## REQ-FIELD-001 — Field drive не baseline

Statement:

Field drive SHALL NOT be treated as baseline QIKI propulsion.

Rationale:

Baseline-движение должно опираться на RCS и физически ограниченные классы тяги.

Priority:

P0.

Status:

canon.

Verification method:

review.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `07_ADR/ADR-0008-field-drive-not-baseline.md`

## REQ-FIELD-002 — Terta-exotic field drive имеет цену

Statement:

If field drive exists as Terta-exotic capability, it SHALL define energy cost, thermal cost, limits, risks, signature, cooldown, command gating and evidence path.

Rationale:

Экзотическая технология должна быть дорогой и проверяемой.

Priority:

P1.

Status:

canon / target-only.

Verification method:

review; future module passport inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `05_ENGINEERING_RATIONALE.md`

---

# 20. REQ-MODULE — модульность и паспорт

## REQ-MODULE-001 — Паспорт модуля обязателен

Statement:

A module SHALL NOT be classified as runtime-ready unless it has a module passport.

Rationale:

Название модуля не является физическим контрактом.

Priority:

P0.

Status:

canon / template-only / target-only.

Verification method:

module passport inspection; future schema validation.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `04_CALCULATION_FRAME.md`; `07_ADR/ADR-0011-module-passport-mandatory.md`

## REQ-MODULE-002 — Модуль должен иметь физические поля

Statement:

A runtime module SHALL define or mark TBD mount point, mass, CoM impact, inertia impact, power, heat, capabilities, restrictions, failure modes and reason_codes.

Rationale:

Модуль является изменением тела, а не бонусом.

Priority:

P0.

Status:

canon / template-only.

Verification method:

module passport inspection.

Evidence status:

documentation-only.

Related documents:

`04_CALCULATION_FRAME.md`

## REQ-MODULE-003 — Модуль даёт и забирает

Statement:

A module SHOULD define both provided capabilities and removed or restricted capabilities.

Rationale:

Модульность QIKI — это смена цены, а не рост силы без последствий.

Priority:

P1.

Status:

canon.

Verification method:

module passport inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-MODULE-004 — Конфигурация не должна улучшать всё

Statement:

A QIKI configuration SHALL NOT improve all major capabilities without corresponding costs or restrictions.

Rationale:

Конфигурации без цены ломают машинное тело и превращают модульность в магазин апгрейдов.

Priority:

P1.

Status:

canon.

Verification method:

review; module passport inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

---

# 21. REQ-CMD — command gating

## REQ-CMD-001 — Канонический lifecycle команды

Statement:

QIKI commands SHALL follow request → validation → allowed / rejected → publish → ACK → effect confirmation → audit.

Rationale:

Команда не должна превращаться в мгновенный эффект.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future integration test; audit replay.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

## REQ-CMD-002 — Request не действие

Statement:

Request SHALL NOT be treated as physical action.

Rationale:

Запрос только инициирует проверку.

Priority:

P0.

Status:

canon.

Verification method:

review; future command trace inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-CMD-003 — Allowed не execution

Statement:

Allowed SHALL NOT be treated as executed.

Rationale:

Разрешение команды не означает доставку, принятие или физический эффект.

Priority:

P0.

Status:

canon.

Verification method:

review; future command trace inspection.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-CMD-004 — ACK не effect confirmation

Statement:

ACK SHALL NOT be treated as effect confirmation.

Rationale:

ACK подтверждает обработку или доставку команды, но не изменение тела или мира.

Priority:

P0.

Status:

canon.

Verification method:

review; audit replay.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `07_ADR/ADR-0015-ack-not-effect-confirmation.md`

## REQ-CMD-005 — Rejected должен иметь reason_codes

Statement:

Rejected commands SHALL return reason_codes when blocking information is known.

Rationale:

Оператор должен понимать, почему тело отказало.

Priority:

P0.

Status:

target-only.

Verification method:

future command rejection scenario; ORION evidence check.

Evidence status:

documentation-only.

Related documents:

`06_INTERFACE_CONTROL.md`; `09_ACCEPTANCE_CHECKS.md`

---

# 22. REQ-SAFE — SAFE

## REQ-SAFE-001 — SAFE является режимом выживания

Statement:

SAFE SHALL be treated as physical survival mode, not as decorative alert state.

Rationale:

SAFE должен защищать тело от опасных действий и деградаций.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future integration test; command rejection scenario.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

## REQ-SAFE-002 — SAFE может блокировать команды

Statement:

SAFE SHALL be able to block commands even when energy is available.

Rationale:

Наличие энергии не означает физическую безопасность действия.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future command rejection scenario.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`

## REQ-SAFE-003 — SAFE должен объясняться

Statement:

SAFE state SHALL expose activation cause, blocked commands, allowed commands and exit conditions when known.

Rationale:

Оператор должен понимать, почему тело вошло в SAFE и что можно делать дальше.

Priority:

P1.

Status:

target-only.

Verification method:

future UI evidence check.

Evidence status:

documentation-only.

Related documents:

`03_ARCHITECTURE_VIEWPOINTS.md`; `06_INTERFACE_CONTROL.md`

---

# 23. REQ-ORION — ORION Evidence

## REQ-ORION-001 — ORION является станцией доказательств

Statement:

ORION SHALL be treated as evidence station, not as decorative HUD.

Rationale:

ORION должен показывать источники, свежесть, доверие, ограничения, reason_codes и доказательный след.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future UI evidence check.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `07_ADR/ADR-0014-orion-evidence-station.md`

## REQ-ORION-002 — ORION не выдумывает физику

Statement:

ORION SHALL NOT present physical state as confirmed without source, telemetry, event, ACK, effect confirmation, audit or explicit status marking.

Rationale:

Интерфейс не должен подменять runtime truth.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future UI evidence check; audit replay.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

## REQ-ORION-003 — ORION показывает missing / target-only / not implemented

Statement:

ORION SHALL mark missing, target-only, not implemented and calculation-required states instead of presenting them as runtime-ready.

Rationale:

Оператор не должен путать проектное требование с работающим состоянием.

Priority:

P0.

Status:

target-only.

Verification method:

future UI evidence check.

Evidence status:

documentation-only.

Related documents:

`03_ARCHITECTURE_VIEWPOINTS.md`; `09_ACCEPTANCE_CHECKS.md`

---

# 24. REQ-AUDIT — ACK, effect confirmation, audit, blackbox

## REQ-AUDIT-001 — Audit фиксирует command lifecycle

Statement:

Audit SHALL record request, validation result, reason_codes, publish, ACK, effect confirmation, operator confirmation, SAFE intervention, failure, timeout, abort and state transition when available.

Rationale:

Цепочка действия должна быть восстановима.

Priority:

P0.

Status:

canon / target-only.

Verification method:

future audit replay.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

## REQ-AUDIT-002 — Blackbox сохраняет критические события

Statement:

Blackbox SHALL preserve critical body events relevant to failure analysis, death, loss, detach, SAFE escalation, sensor conflict, power loss, thermal failure and dangerous command chains.

Rationale:

Blackbox является последней памятью тела и основой postmortem-анализа.

Priority:

P1.

Status:

canon / target-only.

Verification method:

future blackbox replay.

Evidence status:

documentation-only.

Related documents:

`01_BODY_CANON.md`; `06_INTERFACE_CONTROL.md`

---

# 25. REQ-REPO — репозиторное внедрение

## REQ-REPO-001 — Первый патч documentation-only

Statement:

The first repository patch for QIKI Body v0.2.2 SHALL be documentation-only.

Rationale:

Нельзя смешивать канон, расчётный каркас и runtime-реализацию.

Priority:

P0.

Status:

canon.

Verification method:

documentation diff check.

Evidence status:

documentation-only.

Related documents:

`00_INDEX.md`; `08_IMPLEMENTATION_BRIDGE.md`; `09_ACCEPTANCE_CHECKS.md`; `07_ADR/ADR-0012-documentation-only-first-patch.md`

## REQ-REPO-002 — Runtime changes запрещены первым патчем

Statement:

The first documentation package patch SHALL NOT modify runtime code, proto, NATS, gRPC, telemetry paths, ORION UI, MFD logic, generated files or tests implying implemented runtime behavior.

Rationale:

Documentation-only boundary должен быть проверяемым.

Priority:

P0.

Status:

canon.

Verification method:

documentation diff check.

Evidence status:

documentation-only.

Related documents:

`00_INDEX.md`; `09_ACCEPTANCE_CHECKS.md`

## REQ-REPO-003 — Старый GDD сохраняется

Statement:

Old QIKI GDD files SHALL be preserved as game-design and historical context during the first documentation patch.

Rationale:

Старый GDD нельзя уничтожать хаотично; конфликтующие места должны быть помечены alignment / superseded.

Priority:

P1.

Status:

canon.

Verification method:

documentation diff check.

Evidence status:

documentation-only.

Related documents:

`00_INDEX.md`; `08_IMPLEMENTATION_BRIDGE.md`; `07_ADR/ADR-0002-body-canon-separated-from-old-gdd.md`

## REQ-REPO-004 — Reader manual является derived

Statement:

`10_READER_MANUAL.md` SHALL be treated as derived reader document, not as higher source of truth than primary source files.

Rationale:

Читательская сборка нужна для чтения, но не должна побеждать source files при конфликте.

Priority:

P0.

Status:

canon.

Verification method:

review; documentation diff check.

Evidence status:

documentation-only.

Related documents:

`00_INDEX.md`; `07_ADR/ADR-0013-reader-manual-derived.md`

---

# 26. REQ-ADR — архитектурные решения

## REQ-ADR-001 — Фундаментальные решения фиксируются ADR

Statement:

Fundamental body canon decisions SHALL be recorded as ADR when they must not be silently reversed.

Rationale:

Решения вроде “NBL emergency low-rate only” или “ACK is not effect confirmation” не должны размягчаться без следа.

Priority:

P1.

Status:

canon.

Verification method:

review; ADR inspection.

Evidence status:

documentation-only.

Related documents:

`07_ADR/`

## REQ-ADR-002 — Изменение ADR требует superseding

Statement:

Accepted ADR SHALL NOT be silently rewritten to change decision history; changed decisions SHALL create a new ADR or mark the old ADR superseded.

Rationale:

История решений нужна для управления каноном.

Priority:

P1.

Status:

canon.

Verification method:

ADR inspection.

Evidence status:

documentation-only.

Related documents:

`07_ADR/`

---

## 27. Итоговое правило требований

Этот файл фиксирует требования QIKI Body v0.2.2 как target documentation canon.

Он не доказывает runtime conformance.

Он не создаёт runtime schema.

Он не создаёт telemetry paths.

Он не меняет ORION UI.

Он не меняет MFD.

Он не меняет proto, NATS или gRPC.

Любое требование со статусом `implemented` должно иметь evidence.

Любое требование со статусом `verified` должно иметь evidence и verification.

Если evidence нет, использовать `canon`, `target-only`, `template-only`, `rules-only` или `calculation-required`.
