---
id: BR-01
version: re1
status: rebuilt-from-archive
owner: Макс
updated: 2026-03-23
canonical-layer: runtime-core
related:
  - BR-02
  - BR-03
  - BR-04
  - BR-05
  - RE_QIKI_Architecture_Verification_Note.md
  - RE_QIKI_Maturity_Matrix.md
  - RE_QIKI_Runtime_Evidence_Notes.md
  - RE_QIKI_Risks_and_Unresolved_Zones.md
---

# RE BR-01 — Паспорт ветки «Кодовая истина проекта»

## 1. Назначение

Этот документ фиксирует только то, что действительно подтверждается архивом проекта на уровне кода, конфигураций, compose-слоя, контрактов и тестовых поверхностей.

Его задача — не объявить окончательный канон проекта, а отделить:

- **факт кода**;
- **аналитический вывод из кода**;
- **проектное решение более высокого уровня**, которое уже не выводится из репозитория автоматически.

Главное правило ветки BR-01:

**если формулировка не удерживается кодом, контрактами, конфигами или реальной структурой архива, она не считается кодовой истиной.**

---

## 2. Краткий вердикт

Архив подтверждает, что QIKI — это не пустая концепция и не один изолированный сервис, а многослойная система с реальным runtime-spine:

- симуляционный контур (`q_sim_service` + `WorldModel`);
- общий слой контрактов и subject-ов (`shared/*`, `protos/*`, `schemas/*`);
- транспортно-событийный слой (`NATS / FastStream / JetStream`);
- операторская поверхность (`operator_console`, ORION V);
- отдельный BIOS-support слой (`q_bios_service`);
- audit-слой (`registrar`);
- агентный / proposal / intent слой (`q_core_agent`, `qiki_chat`, `faststream_bridge`).

Но архив **не подтверждает**, что этот репозиторий уже очищен до одного бесспорного центра. Наоборот, в коде одновременно видны:

- новый simulation / event / operator-first слой;
- отдельный BIOS-support слой;
- несколько путей intent-обработки;
- заметный ship-centric legacy в `q_core_agent`.

Следовательно, BR-01 должен описывать **реальную многослойность репозитория**, а не изображать уже полностью очищенный канон.

---

## 3. Что подтверждается кодом надёжно

### F1. В архиве есть реальный runtime-core, а не только документы

Подтверждённые кодовые узлы:

- `src/qiki/services/q_sim_service/*`
- `src/qiki/services/faststream_bridge/*`
- `src/qiki/services/operator_console/*`
- `src/qiki/services/q_bios_service/*`
- `src/qiki/services/registrar/*`
- `src/qiki/services/q_core_agent/*`
- `src/qiki/shared/*`
- `protos/*`
- `schemas/asyncapi/*`
- `docker-compose*.yml`

Это означает, что проект имеет не только narrative-слой, но и устойчивый программный каркас.

### F2. Симуляционный слой является одним из главных технических центров

`q_sim_service/service.py`:

- загружает bot/spec-конфиг;
- вычисляет `hardware_profile_hash`;
- поднимает `WorldModel(bot_config=...)`;
- ведёт runtime-state и control-команды;
- публикует telemetry / events / radar.

`q_sim_service/grpc_server.py` поднимает gRPC-поверхность и фоновый цикл симуляции.

`q_sim_service/core/world_model.py` применяет `hardware_profile` к реальному поведению модели: actuator role map, power characteristics, runtime planes и derived diagnostics.

Из этого следует:

**симуляция — не вспомогательная заглушка, а один из реальных технических центров системы.**

### F3. Конфигурационная истина является стеком, а не одним файлом

Код не подтверждает упрощённую формулу «истина = один `bot_config.json`».

Что реально видно:

- `q_sim_service/service.py` ищет конфиг через `QIKI_BOT_CONFIG_PATH` / `BOT_CONFIG_PATH` и затем через fallback в repo path;
- `q_bios_service` использует `bot_config_path` как вход в BIOS POST-слой;
- `shared/config/*` и `shared/config_models.py` задают типизированный слой загрузки и валидации;
- compose-слой монтирует `config/`, `src/`, `protos/`, `tools/` и другие части среды как единый runtime context.

Значит корректная формула для BR-01 такая:

**spec/config truth = layered stack**, а не «единственный безусловный owner-файл».

