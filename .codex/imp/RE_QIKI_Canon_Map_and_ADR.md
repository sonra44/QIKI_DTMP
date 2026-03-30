# RE_QIKI_Canon_Map_and_ADR

## 1. Назначение документа

Этот документ фиксирует **не желаемый, а допустимо канонизированный контур проекта QIKI** после повторной сверки с кодом, runtime-evidence и risk-layer.

Его задача — не объявить весь проект «закрытым каноном», а разделить:

- что уже можно держать как canonical spine;
- что можно считать only verified-support;
- что остаётся unresolved и не должно преждевременно канонизироваться;
- какие короткие ADR допустимы уже сейчас без завышения уверенности.

Этот документ читается вместе с:

- `RE_QIKI_Architecture_Verification_Note.md`
- `RE_QIKI_Maturity_Matrix.md`
- `RUNTIME_EVIDENCE_NOTES.md`
- `RISKS_AND_UNRESOLVED_ZONES.md`

---

## 2. Базовая формула канона

На текущем этапе корректно держать такую короткую формулу:

```text
QIKI actual spine
  = spec stack
  -> physical runtime truth
  -> transport / contract canon
  -> intent normalization / response path
  -> decision / arbitration
  -> operator surface
  -> audit trail
```

Но важно: не каждый слой в этой цепочке уже имеет одинаково жёсткий статус.

- `physical runtime truth` — strong canonical;
- `transport / contract canon` — strong canonical;
- `operator surface` — canonical as primary surface;
- `decision / arbitration` — canonical with bounded scope;
- `intent ownership` — still partially unresolved;
- `audit ownership` — bounded, not singular;
- `runtime closure` — not yet.

---

## 3. Canon Map

```text
QIKI
├── Spec Canon
│   ├── q_core_agent/config/bot_config.json
│   ├── referenced config subtree
│   └── env / compose selection layer
│
├── Physical Runtime Canon
│   ├── q_sim_service
│   └── q_sim_service.core.world_model
│
├── Contract Canon
│   ├── shared models
│   ├── protos / gRPC transport contracts
│   ├── shared/events/cloudevents.py
│   └── shared/nats_subjects.py
│       ├── qiki.telemetry
│       ├── qiki.radar.v1.frames
│       ├── qiki.radar.v1.tracks
│       ├── qiki.commands.control
│       ├── qiki.responses.control
│       ├── qiki.intents
│       ├── qiki.responses.qiki
│       ├── qiki.events.v1.*
│       └── qiki.events.v1.audit
│
├── Intent / Meaning Canon
│   ├── qiki_chat as thin ingress / request-shape edge
│   ├── faststream_bridge as normalization / routing / proposal-execution path
│   └── incident / mode / guard semantics
│
├── Decision Canon
│   └── q_core_agent
│       └── provider update -> sensors -> BIOS -> FSM -> proposals -> decision
│
├── BIOS / Status Support Canon
│   └── q_bios_service
│
├── Operator Canon
│   └── ORION V
│
├── Audit Canon
│   ├── qiki.events.v1.audit
│   └── registrar as audit sink / support layer
│
└── Non-canonical or unresolved
    ├── duplicate operator entrypoints
    ├── shell_os as secondary surface
    ├── intents ownership ambiguity
    ├── signature_changed live path
    ├── ship_* family
    └── mission_control* family
```

---

## 4. Ownership summary

```text
spec truth owner
  = spec stack
  = bot_config.json + referenced config subtree + env/compose selection

physical runtime truth owner
  = q_sim_service + world_model

contract owner
  = shared contracts + proto + subject canon + CloudEvents helpers

intent ingress owner
  = qiki_chat edge

intent normalization / execution owner
  = faststream_bridge

final decision / arbitration owner
  = q_core_agent

bios / status support owner
  = q_bios_service

primary operator UX owner
  = ORION V

audit trail owner
  = event audit path + registrar
  != registrar alone
```

