# QIKI Body v0.2.2 — Мост внедрения

## 0. Назначение документа

Этот документ объясняет, как внести **QIKI Body v0.2.2 Documentation Package** в репозиторий QIKI_DTMP без разрушения текущей документации, без преждевременного изменения runtime-кода и без ложного статуса `implemented`.

Документ не вводит новый канон тела.

Документ не добавляет новые технологии, модули, лорные расширения или runtime-фичи.

Документ не меняет proto, NATS, gRPC, telemetry paths, ORION UI или MFD.

Документ задаёт порядок документационного внедрения: какие файлы должны быть созданы, куда они должны быть положены, как они должны быть связаны со старым GDD, какие действия агенту разрешены, какие действия запрещены и по каким признакам documentation-only patch можно считать корректным.

Главная формула:

Сначала documentation canon.

Потом repository alignment.

Потом acceptance checks.

Потом отдельная runtime-задача.

Никогда не писать `implemented` без evidence.

---

## 1. Статус документа

Файл:

`08_IMPLEMENTATION_BRIDGE.md`

Версия:

`v0.2.2`

Статус:

`implementation bridge / documentation-only`

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

`06_INTERFACE_CONTROL.md`

`07_ADR/`

`09_ACCEPTANCE_CHECKS.md`

`10_READER_MANUAL.md`

---

## 1.1. Текущий runtime evidence snapshot

Этот документ описывает исходную дисциплину первого documentation-only внедрения QIKI Body v0.2.2. В текущем repo snapshot обнаружен и сохранён отдельный узкий runtime-контур:

`body_structure / module attach lifecycle / ORION evidence projection`.

Его статус:

`implemented / unit-verified narrow runtime seed`.

Он покрывает только attach lifecycle 0001-0008: missing passport, invalid passport, unknown mount, occupied mount, forbidden class, valid registration, ordered `run_attach_pipeline`, audit-backed Evidence Card, no-mutation on rejection and success-only mutation.

Это не меняет главный статус пакета:

`Full QIKI Body runtime compliance: not claimed`.

Это не доказывает PDU, thermal clearance, real module catalog, capability activation, bayonet power/data bridge, full ORION UI, MFD, proto / NATS / gRPC / telemetry integration, RCS physics, Thrust Map, Torque Map, NBL, RTG, reactor or field-drive runtime.

Status source:

`docs/runtime_slices/ATTACH_LIFECYCLE_EVIDENCE.md`

Runtime owner:

`src/qiki/services/q_core_agent/core/body_structure.py`

Current attach lifecycle entrypoint:

`run_attach_pipeline()`

Legacy Slice 0001 helper:

`attach_module()`

API boundary constants:

`CURRENT_ATTACH_LIFECYCLE_ENTRYPOINT == "run_attach_pipeline"`

`LEGACY_ATTACH_LIFECYCLE_HELPER == "attach_module"`

Agent rule:

Do not re-implement slices 0002-0008 blindly. First read `ATTACH_LIFECYCLE_EVIDENCE.md` and preserve the existing targeted tests. A shaped passport returning `MODULE_ATTACH_NOT_IMPLEMENTED` from legacy `attach_module()` is not evidence that the current lifecycle is missing; use `run_attach_pipeline()` for the full attach lifecycle seed.

---

## 2. Что именно внедряется

Внедряется документационный пакет:

`QIKI Body v0.2.2 Documentation Package`

Финальный состав пакета:

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

`10_READER_MANUAL.md`

Этот набор является documentation package.

Он не является runtime implementation.

Он не утверждает, что текущий код уже соответствует QIKI Body v0.2.2.

---

## 3. Рекомендуемый путь пакета

