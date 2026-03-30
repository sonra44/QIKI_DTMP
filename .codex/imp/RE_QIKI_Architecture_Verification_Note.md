# QIKI Architecture Verification Note

## 1. Назначение документа

Этот документ фиксирует не желаемую, а наблюдаемую архитектурную картину проекта по коду и runtime-слоям архива.

Его задача — разделить:

- что прямо наблюдается в коде;
- что можно считать рабочей архитектурной опорой;
- что раньше было сформулировано слишком сильно и теперь должно быть ослаблено;
- что остаётся unresolved и не должно канонизироваться раньше времени.

Документ читается как **as-built verification note**, а не как продуктовая презентация.

---

## 2. Базовый вывод

На текущем этапе QIKI корректно читать как многослойную операторско-симуляционную систему, в которой:

- `q_sim_service` удерживает физический runtime-контур и часть исходной телеметрической истины;
- `q_core_agent` реализует внутренний decision/tick pipeline;
- `faststream_bridge` и связанные event-handlers реализуют routing, нормализацию и часть operator-intent логики;
- `ORION V` является primary operator surface;
- `registrar` реализует audit ingestion / republish слой, но не является единственным origin-источником audit semantics;
- `q_bios_service` присутствует как отдельный BIOS/status side-service и влияет на фактическую runtime-картину;
- проект имеет несколько compose-контуров, а не один единственный canonical deployment path.

Следовательно, архитектура проекта уже достаточно хорошо читается, но несколько старых сильных формул надо ослабить.

---

## 3. Что подтверждено кодом

### 3.1. Физический runtime-центр действительно находится в q_sim_service

Это подтверждается тем, что:

- `q_sim_service` поднимает gRPC server;
- внутри него крутится background simulation loop;
- он же подписывается на `qiki.commands.control`;
- он же публикует `qiki.responses.control`;
- `world_model` встроен в сервис как источник runtime state evolution.

Рабочая формула здесь такая:

```text
physical_runtime_truth
  = q_sim_service + world_model
```

Это одна из самых устойчивых архитектурных точек проекта.

### 3.2. Контрактный/event-слой действительно вынесен в shared subjects + CloudEvents helpers + proto

Код показывает устойчивый contract spine:

- `qiki/shared/nats_subjects.py` содержит canonical subject families;
- `qiki/shared/events/cloudevents.py` используется как общий event-envelope helper;
- `protos/` и generated/grpc слой задают transport contracts;
- radar/event/control families названы явно и используются повторно в нескольких сервисах.

Корректная формула:

```text
transport_and_contracts
  = proto/contracts + shared subject canon + CloudEvents helpers + NATS/JetStream
```

### 3.3. ORION V действительно является primary operator surface

Это подтверждается не только наличием `orion_v/` subtree, но и тем, что:

- есть отдельный entrypoint `main_orion_v.py`;
- есть отдельный compose overlay `docker-compose.operator_orionv.yml`;
- основной operator overlay запускает именно `main_orion_v.py`;
- внутри `orion_v/app.py` присутствует полноценная TUI-сборка экранов, overlays, action bar, audit/system screens и NATS-интеграция.

При этом важно не завышать вывод: ORION V — primary surface, но не единственная UI-поверхность репозитория.

### 3.4. q_core_agent действительно является самостоятельным decision pipeline

Код подтверждает, что в `q_core_agent` существует собственный агентный цикл:

```text
provider update
  -> sensor ingest
  -> BIOS handling
  -> FSM handling
  -> proposal evaluation
  -> decision
  -> actuator command
```

То есть `q_core_agent` — не декоративный модуль, а реальный decision/arbitration слой.

Но его нельзя автоматически объявлять единственным владельцем всех operator-intent решений, потому что intent-path в проекте раздвоен.

### 3.5. faststream_bridge — не просто транспорт, а слой нормализации и части operator-intent исполнения

Это важно.

В коде `faststream_bridge/app.py` видно, что bridge:

- подписывается на `qiki.intents`;
- валидирует `QikiChatRequestV1`;
- хранит proposals для последующего accept/reject;
- при accept публикует control commands в `qiki.commands.control`;
- публикует audit events;
- занимается mode-изменениями и частью event normalization.