Ключевое ограничение:

- `q_core_agent` — canonical decision layer, но не доказанный единственный владелец всех intent-paths;
- `faststream_bridge` — не просто transport, но и не весь decision canon;
- `registrar` — audit/support слой, но не sole owner of historical truth;
- `spec truth` нельзя упрощать до одного файла `bot_config.json`.

---

## 5. ADR-001 — Physical runtime truth belongs to spec stack + simulation runtime

**Статус:** adopted with bounded scope.

### Контекст

В проекте есть несколько слоёв, которые могут выглядеть как источник истины:

- config/spec layer;
- simulation runtime;
- agent layer;
- operator UI;
- event / bridge layer;
- audit layer.

### Решение

Физическая runtime-истина проекта закрепляется за связкой:

- `spec stack` как описательный источник машины;
- `q_sim_service + world_model` как исполняемый источник физического состояния.

### Ограничение

`spec stack` нельзя сводить только к `bot_config.json`: кодовая реальность использует и ссылочные config-пути, и средовой selection layer.

### Последствия

- UI не становится second truth source;
- agent не становится owner of physical state;
- bridge не становится owner of physical state;
- audit не становится owner of physical state.

---

## 6. ADR-002 — ORION V is the primary operator surface

**Статус:** adopted.

### Контекст

В репозитории есть несколько operator entrypoint'ов и исторические поверхности.

### Решение

`ORION V` фиксируется как **primary operator surface**.

### Ограничение

Это не означает, что в репозитории нет других UI-поверхностей. Это означает только, что именно `ORION V` является главным операторским слоем текущего пакета.

### Последствия

- product-critical operator UX читается через ORION V;
- параллельные main-entrypoints трактуются как duplicate-or-transition;
- secondary surfaces не канонизируются автоматически.

---

## 7. ADR-003 — Subject model is a first-class architectural contract

**Статус:** adopted.

### Контекст

Event-driven часть проекта нельзя описывать как «абстрактную шину».

### Решение

`shared/nats_subjects.py` и реально используемые subject families считаются first-class частью архитектуры.

### Ядро families

- `qiki.telemetry`
- `qiki.radar.v1.frames`
- `qiki.radar.v1.tracks`
- `qiki.commands.control`
- `qiki.responses.control`
- `qiki.intents`
- `qiki.responses.qiki`
- `qiki.events.v1.*`
- `qiki.events.v1.audit`

### Последствия

- subject drift считается архитектурным изменением;
- transport topology входит в canonical documentation;
- документы не должны скрывать subject model за общими словами вроде «NATS layer».

---

## 8. ADR-004 — q_core_agent is the canonical decision layer, but not the sole intent owner

**Статус:** adopted with caveat.

### Контекст

Есть риск либо завысить роль `q_core_agent` до owner of everything, либо занизить её до периферии.

### Решение

`q_core_agent` фиксируется как **canonical decision / arbitration layer**.

### Ограничение

Ownership по intents остаётся распределённым:

- `qiki_chat` формирует ingress request shape;
- `faststream_bridge` исполняет часть normalization / proposal / routing path;
- `q_core_agent` удерживает decision/arbitration loop.

Следовательно, формула `intent owner = q_core_agent only` пока некорректна.

### Последствия

- decision spine можно считать canonical;
- full intent ownership нельзя считать окончательно закрытым;
- risk `intents ownership ambiguity` остаётся активным.

---

## 9. ADR-005 — faststream_bridge is part of meaning / execution canon, not just transport glue

**Статус:** adopted with bounded wording.

### Контекст

Прежняя формула «bridge = просто транспорт» была слишком слабой.

### Решение

`faststream_bridge` закрепляется как часть canonical meaning/execution path, потому что он не только маршрутизирует события, но и участвует в:

- валидации request shape;
- proposal-store / accept-reject path;
- публикации control commands;
- части mode / guard / event normalization.

### Ограничение

Это не делает bridge final decision owner.

