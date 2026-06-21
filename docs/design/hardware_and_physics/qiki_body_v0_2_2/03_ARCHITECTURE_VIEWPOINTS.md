# QIKI Body v0.2.2 — Архитектурные точки зрения

## 0. Назначение документа

Этот документ фиксирует архитектурные точки зрения для пакета **QIKI Body v0.2.2**.

Документ нужен для того, чтобы QIKI Body не существовала только как линейный справочник или набор глав. Линейный текст удобен для чтения, но архитектура должна позволять смотреть на тело QIKI с разных сторон: через runtime truth, геометрию, массу, питание, тепло, движение, сенсоры, связь, модули, команды, SAFE, ORION Evidence, audit, blackbox и репозиторное внедрение.

Этот документ не вводит новый канон тела.

Этот документ не добавляет новые модули, технологии, лорные расширения или runtime-фичи.

Этот документ не утверждает, что текущий runtime уже реализует описанные viewpoints.

Главная задача документа:

связать stakeholders, concerns, viewpoints, models, requirements, evidence и source files в единую архитектурную карту.

---

## 1. Статус документа

Файл:

`03_ARCHITECTURE_VIEWPOINTS.md`

Версия:

`v0.2.2`

Статус:

`target architecture description / documentation-only`

Runtime conformance:

`not claimed`

Primary source:

`01_BODY_CANON.md`

Related source files:

`00_INDEX.md`

`02_REQUIREMENTS.md`

`04_CALCULATION_FRAME.md`

`05_ENGINEERING_RATIONALE.md`

`06_INTERFACE_CONTROL.md`

`07_ADR/`

`08_IMPLEMENTATION_BRIDGE.md`

`09_ACCEPTANCE_CHECKS.md`

`10_READER_MANUAL.md`

---

## 2. Основные термины

### 2.1. Stakeholder

Stakeholder — участник, роль или контур проекта, у которого есть интерес к архитектуре QIKI Body.

Stakeholder не обязательно является человеком. Это может быть роль: runtime engineer, ORION UI designer, documentation agent, QA reviewer, simulation engineer, operator / player.

### 2.2. Concern

Concern — вопрос, риск или область контроля, важная для stakeholder.

Примеры concerns:

что является фактом;

какой источник данных подтверждает состояние;

почему команда отклонена;

какой модуль действительно установлен;

почему QIKI не может выполнить boost;

какой сенсор stale;

почему NBL не является обычной связью;

где target-only;

где implemented;

где evidence.

### 2.3. Viewpoint

Viewpoint — правило построения архитектурного взгляда.

Viewpoint определяет:

какие concerns покрываются;

какие stakeholders заинтересованы;

какие models нужны;

какие source files участвуют;

какие requirements трассируются;

какие evidence нужны;

какие статусы допустимы.

### 2.4. View

View — конкретное представление, построенное по viewpoint.

Например, viewpoint `Power & Thermal` требует смотреть на Power Budget, Thermal Budget, PDU state, SoC_bat, SoC_cap и thermal nodes.

Конкретный view — это уже заполненный power / thermal snapshot или таблица для конкретной конфигурации QIKI.

### 2.5. Model

Model — таблица, матрица, state machine, checklist, schema, snapshot или diagram, через которые viewpoint становится проверяемым.

В QIKI Body v0.2.2 model может иметь статус:

`target-only`;

`template-only`;

`rules-only`;

`calculation-required`;

`implemented`;

`verified`.

`implemented` и `verified` запрещены без evidence.

---

## 3. Stakeholders

### 3.1. Project owner

Главный интерес:

сохранить целостность QIKI;

не распылить тело QIKI на фантазийные фичи;

не смешать канон, расчёт и реализацию;

удержать стратегическую линию проекта.

Ключевые concerns:

source priority;

documentation-only boundary;

no implemented without evidence;

неразмытие QIKI как машинного тела.

### 3.2. Game designer

Главный интерес:

получить игровую глубину без RPG-магазина апгрейдов.

Ключевые concerns:

модульность как смена цены;

миссионные профили;

запрет конфигураций “лучше во всём”;

физические ограничения как источник решений.

### 3.3. Systems designer

Главный интерес:

связать тело, энергию, тепло, движение, сенсоры, связь, модули, команды и SAFE в единую систему.

Ключевые concerns:

единая причинность тела;

state transitions;

ограничения между подсистемами;

reason_codes;

