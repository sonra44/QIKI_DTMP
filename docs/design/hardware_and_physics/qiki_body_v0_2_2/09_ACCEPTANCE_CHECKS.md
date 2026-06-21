# QIKI Body v0.2.2 — Acceptance Checks

## 0. Назначение документа

Этот документ фиксирует проверки приёмки для **QIKI Body v0.2.2 Documentation Package**.

Его задача — не расширять канон, не добавлять новые модули и не описывать runtime-реализацию, а проверить, что документационный пакет собран корректно, не врёт о runtime и сохраняет границу между `canon`, `target-only`, `template-only`, `rules-only`, `calculation-required`, `implemented` и `verified`.

Этот документ является частью documentation-only пакета.

Он не является тестом runtime.

Он не меняет код.

Он не меняет proto, NATS, gRPC, telemetry paths, ORION UI или MFD.

Он не утверждает runtime conformance.

Главная формула:

Документ не равен реализации.

Таблица не равна расчёту.

Шаблон не равен runtime schema.

ADR не равен runtime behavior.

Reader manual не равен source of truth.

Implemented требует evidence.

Verified требует evidence и verification.

---

## 1. Статус документа

Файл:

`09_ACCEPTANCE_CHECKS.md`

Версия:

`v0.2.2`

Статус:

`acceptance checklist / documentation-only`

Runtime conformance:

`not claimed`

Primary source:

`00_INDEX.md`

Related source files:

`01_BODY_CANON.md`

`02_REQUIREMENTS.md`

`03_ARCHITECTURE_VIEWPOINTS.md`

`04_CALCULATION_FRAME.md`

`05_ENGINEERING_RATIONALE.md`

`06_INTERFACE_CONTROL.md`

`07_ADR/`

`08_IMPLEMENTATION_BRIDGE.md`

`10_READER_MANUAL.md`

---

## 2. Область проверки

Acceptance checks проверяют только документационный пакет.

Проверяется:

структура файлов;

наличие expected files;

наличие ADR;

source priority;

status legend;

documentation-only boundary;

связь со старым GDD;

отсутствие runtime claims без evidence;

отсутствие invented numbers;

отсутствие смешения статусов;

отсутствие runtime diff в первом patch;

пометка reader manual как derived.

Не проверяется:

реальная физика runtime;

реальные telemetry paths;

реальный ORION UI;

реальные proto / NATS / gRPC contracts;

реальная симуляция;

реальные тесты поведения тела;

реальные расчёты Thrust Map / Torque Map;

реальные тепловые коэффициенты;

реальные массы;

реальные сенсорные диапазоны.

---

## 3. Expected package tree

Пакет считается структурно собранным, если существует следующее дерево:

```text
docs/design/hardware_and_physics/qiki_body_v0_2_2/
├── 00_INDEX.md
├── 01_BODY_CANON.md
├── 02_REQUIREMENTS.md
├── 03_ARCHITECTURE_VIEWPOINTS.md
├── 04_CALCULATION_FRAME.md
├── 05_ENGINEERING_RATIONALE.md
├── 06_INTERFACE_CONTROL.md
├── 07_ADR/
│   ├── ADR-0001-machine-body-not-model-voice.md
│   ├── ADR-0002-body-canon-separated-from-old-gdd.md
│   ├── ADR-0003-battery-supercap-split.md
│   ├── ADR-0004-rtg-trickle-not-boost.md
│   ├── ADR-0005-reactor-external-source.md
│   ├── ADR-0006-nbl-emergency-low-rate.md
│   ├── ADR-0007-deflector-not-absolute-shield.md
│   ├── ADR-0008-field-drive-not-baseline.md
│   ├── ADR-0009-bayonet-mechanical-hard-lock.md
│   ├── ADR-0010-rcs-thrust-torque-maps-required.md
│   ├── ADR-0011-module-passport-mandatory.md
│   ├── ADR-0012-documentation-only-first-patch.md
│   ├── ADR-0013-reader-manual-derived.md
│   ├── ADR-0014-orion-evidence-station.md
│   └── ADR-0015-ack-not-effect-confirmation.md
├── 08_IMPLEMENTATION_BRIDGE.md
├── 09_ACCEPTANCE_CHECKS.md
└── 10_READER_MANUAL.md
```

