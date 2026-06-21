# QIKI Body v0.2.2 — Индекс документационного пакета

## 0. Назначение пакета

Этот пакет фиксирует **QIKI Body v0.2.2** как целевой документационный канон тела QIKI.

Он описывает QIKI не как персонажа, не как голосовую модель, не как интерфейсную панель и не как произвольную платформу апгрейдов, а как машинное тело: геометрию, массу, центр масс, инерцию, питание, тепловое поведение, движение, сенсоры, связь, защиту, модульность, команды, SAFE, ORION Evidence, audit и blackbox.

Этот пакет является документационным пакетом.

Он не является runtime-реализацией.

Он не утверждает, что текущий runtime уже соответствует QIKI Body v0.2.2.

Главное правило:

Canon не означает implemented.

Target-only не означает runtime-ready.

Template-only не означает, что runtime schema уже существует.

Rules-only не означает, что protocol уже реализован.

Calculation-required не означает, что расчёт уже выполнен.

Implemented требует evidence.

Verified требует evidence и verification.

---

## 1. Статус пакета

Версия:

`v0.2.2`

Статус:

`target canon / documentation package`

Runtime conformance:

`not claimed`

Тип патча:

`documentation-only`

Рекомендуемый путь пакета:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/`

Основная область:

`QIKI machine body, hardware / physics / body systems, evidence and documentation governance`

Вне области этого пакета:

runtime code implementation;

proto changes;

NATS subjects;

gRPC contracts;

telemetry paths;

ORION UI implementation;

MFD logic;

generated files;

tests implying implemented runtime behavior;

fake telemetry;

runtime conformance claims without evidence.

---

## 2. Карта файлов

Пакет содержит следующие файлы.

### 2.1. `00_INDEX.md`

Навигация, статус пакета, приоритет источников, легенда статусов и trust note.

Этот файл является входной точкой для человека и агента.

### 2.2. `01_BODY_CANON.md`

Основной канон тела.

Фиксирует QIKI как машинное тело и задаёт главные законы тела: runtime truth, геометрию, массу, центр масс, инерцию, байонет, RCS, питание, тепловую модель, сенсоры, связь, NBL, защиту, модульность, паспорт модуля, command gating, SAFE, ORION Evidence, audit и blackbox.

### 2.3. `02_REQUIREMENTS.md`

Реестр требований.

Переводит канон тела в трассируемые требования `REQ-*` со статусом, rationale, verification method и evidence status.

### 2.4. `03_ARCHITECTURE_VIEWPOINTS.md`

Архитектурные точки зрения.

Фиксирует stakeholders, concerns, viewpoints, models и трассировку между требованиями и документацией.

### 2.5. `04_CALCULATION_FRAME.md`

Расчётный каркас.

Содержит целевые таблицы и шаблоны для Face Map, Mass / CoM / Inertia, Power Budget, Thermal Budget, Thrust Map, Torque Map, Bayonet Bridge, Module Passport, NBL Emergency Packet Rules, Command Gating Matrix и ORION Evidence Checklist.

### 2.6. `05_ENGINEERING_RATIONALE.md`

Инженерное обоснование.

Объясняет, почему канон отсекает мягкую фантастику: RTG не является boost-source, reactor не является face module, NBL не является wideband comms, protection не является absolute shield, field drive не является baseline, bayonet требует hard lock, RCS требует maps, а module passport является обязательным.

### 2.7. `06_INTERFACE_CONTROL.md`

Управление интерфейсами.

Описывает целевые interface records между подсистемами QIKI: bayonet, PDU, power telemetry, thermal telemetry, RCS commands, sensor telemetry, comms, NBL, command bus, ORION Evidence feed, audit, blackbox и SAFE.

### 2.8. `07_ADR/`

Architecture Decision Records.

Хранит принятые архитектурные решения, которые нельзя молча откатывать или размягчать.

Начальный набор ADR:

`ADR-0001-machine-body-not-model-voice.md`

`ADR-0002-body-canon-separated-from-old-gdd.md`

`ADR-0003-battery-supercap-split.md`

`ADR-0004-rtg-trickle-not-boost.md`

`ADR-0005-reactor-external-source.md`

`ADR-0006-nbl-emergency-low-rate.md`

`ADR-0007-deflector-not-absolute-shield.md`

`ADR-0008-field-drive-not-baseline.md`

`ADR-0009-bayonet-mechanical-hard-lock.md`

`ADR-0010-rcs-thrust-torque-maps-required.md`

`ADR-0011-module-passport-mandatory.md`

`ADR-0012-documentation-only-first-patch.md`

`ADR-0013-reader-manual-derived.md`

`ADR-0014-orion-evidence-station.md`

`ADR-0015-ack-not-effect-confirmation.md`

### 2.9. `08_IMPLEMENTATION_BRIDGE.md`

Мост внедрения.

Объясняет, как этот пакет должен быть внесён в репозиторий без изменения runtime-кода.

### 2.10. `09_ACCEPTANCE_CHECKS.md`

Чеклист приёмки.

Фиксирует проверки наличия файлов, ссылок, статусов, запрещённых формулировок, no-runtime-diff boundary и запрет implemented-claims без evidence.

### 2.11. `10_READER_MANUAL.md`

Производная читательская сборка.

Читаемая цельная версия QIKI Body Reference Manual Part I–X.

Этот файл является derived.

Он не заменяет primary source files.

---

## 3. Приоритет источников

Primary source files:

`00_INDEX.md`

`01_BODY_CANON.md`

`02_REQUIREMENTS.md`

`03_ARCHITECTURE_VIEWPOINTS.md`

`04_CALCULATION_FRAME.md`

`05_ENGINEERING_RATIONALE.md`

`06_INTERFACE_CONTROL.md`

`07_ADR/`

`08_IMPLEMENTATION_BRIDGE.md`

`09_ACCEPTANCE_CHECKS.md`

Derived file:

`10_READER_MANUAL.md`

Если файлы пакета конфликтуют между собой, использовать следующий порядок приоритета для смысла body canon и implementation meaning:

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

`00_INDEX.md` является навигационной и доверительной входной точкой. Он объясняет, как читать пакет, но не заменяет source files.

`10_READER_MANUAL.md` является читаемой сборкой. Он не является высшим source of truth.

Если `10_READER_MANUAL.md` конфликтует с source files, приоритет имеют source files.

---

## 4. Легенда статусов

### 4.1. `canon`

Правило принято как часть QIKI Body v0.2.2 canon.

Canon не означает implemented.

### 4.2. `target-only`

Правило является целевым требованием или целевым проектным утверждением.

Текущий runtime не считается обязанным уже поддерживать это правило.

### 4.3. `template-only`

Пакет задаёт обязательный шаблон, но не утверждает наличие runtime schema или заполненных runtime instances.

### 4.4. `rules-only`

Пакет задаёт правила или политику, но не утверждает, что protocol или runtime enforcement уже существуют.

### 4.5. `calculation-required`

Пакет задаёт область обязательного расчёта.

Точные значения, карты, пороги или матрицы ещё не установлены.

### 4.6. `implemented`

Функция существует в runtime.

Этот статус запрещено использовать без evidence.

### 4.7. `verified`

Функция существует в runtime и прошла принятый метод проверки.

Этот статус запрещено использовать без evidence.

### 4.8. `superseded`

Предыдущее правило, утверждение или фрагмент документа заменены новым решением.

### 4.9. `rejected`

Вариант был рассмотрен и отклонён.

---

## 5. Связь со старым GDD

Старые QIKI GDD-файлы не должны удаляться первым documentation patch.

Старые GDD-файлы сохраняются как game-design и historical context.

По вопросам hardware / body physics этот пакет имеет приоритет над более ранними описаниями тела.

Это включает:

body geometry;

power architecture;

battery / supercap split;

thermal model;

RCS baseline;

Thrust Map and Torque Map requirements;

bayonet hard lock;

NBL limits;

protection limits;

module passport;

command gating;

SAFE;

ORION Evidence;

audit and blackbox.

Старые конфликтующие формулировки должны считаться superseded by QIKI Body v0.2.2, если они явно не переутверждены в более позднем ADR.

Рекомендуемая alignment note для старого GDD:

`QIKI Body v0.2.2 is the current target documentation canon for body hardware / physics / machine-body constraints. This older GDD file remains available as game-design and historical context. Hardware, body, power, thermal, RCS, bayonet, NBL, protection, modularity and evidence claims should be checked against docs/design/hardware_and_physics/qiki_body_v0_2_2/.`

---

## 6. Documentation-only boundary

Первое внесение пакета должно быть documentation-only.

Разрешено:

create markdown files;

create ADR markdown files;

create local package index;

update documentation indexes;

add old GDD alignment note;

mark old conflicting statements as superseded;

add acceptance checklist;

add documentation-only review notes.

Запрещено:

runtime code changes;

simulation code changes;

ORION UI changes;

MFD changes;

proto changes;

NATS subject changes;

gRPC contract changes;

telemetry path changes;

generated file changes;

tests that imply runtime conformance;

fake evidence;

implemented claims without evidence.

---

## 7. Правила для агентов

Агенты, работающие с этим пакетом, должны соблюдать следующие правила.

Не добавлять новые технологии, модули, лорные расширения или runtime-фичи во время сборки документационного пакета.

Не объявлять что-либо implemented, если evidence не предоставлено явно.

Не смешивать canon, target-only, template-only, rules-only, calculation-required, implemented и verified.

Не патчить code, proto, NATS, gRPC, telemetry paths, ORION UI или MFD.

Не превращать prose из reader manual в runtime claims.

Не считать старый GDD более приоритетным, чем QIKI Body v0.2.2, по вопросам body hardware / physics.

Не заполнять TBD-значения выдуманными числами.

Использовать `TBD`, `target-only`, `template-only`, `rules-only` или `calculation-required`, если данных не хватает.

Использовать ADR для архитектурных решений, которые нельзя молча откатывать.

Использовать acceptance checks перед тем, как считать documentation package готовым к внесению в репозиторий.

---

## 8. Trust note

Этот пакет создан для того, чтобы документация не врала о runtime.

Пакет может описывать, чем QIKI Body v0.2.2 должна стать.

Он может задавать целевые законы тела, требования, viewpoints, расчётные таблицы, interface records и ADR decisions.

Он может задавать, как будущая runtime-работа должна проверяться.

Он не должен подразумевать, что текущий runtime уже выполняет эти требования, если evidence явно не предоставлено.

Statement is not implementation.

Table is not calculation.

Template is not schema.

Rule is not enforcement.

ADR is not runtime behavior.

Reader manual is not evidence.

---

## 9. Минимальная приёмка перед внесением в репозиторий

Перед внесением этого пакета в репозиторий нужно проверить, что:

all expected files exist;

`07_ADR/` contains the accepted initial ADR set;

`10_READER_MANUAL.md` is marked as derived;

source priority is clear;

status legend is present;

documentation-only boundary is present;

old GDD relationship is clear;

no file claims runtime conformance without evidence;

no file uses implemented or verified without evidence;

TBD values are not replaced by invented numbers;

target-only statements are not presented as runtime-ready;

calculation-required items are not presented as calculated;

no runtime, proto, NATS, gRPC, telemetry, ORION or MFD changes are included in the first package patch.

Подробные проверки определены в `09_ACCEPTANCE_CHECKS.md`.

---

## 10. Следующий документ

Следующий документ пакета:

`01_BODY_CANON.md`

Он должен быть собран как основной чистовой канон тела.

Он не должен включать полные requirement cards, полные расчётные таблицы, полные interface records, полный ADR rationale или процедуру repository patch.

Эти материалы должны находиться в отдельных файлах.