Следовательно, формула вида «bridge — только transport glue» была бы занижением.

### 3.6. registrar существует как реальный audit service, но не как эксклюзивный владелец всего audit-origin слоя

Код подтверждает, что `registrar`:

- подписывается на radar frames;
- подписывается на `qiki.events.v1.>`;
- формирует audit records;
- публикует их в `qiki.events.v1.audit`;
- пишет лог локально.

Но одновременно audit-события в `qiki.events.v1.audit` публикуются не только им. Их напрямую публикуют и другие сервисы, как минимум `faststream_bridge`, а также qcore-intents path.

Значит корректно говорить так:

```text
audit_layer
  = registrar as audit collector / republisher
  + direct audit publishers in active services
```

А не так:

```text
audit_truth_owner = registrar only
```

---

## 4. Что пришлось ослабить после самопроверки

### 4.1. Spec truth нельзя сводить к `bot_config.json + root config/*`

Раньше это было сформулировано слишком жёстко.

По коду видно более сложную картину:

- `q_core_agent/core/bot_core.py` загружает `config/bot_config.json` внутри собственного сервиса;
- compose-контуры пробрасывают `BOT_CONFIG_PATH` как runtime override;
- root `config/` содержит доменные таблицы и subsystem rules;
- `q_sim_service/config.yaml` задаёт runtime-параметры сервиса;
- BIOS service тоже читает bot config через configurable path.

Поэтому корректнее так:

```text
spec_stack
  = q_core_agent bot_config
  + root domain config
  + runtime env/config injection
  + service-level config files
```

То есть `bot_config.json` остаётся важнейшим anchor, но не единственным owner всей spec truth.

### 4.2. Decision owner и intent owner нельзя полностью отождествлять

Да, `q_core_agent` является decision pipeline.

Но operator-intents обрабатываются не только им:

- `faststream_bridge` обрабатывает `qiki.intents` в одном runtime contour;
- отдельный compose overlay поднимает `q_core_agent/qiki_orion_intents_service.py`;
- overlay специально отключает intent handling у bridge, чтобы не было double replies.

Это значит, что в проекте есть **вариативный intent owner**, зависящий от compose-контура.

Следовательно, нельзя писать:

```text
operator intent owner = q_core_agent
```

И нельзя писать:

```text
operator intent owner = faststream_bridge
```

Корректнее:

```text
operator intent path
  = compose-dependent
  = faststream_bridge path OR q_core_intents path
```

Это одна из главных unresolved-зон архитектуры.

### 4.3. BIOS-слой нельзя описывать как чисто внутреннюю часть q_core_agent

В архиве есть отдельный `q_bios_service`, который:

- поднимает HTTP service;
- проверяет health q-sim;
- строит BIOS status;
- публикует BIOS payload в NATS.

При этом внутри `q_core_agent` сохраняются `BiosHandler` и `ShipBiosHandler`.

Значит BIOS path в проекте смешанный:

```text
bios_layer
  = q_bios_service side-service
  + q_core_agent BIOS handling
  + config-driven hardware expectations
```

Именно поэтому BIOS лучше считать **active but not fully simplified** слоем, а не идеально очищенной single-owner архитектурой.

### 4.4. Operator surface нельзя описывать как один чистый entrypoint

Хотя ORION V является primary surface, в `operator_console` видно сразу несколько entrypoints:

- `main.py`
- `main_orion.py`
- `main_orion_v.py`
- `main_live.py`
- `main_full.py`
- `main_integrated.py`
- legacy subtree

Следовательно, слой операторских поверхностей в репозитории всё ещё переходный.

Правильная формула:

```text
operator_surface
  = ORION V as primary
  + multiple secondary / legacy / transitional entrypoints
```

---

## 5. Observed map после перепроверки