Рекомендуемый путь:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/`

Причина выбора версионной папки:

пакет является самостоятельным;

версия v0.2.2 не смешивается с будущими версиями;

агент получает один корневой путь;

review становится проще;

documentation-only patch можно проверить по одной директории;

reader manual, ADR, requirements и acceptance checks живут рядом, но не смешиваются.

Допустимая альтернатива:

`docs/design/hardware_and_physics/`

Но для v0.2.2 предпочтительнее версионная подпапка.

---

## 4. Финальное дерево файлов

Целевое дерево:

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

Это дерево является structural target для первого documentation-only patch.

---

## 5. Primary source files и derived file

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

Правило:

source files first;

reader manual second.

Если `10_READER_MANUAL.md` конфликтует с primary source files, приоритет имеют primary source files.

---

## 6. Роль каждого файла при внедрении

### 6.1. `00_INDEX.md`

Входной файл пакета.

Должен объяснять:

что это за пакет;

какая версия;

какой статус;

что входит в пакет;

что является source;

что является derived;

что `canon ≠ implemented`;

что `target-only ≠ runtime-ready`;

какие действия запрещены первому patch.

### 6.2. `01_BODY_CANON.md`

Основной канон тела QIKI.

Должен быть главным источником аппаратной логики тела.

Не должен содержать полные requirement cards, расчётные таблицы, interface records или patch procedure.

### 6.3. `02_REQUIREMENTS.md`

Реестр требований.

Должен превращать канон в `REQ-*` требования со статусами, rationale, verification method и evidence status.

Не должен утверждать implemented без evidence.

### 6.4. `03_ARCHITECTURE_VIEWPOINTS.md`

Архитектурная карта.

Должен показывать stakeholders, concerns, viewpoints, models и traceability.

### 6.5. `04_CALCULATION_FRAME.md`

Расчётный каркас.

Должен содержать target tables и templates.

Не должен выдавать TBD за рассчитанные значения.

### 6.6. `05_ENGINEERING_RATIONALE.md`

Инженерное обоснование.

Должен объяснять, почему приняты жёсткие запреты и почему мягкие формулировки считаются опасными.

### 6.7. `06_INTERFACE_CONTROL.md`

Управление интерфейсами.

Должен описывать target interface records, states, fields, reason_codes и evidence expectations.

Не должен менять реальные протоколы.

### 6.8. `07_ADR/`

Architecture Decision Records.

Должен фиксировать архитектурные решения, которые нельзя молча откатывать.

### 6.9. `08_IMPLEMENTATION_BRIDGE.md`

Этот документ.

Должен задавать порядок внедрения пакета в репозиторий.

### 6.10. `09_ACCEPTANCE_CHECKS.md`

Чеклист приёмки.

Должен проверять, что пакет корректно собран, не врёт о runtime и не нарушает documentation-only boundary.

### 6.11. `10_READER_MANUAL.md`

Производная читательская сборка.

Должна быть помечена как derived.

Не должна становиться главным source of truth.

---

## 7. Связь со старым GDD

Старые QIKI GDD-файлы не должны удаляться первым documentation-only patch.

Старый GDD сохраняется как:

game-design context;

historical layer;

source of earlier ideas;

material for traceability.

Но по вопросам тела, аппаратной физики, энергетики, тепла, RCS, байонетов, NBL, защиты, модульности, command gating и доказательности приоритет имеет QIKI Body v0.2.2.

Критичные superseded-зоны старого GDD:

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

ORION как декоративный HUD.

---

## 8. Рекомендуемая alignment note для старого GDD

В начало старого GDD или рядом с ним можно добавить предупреждение:

```md
> Alignment note — QIKI Body v0.2.2
>
> QIKI Body v0.2.2 is the current target documentation canon for body hardware / physics / machine-body constraints.
>
> This older GDD file remains available as game-design and historical context.
>
> Hardware, body, power, thermal, RCS, bayonet, NBL, protection, modularity, command gating and evidence claims should be checked against:
>
> `docs/design/hardware_and_physics/qiki_body_v0_2_2/`
>
> Older conflicting statements should be treated as superseded by QIKI Body v0.2.2 unless explicitly re-accepted by a later ADR.
```

Эта note не удаляет старый GDD.

Она меняет его статус.

---

## 9. Индексы документации

При documentation-only patch допустимо обновить документационные индексы.

Допустимые изменения:

добавить ссылку на `docs/design/hardware_and_physics/qiki_body_v0_2_2/00_INDEX.md`;

добавить краткое описание пакета;

указать, что пакет является target documentation canon;

указать, что runtime conformance не заявляется;

указать, что первый patch documentation-only.

Нельзя:

объявлять весь runtime соответствующим QIKI Body v0.2.2;

писать, что ORION уже реализует evidence station, если evidence нет;

писать, что telemetry уже поддерживает все поля, если evidence нет;

писать, что command gating уже соответствует матрице, если evidence нет.

---

## 10. Связь с bot_source_of_truth

Если в репозитории существует `bot_source_of_truth.md` или аналогичный документ, туда можно добавить секцию:

`QIKI Body v0.2.2 alignment`

Эта секция должна говорить:

QIKI Body v0.2.2 является target documentation canon для body hardware / physics;

существующие runtime-числа не переписываются этим патчем;

новые требования имеют статус target / documentation-only, если evidence отсутствует;

future runtime work must be tracked separately.

Нельзя:

переписывать runtime truth без проверки;

подменять текущие telemetry values target-таблицами;

объявлять новый канон implemented;

удалять старые runtime факты, если они являются evidence.

---

## 11. Documentation-only boundary

Первое внесение пакета должно быть documentation-only.

### 11.1. Разрешено

Создавать markdown files.

Создавать ADR markdown files.

Создавать local package index.

Обновлять documentation indexes.

Добавлять old GDD alignment note.

Помечать старые конфликтующие statements как superseded.

Добавлять acceptance checklist.

Добавлять documentation-only review notes.

Добавлять TODO / TBD / target-only / calculation-required.

### 11.2. Запрещено

Менять runtime code.

Менять simulation code.

Менять ORION UI.

Менять MFD.

Менять proto.

Менять NATS subjects.

Менять gRPC contracts.

Менять telemetry paths.

Менять generated files.

Добавлять tests that imply runtime conformance.

Добавлять fake evidence.

Писать implemented claims без evidence.

Писать verified claims без verification.

Удалять старый GDD.

Вносить новые технологии или модули в рамках patch.

---

## 12. Агентные правила

Агент, работающий с этим пакетом, должен соблюдать следующие правила.

Не добавлять новые технологии, модули, лорные расширения или runtime-фичи.

Не объявлять `implemented`, если evidence не предоставлено явно.

Не объявлять `verified`, если нет verification.

Не смешивать `canon`, `target-only`, `template-only`, `rules-only`, `calculation-required`, `implemented`, `verified`.

Не патчить code, proto, NATS, gRPC, telemetry paths, ORION UI или MFD.

Не превращать reader manual prose в runtime claims.

Не считать старый GDD более приоритетным по вопросам body hardware / physics.

Не заполнять TBD выдуманными значениями.

Не выводить расчётные числа без расчёта.

Не создавать параллельный канон.

Не изменять ADR задним числом так, будто решение всегда было другим.

---

## 13. Порядок выполнения documentation-only patch

Рекомендуемый порядок:

1. Создать директорию:

`docs/design/hardware_and_physics/qiki_body_v0_2_2/`

2. Добавить `00_INDEX.md`.

3. Добавить `01_BODY_CANON.md`.

4. Добавить `02_REQUIREMENTS.md`.

5. Добавить `03_ARCHITECTURE_VIEWPOINTS.md`.

6. Добавить `04_CALCULATION_FRAME.md`.

7. Добавить `05_ENGINEERING_RATIONALE.md`.

8. Добавить `06_INTERFACE_CONTROL.md`.

9. Добавить `07_ADR/` с начальным набором ADR.

10. Добавить `08_IMPLEMENTATION_BRIDGE.md`.

11. Добавить `09_ACCEPTANCE_CHECKS.md`.

12. Добавить `10_READER_MANUAL.md` как derived file.

13. Обновить documentation index, если он есть.

14. Добавить alignment note к старому GDD, если применимо.

15. Запустить documentation acceptance checks.

16. Проверить, что runtime diff отсутствует.

---

## 14. Запрещённые признаки плохого patch

Patch считается неправильным, если он:

меняет runtime-код;

меняет simulation-код;

меняет proto;

меняет NATS subjects;

меняет gRPC contracts;

меняет telemetry paths;

меняет ORION UI;

меняет MFD;

меняет generated files;

создаёт тесты, которые заявляют runtime-conformance;

пишет `implemented` без evidence;

пишет `verified` без verification;

заменяет TBD выдуманными числами;

переносит Terta-exotic в baseline без ADR;

удаляет старый GDD;

делает reader manual главным source of truth;

создаёт второй body canon;

обходит ADR для изменения решений.

---

## 15. Минимальные acceptance gates перед merge

Перед merge нужно проверить:

все expected files существуют;

`07_ADR/` содержит начальный набор ADR-0001–ADR-0015;

`10_READER_MANUAL.md` помечен как derived;

`00_INDEX.md` содержит source priority;

`01_BODY_CANON.md` не содержит runtime implementation claims;

`02_REQUIREMENTS.md` не использует implemented без evidence;

`04_CALCULATION_FRAME.md` не содержит invented numbers;

`06_INTERFACE_CONTROL.md` не меняет реальные протоколы;

`08_IMPLEMENTATION_BRIDGE.md` фиксирует documentation-only boundary;

`09_ACCEPTANCE_CHECKS.md` содержит проверки no-runtime-diff;

старый GDD получает alignment note или связанную пометку;

package path соответствует плану;

runtime diff отсутствует.

Подробный чеклист должен быть в `09_ACCEPTANCE_CHECKS.md`.

---

## 16. Первый runtime-slice после документации

Первый runtime-slice не входит в этот documentation-only patch.

После принятия документационного пакета можно поставить отдельную задачу на минимальную runtime-реализацию.

Минимальный кандидат на первый runtime-slice:

machine-readable status registry;

Face Map skeleton;

module passport template schema;

basic body_config snapshot;

battery / supercap separation in telemetry;

basic thermal node status;

command lifecycle labels;

ORION evidence placeholders.

Но это должна быть отдельная задача.

Она должна иметь отдельный scope, отдельные tests и отдельное evidence.

Нельзя делать вид, что documentation-only patch уже реализовал runtime-slice.

---

## 17. Связь с acceptance checks

`09_ACCEPTANCE_CHECKS.md` должен проверять этот документ и весь пакет.

Минимальные проверки:

package tree exists;

source priority is declared;

documentation-only boundary is present;

old GDD relationship is clear;

ADR set exists;

no implemented without evidence;

no verified without verification;

no runtime files changed;

no generated files changed;

no telemetry path claims;

no proto / NATS / gRPC changes;

TBD remains TBD;

calculation-required remains calculation-required;

reader manual is derived.

---

## 18. Итоговая формула

`08_IMPLEMENTATION_BRIDGE.md` не внедряет runtime.

Он внедряет порядок.

Он говорит, как положить QIKI Body v0.2.2 в репозиторий так, чтобы документация не начала врать о реализации.

Сначала пакет.

Потом ссылки.

Потом acceptance checks.

Потом отдельная runtime-задача.

Если evidence нет, нельзя писать `implemented`.

Если verification нет, нельзя писать `verified`.

Если patch меняет runtime, это уже не первый documentation-only patch.

Если документ создаёт новую физику, он нарушает роль моста внедрения.

Этот мост должен удержать границу между каноном и реализацией.