непротиворечивость статусов.

### 3.4. Runtime engineer

Главный интерес:

понять, какие поля и состояния должны стать machine-readable в будущих runtime-задачах.

Ключевые concerns:

не внедрить target-only как implemented;

не выдумать telemetry paths;

не менять proto / NATS / gRPC в documentation-only patch;

получить минимальный будущий runtime-slice.

### 3.5. Simulation engineer

Главный интерес:

понять, какие модели нужны для тела.

Ключевые concerns:

Face Map;

Mass / CoM / Inertia Sheet;

Power Budget;

Thermal Budget;

Thrust Map;

Torque Map;

bayonet state;

module effects.

### 3.6. ORION UI designer

Главный интерес:

понять, что оператор должен видеть.

Ключевые concerns:

ORION как evidence station;

source / freshness / trust;

reason_codes;

missing / stale / conflicting;

target-only / not implemented;

ACK vs effect confirmation;

audit trail.

### 3.7. AI / agent engineer

Главный интерес:

понять, как агент должен читать канон и где ему запрещено действовать.

Ключевые concerns:

не добавлять новые фичи во время сборки пакета;

не писать implemented без evidence;

не патчить runtime;

не превращать reader manual prose в runtime claims;

сохранять source priority.

### 3.8. Documentation agent

Главный интерес:

собрать пакет файлов без смешения типов документации.

Ключевые concerns:

01_BODY_CANON как основной канон;

02_REQUIREMENTS как требования;

03_ARCHITECTURE_VIEWPOINTS как viewpoints;

04_CALCULATION_FRAME как таблицы;

05_ENGINEERING_RATIONALE как rationale;

06_INTERFACE_CONTROL как interfaces;

07_ADR как решения;

10_READER_MANUAL как derived file.

### 3.9. QA / reviewer

Главный интерес:

проверить, что документация не врёт о runtime.

Ключевые concerns:

наличие всех файлов;

нет implemented без evidence;

нет verified без verification;

TBD не заменены выдуманными числами;

target-only не подан как runtime-ready;

старый GDD правильно помечен;

ADR присутствуют.

### 3.10. Operator / player

Главный интерес:

понимать, что QIKI может сейчас и почему.

Ключевые concerns:

почему команда запрещена;

что перегрето;

какой модуль мешает;

какой сенсор недостоверен;

какое состояние SAFE;

какой источник данных;

что подтверждено, а что только гипотеза.

### 3.11. Lore writer

Главный интерес:

писать фантастическую часть так, чтобы она не ломала физический канон.

Ключевые concerns:

Terta-exotic marking;

NBL не как wideband;

field drive не как baseline;

защита не как absolute shield;

реактор не как обычный модуль;

экзотика должна иметь цену.

---

## 4. Master concerns

### 4.1. Truth concerns

Что является фактом?

Что является гипотезой?

Где source?

Где telemetry?

Где ACK?

Где effect confirmation?

Где audit?

Где blackbox?

Где missing?

Где stale?

Где local reconstruction?

### 4.2. Body concerns

Где находится модуль?

Какая грань занята?

Какая масса добавлена?

Как изменился CoM?

Как изменилась inertia?

Какие команды теперь запрещены?

Что должно увидеть ORION?

### 4.3. Power / thermal concerns

Почему есть заряд батареи, но нет права на пик?

Почему SoC_bat не равен SoC_cap?

Какой thermal node блокирует команду?

Что делает PDU?

Что отключает SAFE?

Почему boost запрещён?

### 4.4. Motion concerns

Какая тяга доступна?

Какая ось degraded?

Есть ли Thrust Map?

Есть ли Torque Map?

Почему balanced thrust не подтверждён?

Почему manual RCS override не baseline?

Как CoM влияет на манёвр?

### 4.5. Sensor / comms concerns

Какой сенсор trusted?

Какой sensor stale?

Где conflict?

Какой канал связи активен?

Что ограничено EMCON?

Почему NBL не передаёт bulk telemetry?

Что является observation, а что hypothesis?

### 4.6. Module concerns

Есть ли module passport?

Валидирован ли passport?

Какая совместимость с mount point?

Что модуль даёт?

Что модуль забирает?

Какие команды он добавляет?

Какие команды он блокирует?

Какие failure modes?

### 4.7. Command safety concerns

Где request?

Где validation?

Почему allowed?

Почему rejected?

Где publish?