```text
QIKI
├── Spec Stack
│   ├── q_core_agent/config/bot_config.json
│   ├── root config/*
│   ├── service config.yaml files
│   └── env/compose overrides
│
├── Physical Runtime
│   ├── q_sim_service
│   └── world_model
│
├── BIOS / Status Layer
│   ├── q_bios_service
│   ├── BiosHandler
│   └── ShipBiosHandler
│
├── Contracts / Transport
│   ├── protos + grpc
│   ├── shared nats subjects
│   ├── CloudEvents helpers
│   └── NATS / JetStream
│
├── Meaning / Routing Layer
│   ├── faststream_bridge
│   ├── incident / guard semantics
│   └── operator event normalization
│
├── Decision Layer
│   ├── q_core_agent tick pipeline
│   └── q_core_intents optional overlay
│
├── Operator Surface
│   ├── ORION V
│   ├── shell_os
│   └── multiple legacy/transitional operator entrypoints
│
├── Audit Layer
│   ├── registrar
│   ├── direct audit publishers
│   └── qiki.events.v1.audit family
│
└── Supporting / Auxiliary
    ├── qiki_chat
    ├── smoke tools
    ├── record/replay tools
    └── mission_control / ship_* residual families
```

---

## 6. Что уже можно канонизировать

На текущем этапе разумно канонизировать следующее.

### 6.1. Runtime canon

```text
runtime_canon
  = q_sim_service + world_model
```

### 6.2. Contract canon

```text
contract_canon
  = protos + shared subject names + CloudEvents helpers + NATS/JetStream
```

### 6.3. Primary operator canon

```text
primary_operator_surface
  = ORION V
```

### 6.4. Decision canon с оговоркой

```text
decision_canon
  = q_core_agent
```

Но только для внутреннего agent pipeline, не для всей operator-intent поверхности целиком.

### 6.5. Audit canon с оговоркой

```text
audit_canon
  = qiki.events.v1.audit family + registrar as audit collector
```

Но не как эксклюзивный единственный источник всех audit-событий.

---

## 7. Что пока нельзя канонизировать без оговорок

### 7.1. Единственный intent owner

Не подтверждено.

В проекте есть минимум два активных runtime-path:

- `faststream_bridge` path;
- `q_core_intents` overlay path.

### 7.2. Чистый single-source BIOS owner

Не подтверждено.

BIOS architecture остаётся смешанной и частично переходной.

### 7.3. Один canonical deployment contour

Не подтверждено.

В архиве есть несколько compose-контуров:

- baseline;
- phase1;
- qcore-intents overlay;
- operator overlay;
- operator_orionv overlay;
- shell_os overlay;
- legacy operator overlay;
- minimal contour.

Следовательно, проект надо читать как систему с несколькими runtime compositions.

### 7.4. registrar как exclusive audit owner

Не подтверждено.

Он является audit collector/republisher, но не эксклюзивным origin publisher.

---

## 8. Подозрительно переходные или legacy-зоны

Следующие семьи не следует автоматически удалять или объявлять мусором, но и канонизировать их без live proof нельзя:

- `ship_*` family;
- `mission_control*` family;
- часть старых operator entrypoints;
- часть roadmap/docs-derived остатков;
- часть secondary surfaces вне ORION V.

Это именно transition layer, а не автоматически verified garbage.

---

## 9. Рабочие правила чтения репозитория после самопроверки

1. Любой тезис о physical truth должен проходить через `q_sim_service` и `world_model`.
2. Любой тезис о operator UI по умолчанию должен проходить через `ORION V`, но с учётом наличия transitional entrypoints.
3. Любой тезис о intent execution должен проверяться по compose-контуру, а не объявляться единым заранее.
4. Любой тезис о BIOS owner должен считаться условным, пока смешанный BIOS path не нормализован окончательно.
5. Любой тезис об audit owner должен разделять `audit family`, `publisher`, `collector`, `storage role`.
6. Любой тезис о spec truth должен учитывать не только `bot_config.json`, но и runtime config injection.

---

## 10. Итоговая формула

Самая точная архитектурная формула на текущем этапе такая:

```text
QIKI_actual
  = stable simulation/runtime spine
  + stable contract/event spine
  + primary ORION V operator surface
  + real q_core decision pipeline
  + active but mixed BIOS and intent layers
  + multi-compose deployment reality
  - unresolved ownership ambiguities
  - unresolved transition/legacy zones
```

Именно это сейчас является наиболее честной архитектурной фиксацией проекта.

Не минимальной. Не рекламной. И не завышенной.