Для текущей чистовой выгрузки допустимо, что `10_READER_MANUAL.md` будет создан последним.

---

## 4. File existence checks

Проверить наличие:

- [ ] `00_INDEX.md`
- [ ] `01_BODY_CANON.md`
- [ ] `02_REQUIREMENTS.md`
- [ ] `03_ARCHITECTURE_VIEWPOINTS.md`
- [ ] `04_CALCULATION_FRAME.md`
- [ ] `05_ENGINEERING_RATIONALE.md`
- [ ] `06_INTERFACE_CONTROL.md`
- [ ] `07_ADR/`
- [ ] `08_IMPLEMENTATION_BRIDGE.md`
- [ ] `09_ACCEPTANCE_CHECKS.md`
- [ ] `10_READER_MANUAL.md`

Проверить, что `07_ADR/` является директорией, а не единым большим markdown-файлом.

Проверить, что каждый ADR хранится отдельным файлом.

---

## 5. ADR checks

Проверить наличие начального набора ADR:

- [ ] `ADR-0001-machine-body-not-model-voice.md`
- [ ] `ADR-0002-body-canon-separated-from-old-gdd.md`
- [ ] `ADR-0003-battery-supercap-split.md`
- [ ] `ADR-0004-rtg-trickle-not-boost.md`
- [ ] `ADR-0005-reactor-external-source.md`
- [ ] `ADR-0006-nbl-emergency-low-rate.md`
- [ ] `ADR-0007-deflector-not-absolute-shield.md`
- [ ] `ADR-0008-field-drive-not-baseline.md`
- [ ] `ADR-0009-bayonet-mechanical-hard-lock.md`
- [ ] `ADR-0010-rcs-thrust-torque-maps-required.md`
- [ ] `ADR-0011-module-passport-mandatory.md`
- [ ] `ADR-0012-documentation-only-first-patch.md`
- [ ] `ADR-0013-reader-manual-derived.md`
- [ ] `ADR-0014-orion-evidence-station.md`
- [ ] `ADR-0015-ack-not-effect-confirmation.md`

Проверить, что каждый ADR содержит:

- [ ] Title
- [ ] Status
- [ ] Date
- [ ] Context
- [ ] Decision
- [ ] Rejected alternatives
- [ ] Consequences
- [ ] Related requirements
- [ ] Related viewpoints
- [ ] Related interfaces
- [ ] Related documents
- [ ] Review notes

Проверить, что ADR не изменяются задним числом как будто решение всегда было другим.

Если решение меняется, должен появиться новый ADR, а старый должен получить статус `superseded`.

---

## 6. Source priority checks

Проверить, что `00_INDEX.md` содержит source priority.

Минимальный порядок приоритета:

1. `01_BODY_CANON.md`
2. `02_REQUIREMENTS.md`
3. `03_ARCHITECTURE_VIEWPOINTS.md`
4. `04_CALCULATION_FRAME.md`
5. `05_ENGINEERING_RATIONALE.md`
6. `06_INTERFACE_CONTROL.md`
7. `07_ADR/`
8. `08_IMPLEMENTATION_BRIDGE.md`
9. `09_ACCEPTANCE_CHECKS.md`
10. `10_READER_MANUAL.md`

Проверить, что `00_INDEX.md` явно говорит:

- [ ] `10_READER_MANUAL.md` является derived file.
- [ ] Reader manual не заменяет primary source files.
- [ ] Если reader manual конфликтует с source files, source files имеют приоритет.

---

## 7. Status legend checks