Где ACK?

Где effect confirmation?

Где audit?

Что значит timeout?

Что значит partial effect?

### 4.8. Operator evidence concerns

Что ORION должен показать?

Что нельзя скрывать?

Где reason_code?

Где source?

Где target-only?

Где not implemented?

Где calculation-required?

Где stale?

Где missing?

### 4.9. Repository governance concerns

Где лежит пакет?

Как он связан со старым GDD?

Какие файлы primary?

Какой файл derived?

Что запрещено первому patch?

Что считается acceptance evidence?

---

## 5. Viewpoint catalog

Минимальный каталог viewpoints QIKI Body v0.2.2:

VP-01 Runtime Truth Viewpoint.

VP-02 Machine Body Viewpoint.

VP-03 Geometry / Mounting Viewpoint.

VP-04 Mass / CoM / Inertia Viewpoint.

VP-05 Power / Thermal Viewpoint.

VP-06 Motion / RCS Viewpoint.

VP-07 Sensor / Communication Viewpoint.

VP-08 Modularity / Module Passport Viewpoint.

VP-09 Command Safety Viewpoint.

VP-10 Operator Evidence Viewpoint.

VP-11 Repository Governance Viewpoint.

VP-12 Engineering Rationale Viewpoint.

---

## 6. VP-01 Runtime Truth Viewpoint

### Purpose

Проверять, что физическая истина о QIKI не подменяется текстом, голосом модели или интерфейсом.

### Stakeholders

Project owner;

systems designer;

runtime engineer;

ORION UI designer;

AI / agent engineer;

QA / reviewer;

operator / player.

### Concerns

Что является фактом?

Где source?

Где telemetry?

Где ACK?

Где effect confirmation?

Где audit?

Где blackbox?

Где missing / stale / hypothesis?

### Models

Runtime state snapshot;

telemetry snapshot;

event log;

ACK record;

effect confirmation record;

audit entry;

blackbox record;

ORION evidence card.

### Related requirements

REQ-BODY-*;

REQ-AUDIT-*;

REQ-ORION-*;

REQ-CMD-*.

### Related source files

`01_BODY_CANON.md`;

`02_REQUIREMENTS.md`;

`06_INTERFACE_CONTROL.md`;

`09_ACCEPTANCE_CHECKS.md`.

### Evidence expectations

Физическое утверждение должно иметь source или быть явно помечено как missing / unknown / hypothesis / local reconstruction / target-only / not implemented.

---

## 7. VP-02 Machine Body Viewpoint

### Purpose

Проверять, что QIKI рассматривается как машинное тело, а не как персонаж, ассистент или декоративный интерфейс.

### Stakeholders

Project owner;

game designer;

systems designer;

simulation engineer;

AI / agent engineer;

lore writer.

### Concerns

QIKI сохраняет идентичность?

Модульность не создаёт нового робота?

Каждая возможность имеет цену?

Форма, масса, энергия и тепло имеют значение?

### Models

Body configuration snapshot;

body state model;

mission profile map;

capability / cost map;

status model.

### Related requirements

REQ-BODY-*;

REQ-MODULE-*;

REQ-SAFE-*.

### Related source files

`01_BODY_CANON.md`;

`02_REQUIREMENTS.md`;

`05_ENGINEERING_RATIONALE.md`;

`07_ADR/`.

### Evidence expectations

Любое утверждение о действующем теле должно быть связано с конфигурацией, состоянием или явным target-only статусом.

---

## 8. VP-03 Geometry / Mounting Viewpoint

### Purpose

Проверять геометрию тела, грани, mount points и запрет произвольной установки модулей.

### Stakeholders

Simulation engineer;

runtime engineer;

systems designer;

ORION UI designer;

QA / reviewer.

### Concerns

Какая грань занята?

Где face_id?

Где face normal?

Что можно ставить?

Что запрещено ставить?

Какие конфликты?

Какие данные TBD?

### Models

Face Map;

mount compatibility table;

module occupancy map;

geometry status table;

ORION face view.

### Related requirements

REQ-GEOM-*;

REQ-MODULE-*;

REQ-ORION-*.

### Related source files

`01_BODY_CANON.md`;

`04_CALCULATION_FRAME.md`;

`06_INTERFACE_CONTROL.md`.

### Evidence expectations

Модуль не может считаться установленным без mount point или bayonet / internal / external attachment status.

---