### F4. Subject/transport слой централизован и реально используется несколькими сервисами

`shared/nats_subjects.py` задаёт canonical subjects / streams / durables.

Этот слой реально используется как минимум в:

- `q_sim_service`;
- `faststream_bridge`;
- `q_core_agent/qiki_orion_intents_service.py`;
- `qiki_chat/handler.py`;
- `registrar/main.py`.

Следовательно:

**transport truth в проекте действительно существует как общий кодовой слой**, а не как случайные строки по сервисам.

### F5. Operator surface реальна, но кодовая поверхность ещё не полностью схлопнута в один entrypoint

Что подтверждается кодом:

- `operator_console/main_orion_v.py` — прямой entrypoint ORION V;
- `docker-compose.operator_orionv.yml` и `docker-compose.operator.yml` запускают именно ORION V;
- в `operator_console/` одновременно присутствуют `main.py`, `main_orion.py`, `main_live.py`, `main_full.py`, `main_enhanced.py`, `main_integrated.py`.

При этом `operator_console/main.py` сам помечен как **LEGACY / ARCHIVE ENTRYPOINT** и прямо говорит, что каноническая консоль — `main_orion_v.py`.

Отсюда следует:

- ORION V действительно является главным operator entrypoint активного слоя;
- но кодовая поверхность оператора ещё хранит исторические и параллельные варианты запуска.

### F6. BIOS-слой реален и должен считаться частью runtime architecture

`q_bios_service/main.py`:

- поднимает HTTP-сервис;
- проверяет здоровье `q_sim_service`;
- собирает BIOS payload;
- публикует BIOS status в NATS.

`q_bios_service/bios_engine.py`:

- строит POST-результаты из `bot_config`;
- извлекает device rows из `hardware_profile` и `hardware_manifest`;
- вычисляет `hardware_profile_hash`.

Из этого следует:

**BIOS — это не только аналитическая метафора, а отдельный рабочий support/runtime слой.**

### F7. Intent/response слой в коде неоднороден и не сводится к одному бесспорному owner

Что показывает архив:

- `faststream_bridge/app.py` работает с `QIKI_INTENTS` / `QIKI_RESPONSES` и использует `qiki_chat.handler`;
- `qiki_chat/handler.py` даёт детерминированную обработку и proposals-only поведение;
- `q_core_agent/qiki_orion_intents_service.py` поднимает отдельный intent-service поверх тех же subject-ов;
- `docker-compose.qcore-intents.yml` прямо добавляет `q-core-intents` и одновременно отключает intent handling в `faststream-bridge`, чтобы избежать double replies.

Это очень важный факт.

Код сам подтверждает, что:

- intent path существует;
- proposals / replies реально обрабатываются;
- но ownership этого слоя исторически раздвоен и требует явной канонизации на уровне BR-02 / risk-layer.

### F8. Audit-слой реален, но не должен описываться как единственный центр всей истины

`registrar/main.py`:

- подписывается на system streams;
- формирует audit records;
- публикует их в `EVENTS_AUDIT`;
- работает как black-box recorder.

Следовательно:

- registrar — реальный audit-node;
- но он не заменяет собой simulation truth, spec truth или operator truth.

### F9. Ship-centric legacy не исчез и остаётся материальной частью архива

В `q_core_agent/core/` и тестах сохраняются:

- `ship_core.py`;
- `ship_actuators.py`;
- `ship_bios_handler.py`;
- `ship_fsm_handler.py`;
- `config/ship_config.json`;
- ship-related tests.

Это означает:

- ship-layer нельзя честно объявить уже отсутствующим в кодовой базе;
- его можно считать legacy по отношению к активному simulation/operator-first контуру;
- но BR-01 обязан признавать его фактическое присутствие.

---

## 4. Что из этого следует

### V1. Кодовая истина проекта многослойна

Нельзя сводить техническую картину к одному-единственному владельцу.

На уровне кода присутствуют как минимум следующие реальные слои:

- spec/config stack;
- simulation truth;
- event/transport truth;
- operator surface;
- BIOS-support;
- agent / intent logic;
- audit logging;
- ship-centric legacy.

### V2. Активный runtime-spine уже читается достаточно уверенно

Наиболее устойчивый кодовой позвоночник сейчас выглядит так:

`spec/config stack` → `q_sim_service / WorldModel` → `NATS/JetStream/FastStream subjects` → `operator surface / ORION V` → `audit / registrar`

Но этот spine **не равен** всей кодовой базе целиком, потому что рядом с ним присутствуют дополнительные и исторические слои.

### V3. QCoreAgent нельзя безоговорочно объявлять единственным центром проекта

Причина не в том, что `q_core_agent` неважен. Он важен.

Причина в другом:

- рядом есть самостоятельный `q_sim_service`;
- рядом есть самостоятельный `q_bios_service`;
- intent path не замыкается только на одном модуле;
- часть логики в `q_core_agent` всё ещё несёт ship-centric legacy.

То есть на уровне BR-01 корректнее писать не «весь проект центрирован на q_core_agent», а:

**`q_core_agent` — один из ключевых слоёв, но не единственный бесспорный центр кодовой истины.**

### V4. BR-01 должен удерживать distinction между фактом репозитория и решением о каноне

Например:

- факт: ORION V — активный операторский entrypoint;
- факт: intent ownership в коде неоднозначен;
- факт: ship-layer всё ещё присутствует;
- факт: BIOS является отдельным runtime-support слоем.

Но из этого автоматически не следует:

- что канон уже окончательно закрыт;
- что все ownership-вопросы уже сняты;
- что репозиторий уже очищен до одного смыслового центра.

---

## 5. Что в BR-01 допустимо считать фактами

Ниже — безопасный состав утверждений для этой ветки.

1. В архиве есть реальный многосервисный runtime-core.
2. `q_sim_service` и `WorldModel` являются одним из главных технических центров.
3. `hardware_profile` реально влияет на runtime-модель и BIOS-представление.
4. Subject/stream слой реально централизован в shared contracts.
5. ORION V является активным operator entrypoint, но вокруг него сохраняются legacy/parallel entrypoints.
6. `q_bios_service` — отдельный рабочий support/runtime слой.
7. `registrar` — реальный audit-node.
8. intent/response path существует, но ownership в коде неоднозначен.
9. ship-centric layer всё ещё материально присутствует в репозитории.
10. Следовательно, кодовая база ещё не тождественна полностью очищенному канону.

---

## 6. Что нельзя объявлять кодовым фактом

Ниже — формулировки, которые BR-01 не должен объявлять как уже доказанные кодом.

1. Что весь проект уже очищен до одного окончательного центра.
2. Что intent-owner уже бесспорно определён.
3. Что spec truth сводится к одному файлу.
4. Что audit-owner равен owner-у всей системной истины.
5. Что ship-layer уже фактически выведен из репозитория.
6. Что product identity полностью следует из одного только кода.
7. Что проект уже в состоянии полной end-to-end closure.

---

## 7. Риски неправильного чтения BR-01

### R1. Риск переупрощения config truth

Если свести конфигурационную истину к одному `bot_config.json`, это создаст ложную картину single-owner spec-layer.

### R2. Риск скрыть раздвоение intent-path

Если назвать только один owner для intent/response слоя, BR-01 начнёт противоречить и compose-слою, и risk-layer.

### R3. Риск преждевременно вычеркнуть ship-legacy

Если описать ship-layer как уже несуществующий, документ начнёт расходиться с самим архивом кода.

### R4. Риск перепутать active canon с полным содержимым репозитория

Код уже показывает активный spine, но всё ещё содержит исторические и переходные пласты.

---

## 8. Практическая роль BR-01 в пакете

BR-01 должен выполнять функцию нижнего ограничителя для остальных документов.

То есть:

- BR-02 не должен канонизировать то, что BR-01 не удерживает кодом;
- BR-03 должен опираться на признание ORION V как активного operator surface, но не скрывать многовходность;
- BR-04 не должен выдавать продуктовую интерпретацию за прямой факт репозитория;
- BR-05 не должен подменять кодовую истину архивной политикой.

Именно в этом и состоит роль ветки «Кодовая истина проекта».

---

## 9. Итоговая формула

**QIKI на уровне BR-01 — это многослойный кодовой архив с уже читаемым simulation / transport / operator / BIOS / audit spine, но ещё не доведённый до одного бесспорного технического центра из-за сохраняющейся неоднозначности ownership и присутствия ship-centric legacy.**