Проверить, что пакет различает статусы:

- [ ] `canon`
- [ ] `target-only`
- [ ] `template-only`
- [ ] `rules-only`
- [ ] `calculation-required`
- [ ] `implemented`
- [ ] `verified`
- [ ] `superseded`
- [ ] `rejected`

Проверить, что пакет явно говорит:

- [ ] `canon` не означает `implemented`.
- [ ] `target-only` не означает `runtime-ready`.
- [ ] `template-only` не означает runtime schema.
- [ ] `rules-only` не означает protocol implemented.
- [ ] `calculation-required` не означает calculated.
- [ ] `implemented` требует evidence.
- [ ] `verified` требует evidence и verification.

---

## 8. Documentation-only boundary checks

Первый patch должен быть documentation-only.

Разрешено:

- [ ] create markdown files
- [ ] create ADR markdown files
- [ ] create local package index
- [ ] update documentation indexes
- [ ] add old GDD alignment note
- [ ] mark old conflicting statements as superseded
- [ ] add acceptance checklist
- [ ] add documentation-only review notes

Запрещено:

- [ ] runtime code changes
- [ ] simulation code changes
- [ ] ORION UI changes
- [ ] MFD changes
- [ ] proto changes
- [ ] NATS subject changes
- [ ] gRPC contract changes
- [ ] telemetry path changes
- [ ] generated file changes
- [ ] tests that imply runtime conformance
- [ ] fake evidence
- [ ] implemented claims without evidence
- [ ] verified claims without verification

Проверка считается проваленной, если patch меняет runtime-файлы.

---

## 9. No-runtime-diff checks

Проверить, что первый documentation-only patch не меняет:

- [ ] application source code
- [ ] simulation source code
- [ ] generated files
- [ ] protobuf files
- [ ] NATS subjects
- [ ] gRPC contracts
- [ ] telemetry schemas or paths
- [ ] ORION UI implementation
- [ ] MFD implementation
- [ ] runtime tests
- [ ] docker runtime config
- [ ] service configs that alter behavior

Если изменение runtime-файла необходимо, оно должно быть вынесено в отдельную задачу после принятия документационного пакета.

---

## 10. Implemented / verified claim checks

Проверить весь пакет на слова и формулировки:

- [ ] `implemented`
- [ ] `verified`
- [ ] `runtime-ready`
- [ ] `runtime supports`
- [ ] `already implemented`
- [ ] `conforms`
- [ ] `telemetry supports`
- [ ] `ORION shows`
- [ ] `system does`

Каждое использование `implemented` должно иметь evidence.

Каждое использование `verified` должно иметь verification.

Если evidence отсутствует, заменить на:

`target-only`

`template-only`

`rules-only`

`calculation-required`

`not claimed`

`documentation-only`

`future runtime work`

---

## 11. TBD / calculation-required checks

Проверить, что неизвестные значения не заменены выдуманными числами.

Следующие зоны должны оставаться `TBD` или `calculation-required`, если нет отдельного расчёта:

- [ ] точная геометрия додекаэдра QIKI
- [ ] нормали F00–F11
- [ ] соседство граней
- [ ] финальная Face Map
- [ ] точные mount constraints
- [ ] масса базового тела
- [ ] масса подсистем
- [ ] масса конкретных модулей
- [ ] local_position подсистем
- [ ] CoM_delta thresholds
- [ ] inertia matrix или inertia classes
- [ ] RCS thrust values
- [ ] RCS directions
- [ ] Thrust Map
- [ ] Torque Map
- [ ] plume-clearance zones
- [ ] working mass consumption
- [ ] battery capacity
- [ ] supercap capacity
- [ ] PDU limits
- [ ] source generation profiles
- [ ] thermal thresholds
- [ ] cooldown profiles
- [ ] bayonet structural rating
- [ ] bayonet power limits
- [ ] bridge data limits
- [ ] NBL packet size
- [ ] NBL cost
- [ ] sensor range
- [ ] sensor accuracy
- [ ] sensor update rate
- [ ] comms bandwidth
- [ ] radiation deflector effectiveness
- [ ] field / Terta-exotic effects, если они используются