## 9. VP-04 Mass / CoM / Inertia Viewpoint

### Purpose

Проверять, что QIKI управляется как физическое тело, а не как точка.

### Stakeholders

Simulation engineer;

runtime engineer;

systems designer;

ORION UI designer;

QA / reviewer.

### Concerns

Какая масса тела?

Как модуль меняет массу?

Где CoM?

Как изменился CoM_delta?

Как изменилась inertia?

Какие манёвры запрещены?

### Models

Mass / CoM / Inertia Sheet;

module mass entries;

CoM_delta classes;

inertia classes;

maneuver restriction table.

### Related requirements

REQ-MASS-*;

REQ-RCS-*;

REQ-MODULE-*;

REQ-CMD-*.

### Related source files

`01_BODY_CANON.md`;

`04_CALCULATION_FRAME.md`;

`06_INTERFACE_CONTROL.md`.

### Evidence expectations

Тяжёлый модуль не должен считаться безопасным без CoM / inertia impact или статуса calculation-required.

---

## 10. VP-05 Power / Thermal Viewpoint

### Purpose

Проверять энергетические и тепловые ограничения тела QIKI.

### Stakeholders

Systems designer;

runtime engineer;

simulation engineer;

ORION UI designer;

operator / player;

QA / reviewer.

### Concerns

Почему SoC_bat не равен SoC_cap?

Почему заряд батареи не даёт право на boost?

Какой thermal node горячий?

Что делает PDU?

Что блокирует peak action?

### Models

Power Budget Sheet;

Thermal Budget Sheet;

PDU state table;

battery / supercap telemetry;

thermal node telemetry;

peak consumer table;

load shedding table.

### Related requirements

REQ-POWER-*;

REQ-THERMAL-*;

REQ-CMD-*;

REQ-SAFE-*;

REQ-ORION-*.

### Related source files

`01_BODY_CANON.md`;

`04_CALCULATION_FRAME.md`;

`05_ENGINEERING_RATIONALE.md`;

`06_INTERFACE_CONTROL.md`.

### Evidence expectations

Пиковая команда должна иметь проверку SoC_cap, PDU allowance и thermal clearance.

---

## 11. VP-06 Motion / RCS Viewpoint

### Purpose

Проверять, что движение QIKI не объявляется доказанным без RCS-геометрии, Thrust Map и Torque Map.

### Stakeholders

Simulation engineer;

runtime engineer;

systems designer;

ORION UI designer;

QA / reviewer.

### Concerns

Какая тяга доступна?

Какие RCS-кластеры активны?

Есть ли Thrust Map?

Есть ли Torque Map?

Как CoM влияет на burn?

Есть ли plume conflicts?

Почему manual override не baseline?

### Models

RCS cluster map;

Thrust Map;

Torque Map;

plume-clearance table;

working mass table;

burn command matrix;

motion restriction table.

### Related requirements

REQ-RCS-*;

REQ-MASS-*;

REQ-CMD-*;

REQ-ORION-*.

### Related source files

`01_BODY_CANON.md`;

`04_CALCULATION_FRAME.md`;

`05_ENGINEERING_RATIONALE.md`;

`06_INTERFACE_CONTROL.md`.

### Evidence expectations

Нельзя заявлять balanced thrust или full maneuverability без расчётной карты или явного target-only статуса.

---

## 12. VP-07 Sensor / Communication Viewpoint

### Purpose

Проверять, что сенсоры и связь имеют source, freshness, trust, ограничения и цену.

### Stakeholders

Systems designer;

runtime engineer;

ORION UI designer;

operator / player;

QA / reviewer;

lore writer.

### Concerns

Какой сенсор trusted?

Какой stale?

Где conflicting?

Что является observation?

Что является hypothesis?

Какой канал связи активен?

Почему NBL не wideband?

Что ограничивает EMCON?

### Models

Sensor profile table;

sensor trust table;

freshness table;

communication channel table;

NBL emergency packet rules;

EMCON state table.

### Related requirements

REQ-SENSOR-*;

REQ-COMMS-*;

REQ-NBL-*;

REQ-ORION-*;

REQ-CMD-*.

### Related source files

`01_BODY_CANON.md`;

`04_CALCULATION_FRAME.md`;

`05_ENGINEERING_RATIONALE.md`;

`06_INTERFACE_CONTROL.md`.

### Evidence expectations