### Последствия

- bridge нельзя опускать до уровня вторичного plumbing;
- но и нельзя объявлять его единым центром смыслового управления.

---

## 10. ADR-006 — q_bios_service is a verified support layer, not the center of machine truth

**Статус:** adopted as support ADR.

### Контекст

В старом каноне BIOS-слой был недоразведён.

### Решение

`q_bios_service` фиксируется как **verified-support BIOS/status layer**.

Он:

- вычисляет BIOS/status payload;
- использует bot-config path и q-sim health checks;
- публикует status events;
- влияет на наблюдаемую runtime-картину.

### Ограничение

Он не является:

- owner of physical truth;
- главным decision layer;
- replacement for simulation runtime.

### Последствия

- BIOS-слой должен присутствовать в архитектурной карте;
- но не должен искусственно расширяться до source-of-truth центра.

---

## 11. ADR-007 — registrar is part of audit canon, but audit ownership is distributed

**Статус:** adopted with caveat.

### Контекст

Раньше было слишком легко свести audit canon к формуле `registrar = audit owner`.

### Решение

`registrar` фиксируется как **audit sink / support layer**, а `qiki.events.v1.audit` — как часть canonical audit path.

### Ограничение

Audit semantics не принадлежат одному `registrar` монолитно, потому что audit-события создаются и публикуются разными частями стека.

### Последствия

- registrar можно считать важным audit-узлом;
- registrar нельзя описывать как единственный owner of reconstructable history;
- event audit path надо мыслить шире, чем один сервис.

---

## 12. ADR-008 — UI may explain truth, but must not replace it

**Статус:** adopted.

### Контекст

Операторская поверхность агрегирует и интерпретирует данные, и без жёсткого ограничения быстро становится second truth source.

### Решение

Любая операторская поверхность имеет право:

- визуализировать;
- агрегировать;
- объяснять;
- сопровождать решения и legality-context.

Но не имеет права:

- придумывать физические значения без источника;
- подменять runtime truth собственным состоянием;
- скрывать unresolved runtime gaps за удобной картинкой.

### Последствия

- truth-first telemetry остаётся принципом operator UX;
- derived values должны быть отличимы от source values;
- UI-красота не может считаться доказательством runtime closure.

---

## 13. Status map of blocks

```text
canonical
  - spec stack
  - q_sim_service / world_model
  - shared contracts / subject model / CloudEvents
  - q_core_agent as decision layer
  - faststream_bridge as meaning / execution path
  - ORION V as primary operator surface

verified-support
  - q_bios_service
  - registrar
  - qiki_chat as edge ingress layer
  - shell_os as secondary surface
  - record / replay tools

proof-stage
  - active slice G3-QIKI-009

duplicate-or-transition
  - multiple operator entrypoints

suspected-legacy
  - ship_* family
  - mission_control* family

unresolved
  - signature_changed live path
  - intents ownership ambiguity
  - final runtime closure
```

---

## 14. Чего этот документ не утверждает

Этот документ **не утверждает**, что:

- весь проект fully closed;
- ownership по intents уже разведён без остатка;
- registrar является единым хозяином audit history;
- legacy-зоны окончательно исключены;
- active runtime path уже полностью доказан live-наблюдением.

Такие утверждения сейчас были бы завышением уверенности.

---

## 15. Самая короткая рабочая формула

```text
QIKI current canon
  = spec stack
  -> simulation truth
  -> contract / subject canon
  -> bridge + agent control path
  -> ORION V operator surface
  -> distributed audit trail

closure != complete
```

---

## 16. Практический вывод

На текущем этапе канон проекта уже можно держать как **сильный, но ограниченный**.

Сильный — потому что architectural spine, subject model, decision layer, operator primary surface и audit path уже достаточно хорошо восстановлены.

Ограниченный — потому что runtime closure, full intent ownership и несколько transition/legacy зон ещё не должны подаваться как окончательно закрытые.