Проверка считается проваленной, если появились численные значения без source, calculation или evidence.

---

## 12. Forbidden wording checks

Проверить, что опасные формулировки отсутствуют или помечены как superseded / rejected.

| Запрещённая формулировка | Корректная формулировка |
|---|---|
| RTG battery | RTG-class heavy / trickle source |
| RTG boost | RTG cannot be boost-source |
| RTG solves power | RTG does not remove battery / supercap / thermal constraints |
| Reactor module on face | Reactor-class external / station / sled source |
| Reactor upgrade | External reactor-class source with bridge and safety |
| NBL broadband | NBL emergency low-rate only |
| NBL normal telemetry | NBL critical packet only |
| NBL internet through everything | Baseline NBL is not wideband comms |
| Absolute shield | constrained protection / deflector |
| Invulnerable field | protection with limits, cost and failure modes |
| Field drive baseline | field drive Terta-exotic / not baseline |
| Pure energy thrust | propulsion requires working mass, environment interaction or explicit exotic status |
| Magnetic lock | magnetic pre-align / mechanical hard lock required |
| Soft capture connected | soft capture is not bridge allowed |
| RCS balanced | RCS requires Thrust Map and Torque Map |
| Full maneuverability | maneuverability requires maps, CoM and inertia checks |
| Module installed | module installed only with mount point and passport |
| Module active | module active only with state, power and thermal evidence |
| ACK complete | ACK is not effect confirmation |
| ORION truth | ORION evidence view with source |
| Target-only implemented | target-only is not runtime-ready |
| Template is schema | template-only is not runtime schema |
| Table is calculation | table is not calculated unless values are verified |

---

## 13. Old GDD relationship checks

Проверить, что старый GDD не удаляется первым documentation-only patch.

Проверить, что старый GDD получает alignment note или связанную пометку.

Проверить, что по вопросам body hardware / physics приоритет имеет QIKI Body v0.2.2.

Критичные superseded-зоны:

- [ ] магнитный замок как основной силовой байонет
- [ ] RTG как обычная батарейка
- [ ] реактор как обычный модуль на грань
- [ ] NBL как широкий канал данных
- [ ] щит как абсолютная защита
- [ ] field drive как baseline
- [ ] равномерная RCS без Thrust Map / Torque Map
- [ ] модуль без паспорта
- [ ] команда как мгновенный эффект
- [ ] ACK как effect confirmation
- [ ] ORION как decorative HUD

---

## 14. Requirements checks

Проверить `02_REQUIREMENTS.md`.

Минимально должно быть:

- [ ] namespace list
- [ ] requirement format
- [ ] status model
- [ ] verification methods
- [ ] evidence status
- [ ] REQ-BODY
- [ ] REQ-GEOM
- [ ] REQ-MASS
- [ ] REQ-BAYONET
- [ ] REQ-RCS
- [ ] REQ-POWER
- [ ] REQ-THERMAL
- [ ] REQ-SENSOR
- [ ] REQ-COMMS
- [ ] REQ-NBL
- [ ] REQ-PROTECT
- [ ] REQ-FIELD
- [ ] REQ-MODULE
- [ ] REQ-CMD
- [ ] REQ-SAFE
- [ ] REQ-ORION
- [ ] REQ-AUDIT
- [ ] REQ-REPO
- [ ] REQ-ADR

Проверить, что requirements не используют неясные слова без проверяемого смысла:

- [ ] “красиво”
- [ ] “удобно”
- [ ] “реалистично” без критерия
- [ ] “интуитивно” без критерия
- [ ] “лучше” без сравнения
- [ ] “готово” без evidence
- [ ] “реализовано” без evidence