Сенсорные данные должны иметь source, freshness и trust status. NBL baseline не должен использоваться как bulk telemetry channel.

---

## 13. VP-08 Modularity / Module Passport Viewpoint

### Purpose

Проверять, что модульность является физическим изменением тела, а не магазином бонусов.

### Stakeholders

Game designer;

systems designer;

runtime engineer;

simulation engineer;

ORION UI designer;

QA / reviewer.

### Concerns

Есть ли module passport?

Что модуль даёт?

Что модуль забирает?

Где mount point?

Какие команды добавлены?

Какие команды заблокированы?

Какие failure modes?

Какие reason_codes?

### Models

Module Passport Template;

module compatibility table;

capability / cost map;

blocked commands table;

module failure modes table;

module handshake interface.

### Related requirements

REQ-MODULE-*;

REQ-GEOM-*;

REQ-MASS-*;

REQ-POWER-*;

REQ-THERMAL-*;

REQ-CMD-*.

### Related source files

`01_BODY_CANON.md`;

`04_CALCULATION_FRAME.md`;

`06_INTERFACE_CONTROL.md`;

`07_ADR/`.

### Evidence expectations

Модуль без паспорта не может быть runtime-ready.

---

## 14. VP-09 Command Safety Viewpoint

### Purpose

Проверять, что команды проходят через тело и не превращаются в мгновенный эффект.

### Stakeholders

Systems designer;

runtime engineer;

AI / agent engineer;

ORION UI designer;

operator / player;

QA / reviewer.

### Concerns

Где request?

Где validation?

Почему allowed?

Почему rejected?

Где publish?

Где ACK?

Где effect confirmation?

Где audit?

Что прервал SAFE?

### Models

Command lifecycle state machine;

Command Gating Matrix;

reason_code catalog;

ACK record;

effect confirmation record;

audit entry;

SAFE block table.

### Related requirements

REQ-CMD-*;

REQ-SAFE-*;

REQ-AUDIT-*;

REQ-ORION-*.

### Related source files

`01_BODY_CANON.md`;

`02_REQUIREMENTS.md`;

`04_CALCULATION_FRAME.md`;

`06_INTERFACE_CONTROL.md`;

`09_ACCEPTANCE_CHECKS.md`.

### Evidence expectations

ACK не должен считаться effect confirmation. Command allowed не должен считаться executed.

---

## 15. VP-10 Operator Evidence Viewpoint

### Purpose

Проверять, что ORION показывает доказательства, а не декоративную картину.

### Stakeholders

ORION UI designer;

operator / player;

systems designer;

QA / reviewer;

AI / agent engineer.

### Concerns

Что оператор должен видеть?

Где source?

Где freshness?

Где trust?

Где reason_code?

Где target-only?

Где not implemented?

Где missing?

Где audit trail?

### Models

ORION Evidence Checklist;

evidence card model;

source / freshness / trust display model;

reason_code display table;

target-only / not implemented marking.

### Related requirements

REQ-ORION-*;

REQ-BODY-*;

REQ-SENSOR-*;

REQ-CMD-*;

REQ-AUDIT-*.

### Related source files

`01_BODY_CANON.md`;

`04_CALCULATION_FRAME.md`;

`06_INTERFACE_CONTROL.md`;

`09_ACCEPTANCE_CHECKS.md`.

### Evidence expectations

ORION не должен показывать уверенное состояние без source или явного статуса missing / target-only / not implemented.

---

## 16. VP-11 Repository Governance Viewpoint

### Purpose

Проверять, что документационный пакет внесён в репозиторий без смешения с runtime implementation.

### Stakeholders

Project owner;

documentation agent;

AI / agent engineer;

QA / reviewer;

runtime engineer.

### Concerns

Где лежит пакет?

Какие файлы primary?

Какой файл derived?

Как связан old GDD?

Что запрещено первому patch?

Где acceptance checks?

Где implemented evidence?

### Models

package file tree;

source priority table;

documentation-only boundary checklist;

old GDD alignment note;

acceptance checklist;

ADR index.

### Related requirements

REQ-REPO-*;

REQ-ADR-*.

### Related source files

`00_INDEX.md`;

`08_IMPLEMENTATION_BRIDGE.md`;

`09_ACCEPTANCE_CHECKS.md`;

`07_ADR/`.

### Evidence expectations

Первый patch должен быть documentation-only. Любые runtime changes запрещены в этом шаге.

---

## 17. VP-12 Engineering Rationale Viewpoint

### Purpose

Проверять, что ключевые инженерные запреты имеют rationale и не размягчаются без ADR.

### Stakeholders

Project owner;

systems designer;

game designer;

lore writer;

QA / reviewer;

AI / agent engineer.

### Concerns

Почему RTG не boost-source?

Почему reactor external?

Почему NBL emergency low-rate?

Почему protection not absolute shield?

Почему field drive not baseline?

Почему bayonet hard lock?

Почему RCS needs maps?

Почему module passport mandatory?

### Models

Engineering rationale sections;

ADR records;

forbidden wording list;

accepted replacement wording list.

### Related requirements

REQ-POWER-*;

REQ-NBL-*;

REQ-PROTECT-*;

REQ-FIELD-*;

REQ-BAYONET-*;

REQ-RCS-*;

REQ-MODULE-*.

### Related source files

`05_ENGINEERING_RATIONALE.md`;

`07_ADR/`;

`09_ACCEPTANCE_CHECKS.md`.

### Evidence expectations

Опасная формулировка должна быть заменена корректной или помечена как superseded / rejected / Terta-exotic.

---

## 18. Traceability matrix

Минимальная трассировка:

| Viewpoint | Основные source files | Основные model kinds | Основные requirement namespaces |
|---|---|---|---|
| VP-01 Runtime Truth | `01`, `02`, `06`, `09` | telemetry, ACK, effect, audit, blackbox | REQ-BODY, REQ-AUDIT, REQ-ORION |
| VP-02 Machine Body | `01`, `02`, `05`, `07` | body config, capability/cost map | REQ-BODY, REQ-MODULE |
| VP-03 Geometry / Mounting | `01`, `04`, `06` | Face Map, mount table | REQ-GEOM, REQ-MODULE |
| VP-04 Mass / CoM / Inertia | `01`, `04`, `06` | Mass / CoM / Inertia Sheet | REQ-MASS, REQ-RCS |
| VP-05 Power / Thermal | `01`, `04`, `05`, `06` | Power Budget, Thermal Budget | REQ-POWER, REQ-THERMAL |
| VP-06 Motion / RCS | `01`, `04`, `05`, `06` | Thrust Map, Torque Map | REQ-RCS, REQ-CMD |
| VP-07 Sensor / Communication | `01`, `04`, `05`, `06` | sensor table, comms table, NBL rules | REQ-SENSOR, REQ-COMMS, REQ-NBL |
| VP-08 Modularity / Passport | `01`, `04`, `06`, `07` | Module Passport Template | REQ-MODULE |
| VP-09 Command Safety | `01`, `02`, `04`, `06`, `09` | Command Gating Matrix | REQ-CMD, REQ-SAFE, REQ-AUDIT |
| VP-10 Operator Evidence | `01`, `04`, `06`, `09` | ORION Evidence Checklist | REQ-ORION |
| VP-11 Repository Governance | `00`, `08`, `09`, `07` | package tree, acceptance checklist | REQ-REPO, REQ-ADR |
| VP-12 Engineering Rationale | `05`, `07`, `09` | ADR, forbidden wording table | REQ-POWER, REQ-NBL, REQ-PROTECT, REQ-FIELD |

---

## 19. Status handling

Все viewpoints должны различать:

`canon`;

`target-only`;

`template-only`;

`rules-only`;

`calculation-required`;

`implemented`;

`verified`;

`superseded`;

`rejected`.

Viewpoint не имеет права превращать `target-only` в `implemented`.

Viewpoint не имеет права превращать `template-only` в runtime schema.

Viewpoint не имеет права превращать `calculation-required` в calculated.

Viewpoint не имеет права превращать prose в evidence.

---

## 20. Итоговая формула

Requirements говорят, что должно быть верно.

Viewpoints говорят, с какой стороны это проверять.

Models показывают, какими артефактами это проверяется.

Interfaces показывают, где проходят границы между подсистемами.

ADR объясняет, почему решение принято.

Acceptance checks проверяют, что документация не врёт о runtime.

QIKI Body v0.2.2 должна читаться не только как книга, но и как архитектурная карта.

Если viewpoint отсутствует, архитектура расползается по главам.

Если concern не покрыт, риск остаётся невидимым.

Если model отсутствует, требование остаётся плохо проверяемым.

Если evidence отсутствует, нельзя писать implemented.