---

## 15. Architecture viewpoints checks

Проверить `03_ARCHITECTURE_VIEWPOINTS.md`.

Минимально должны быть:

- [ ] stakeholders
- [ ] concerns
- [ ] viewpoint catalog
- [ ] VP-01 Runtime Truth
- [ ] VP-02 Machine Body
- [ ] VP-03 Geometry / Mounting
- [ ] VP-04 Mass / CoM / Inertia
- [ ] VP-05 Power / Thermal
- [ ] VP-06 Motion / RCS
- [ ] VP-07 Sensor / Communication
- [ ] VP-08 Modularity / Module Passport
- [ ] VP-09 Command Safety
- [ ] VP-10 Operator Evidence
- [ ] VP-11 Repository Governance
- [ ] VP-12 Engineering Rationale
- [ ] traceability matrix
- [ ] status handling

Проверить, что viewpoints не заявляют runtime implementation.

---

## 16. Calculation frame checks

Проверить `04_CALCULATION_FRAME.md`.

Минимально должны быть:

- [ ] общие правила расчёта
- [ ] базовые единицы
- [ ] координатная система
- [ ] статусы расчётных элементов
- [ ] Face Map skeleton
- [ ] Mount Compatibility Matrix
- [ ] Mass / CoM / Inertia Sheet
- [ ] Power Budget Sheet
- [ ] Thermal Budget Sheet
- [ ] Thrust Map target
- [ ] Torque Map target
- [ ] Bayonet Bridge Sheet
- [ ] Module Passport Template
- [ ] NBL Emergency Packet Rules
- [ ] Command Gating Matrix
- [ ] ORION Evidence Checklist
- [ ] Open calculation-required list

Проверить, что нет invented numbers.

Проверить, что карты Thrust / Torque не объявлены рассчитанными.

---

## 17. Engineering rationale checks

Проверить `05_ENGINEERING_RATIONALE.md`.

Минимально должны быть объяснены:

- [ ] QIKI as machine body
- [ ] battery / supercap split
- [ ] RTG not boost-source
- [ ] reactor external / station / sled
- [ ] NBL emergency low-rate
- [ ] protection not absolute shield
- [ ] field drive not baseline
- [ ] bayonet hard lock required
- [ ] RCS requires maps
- [ ] module passport mandatory
- [ ] ACK is not effect confirmation
- [ ] ORION evidence station
- [ ] first patch documentation-only
- [ ] forbidden wording table
- [ ] связь с ADR

Проверить, что rationale не добавляет новые runtime-фичи.

---

## 18. Interface control checks

Проверить `06_INTERFACE_CONTROL.md`.

Минимально должны быть:

- [ ] общие правила interface control
- [ ] минимальный interface record
- [ ] статусы интерфейса
- [ ] типы блокировок
- [ ] interface catalog
- [ ] IF-BAYONET-MECH-001
- [ ] IF-BAYONET-BRIDGE-001
- [ ] IF-MODULE-PASSPORT-001
- [ ] IF-PDU-POWER-001
- [ ] IF-POWER-TELEM-001
- [ ] IF-THERMAL-TELEM-001
- [ ] IF-RCS-CMD-001
- [ ] IF-SENSOR-TELEM-001
- [ ] IF-COMMS-001
- [ ] IF-NBL-001
- [ ] IF-CMD-BUS-001
- [ ] IF-ORION-EVIDENCE-001
- [ ] IF-AUDIT-001
- [ ] IF-BLACKBOX-001
- [ ] IF-SAFE-001
- [ ] cross-interface rules

Проверить, что interface control не меняет реальные протоколы.

---

## 19. Implementation bridge checks

Проверить `08_IMPLEMENTATION_BRIDGE.md`.

Минимально должны быть:

- [ ] recommended path
- [ ] final tree
- [ ] primary source files vs derived file
- [ ] роль каждого файла
- [ ] связь со старым GDD
- [ ] old GDD alignment note
- [ ] documentation-only boundary
- [ ] agent rules
- [ ] order of documentation patch
- [ ] forbidden patch signs
- [ ] minimal acceptance gates
- [ ] first runtime-slice after docs
- [ ] связь с acceptance checks

Проверить, что bridge не внедряет runtime.

---

## 20. Reader manual checks

Проверить `10_READER_MANUAL.md`.

Он должен быть помечен как:

`derived`

Он должен быть readable consolidated version.

Он не должен заменять primary source files.

Он не должен содержать новые правила, которых нет в source files.

Он не должен объявлять implemented.

Он не должен содержать runtime conformance claims.

Если есть конфликт с source files, source files имеют приоритет.

---

## 21. Package-level acceptance result

Пакет может получить один из статусов.

### 21.1. `PASS`

Все обязательные файлы есть.

Runtime-diff отсутствует.

Implemented / verified claims отсутствуют или имеют evidence.

TBD не заменены выдуманными значениями.

ADR set присутствует.

Reader manual помечен как derived.

Documentation-only boundary соблюдён.

### 21.2. `PASS_WITH_NOTES`

Пакет структурно корректен, но есть мелкие редакционные замечания:

неполные cross-links;

стилистические расхождения;

некритичные повторы;

недостаточно ясные формулировки.

Runtime boundary не нарушен.

### 21.3. `FAIL`

Есть одно или несколько нарушений:

runtime changes в первом patch;

implemented без evidence;

verified без verification;

invented values вместо TBD;

missing primary files;

missing ADR set;

reader manual стал source of truth;

old GDD удалён;

новые технологии добавлены без ADR;

documentation-only boundary нарушен.

---

## 22. Minimal final checklist

Перед тем как считать пакет готовым, отметить:

- [ ] `00_INDEX.md` создан.
- [ ] `01_BODY_CANON.md` создан.
- [ ] `02_REQUIREMENTS.md` создан.
- [ ] `03_ARCHITECTURE_VIEWPOINTS.md` создан.
- [ ] `04_CALCULATION_FRAME.md` создан.
- [ ] `05_ENGINEERING_RATIONALE.md` создан.
- [ ] `06_INTERFACE_CONTROL.md` создан.
- [ ] `07_ADR/` создан.
- [ ] `08_IMPLEMENTATION_BRIDGE.md` создан.
- [ ] `09_ACCEPTANCE_CHECKS.md` создан.
- [ ] `10_READER_MANUAL.md` создан.
- [ ] ADR-0001–ADR-0015 присутствуют.
- [ ] Source priority указан.
- [ ] Status legend указан.
- [ ] Documentation-only boundary указан.
- [ ] Old GDD relationship указан.
- [ ] Reader manual marked as derived.
- [ ] No runtime code changes.
- [ ] No proto changes.
- [ ] No NATS changes.
- [ ] No gRPC changes.
- [ ] No telemetry path changes.
- [ ] No ORION UI changes.
- [ ] No MFD changes.
- [ ] No generated file changes.
- [ ] No fake evidence.
- [ ] No implemented without evidence.
- [ ] No verified without verification.
- [ ] No invented numbers.
- [ ] No target-only as runtime-ready.
- [ ] No calculation-required as calculated.

---

## 23. Итоговая формула

Acceptance checks нужны не для бюрократии.

Они нужны, чтобы документация не начала врать.

QIKI Body v0.2.2 может быть сильным каноном.

Но сильный канон не равен реализации.

Пока evidence нет, нельзя писать `implemented`.

Пока verification нет, нельзя писать `verified`.

Пока расчёта нет, нельзя писать число.

Пока runtime не изменён отдельной задачей, нельзя писать conformance.

Первый patch должен быть documentation-only.

Если это правило соблюдено, пакет можно безопасно вносить в репозиторий как target documentation canon.
