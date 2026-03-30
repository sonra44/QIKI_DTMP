# ORION V Operator Execution Dossier

Цель этого dossier: зафиксировать канонический operator execution contour ORION V по фактическому коду и compose, без изменения behavior, чтобы следующие задачи можно было ставить без повторного расследования.

## 1. Canonical operator entrypoint

### Канонический entrypoint

- `src/qiki/services/operator_console/main_orion_v.py`
  - Единственная функция файла: `OrionVApp().run()`.
- `docker-compose.operator.yml`
  - `operator-console` запускается командой `python main_orion_v.py`.
- `scripts/run_orion_v_live.sh`
  - live/tmux path тоже жёстко использует `python main_orion_v.py`.

### Канонический launch contour

1. Поднять baseline runtime: `docker-compose.phase1.yml`
2. Поднять ORION overlay: `docker-compose.operator.yml`
3. Для интерактивной live-сессии использовать `scripts/run_orion_v_live.sh`

### Где собирается runtime

- `docker-compose.phase1.yml`
  - даёт baseline runtime: `nats`, `nats-js-init`, `q-sim-service`, `q-bios-service`, `faststream-bridge`, `q-core-intents`, `registrar`, `qiki-dev`
- `docker-compose.operator.yml`
  - накладывает `operator-console`
- `src/qiki/shared/nats_subjects.py`
  - единый набор canonical subjects/streams/durables

## 2. Full execution chain

Ниже зафиксирован полный путь `intent -> response -> confirm -> execute -> ack -> telemetry effect`.

### 2.1 Intent ingress

1. Оператор вводит `q: <текст>` в ORION.
2. `OrionVApp.on_input_submitted()` распознаёт QIKI intent и вызывает `_publish_qiki_intent()`.
3. `_publish_qiki_intent()` строит `QikiChatRequestV1` через `_build_qiki_chat_request()` и публикует его в `qiki.intents`.
4. В canonical contour owner subject `qiki.intents` = `q-core-intents`, потому что в `docker-compose.phase1.yml`:
   - `q-core-intents` слушает live `qiki.intents`
   - `faststream-bridge` уводится на `qiki.intents.faststream_disabled`

### 2.2 QIKI response ingress

1. `src/qiki/services/q_core_agent/qiki_orion_intents_service.py` подписывается на `qiki.intents`.
2. Handler строит `QikiChatResponseV1`.
3. Для observation-команд он дополнительно публикует objective event в `qiki.events.v1.operator.objectives` и скрытый audit event в `qiki.events.v1.audit`.
4. Затем публикует response в `qiki.responses.qiki`.
5. ORION подписан на `qiki.responses.qiki` через `NATSClient.subscribe_qiki_responses()`.
6. `OrionVApp._on_qiki_response()`:
   - валидирует `QikiChatResponseV1`
   - сохраняет `self._qiki_last_response`
   - извлекает `self._qiki_pending_action` через `_extract_qiki_pending_action()`
   - если есть legality/proposal, показывает оператору `q confirm`

### 2.3 Operator confirm

1. Команда `q confirm` обрабатывается в `OrionVApp.on_input_submitted()`.
2. Вызывается `_confirm_qiki_pending_action()`.
3. Открывается `ConfirmDialog`.
4. После подтверждения вызывается `_execute_qiki_pending_action()`.

### 2.4 Branch A: `NATS_COMMAND`

Эта ветка используется, когда `QikiProposedActionV1.kind == "NATS_COMMAND"`.

#### Execution

1. `_execute_qiki_pending_action()` берёт `action_kind`, `subject`, `name`, `parameters`.
2. Если `action_kind != ORION_PROCEDURE`, ORION ожидает:
   - `subject == qiki.commands.control`
   - задан `command_name`
3. `_publish_sim_command()`:
   - создаёт `CommandMessage`
   - кладёт `correlation_id`
   - публикует команду в `qiki.commands.control`

#### ACK

4. `_wait_for_ack()` ждёт подтверждение в локальном буфере `_control_acks`.
5. Буфер наполняется через `_on_control_response()`, который получает сообщения из `qiki.responses.control`.
6. `qiki.responses.control` в canonical contour публикует `q-sim-service`, а не bridge:
   - `src/qiki/services/q_sim_service/grpc_server.py::control_commands_loop()`
   - подписка на `qiki.commands.control`
   - `sim_service.apply_control_command(cmd)`
   - публикация response в `qiki.responses.control`

#### Telemetry effect

7. После ACK ORION вызывает `_wait_for_qiki_effect()`.
8. Для доказанного сегодня command-specific effect в коде явно реализован `sim.dock.release`:
   - ORION ждёт перехода snapshot docking в `state == undocked`
   - и `connected == false`
9. Если effect не подтверждён:
   - consequence переводится в `pending`
10. Если effect подтверждён:
   - consequence переводится в `confirmed`

### 2.5 Branch B: `ORION_PROCEDURE`

Эта ветка используется, когда `QikiProposedActionV1.kind == "ORION_PROCEDURE"`.

#### Procedure selection

1. `_execute_qiki_pending_action()` видит `action_kind == ORION_PROCEDURE`.
2. Вызывает `_execute_qiki_pending_procedure(procedure_name)`.
3. Процедура ищется в `ProcedureEngine`, который загружается при старте `OrionVApp.__init__()`.
4. Директория процедур:
   - env `ORIONV_PROCEDURES_DIR`
   - default: `/workspace/config/orion_v/procedures`

#### Procedure execution

5. `ProcedureEngine.load_from_dir()` загружает `*.json`, `*.yaml`, `*.yml`.
6. `parse_procedure_file()` валидирует:
   - `name`
   - `steps`
   - для каждого шага: `command`, `expected_ack`, `timeout`, `parameters`, `on_fail`
7. `_execute_qiki_pending_procedure()` создаёт `self._procedure_task = asyncio.create_task(self._run_procedure(...))`
8. `_run_procedure()`:
   - публикует `procedure_start` в `qiki.events.v1.operator.procedures`
   - вызывает `ProcedureEngine.run(...)`
   - по завершении публикует `procedure_finish` в `qiki.events.v1.operator.procedures`

#### Inner loop inside ProcedureEngine

9. `ProcedureEngine.run()` для каждого шага:
   - вызывает `publish_command(step.command, step.parameters)`
   - ждёт `wait_ack(step.expected_ack, step.timeout)`
   - при таймауте публикует `procedure_step_failed`
   - при `on_fail != continue` завершает процедуру со статусом `failed`
10. Если все шаги прошли:
   - state = `ok`
   - публикуется `procedure_done`

#### Post-procedure effect confirmation

11. `_wait_for_procedure_completion()` ждёт `self._procedure_task.done()` и `ProcedureEngine.state.status == "ok"`.
12. После этого `_wait_for_procedure_effect()` ждёт телеметрический эффект:
   - для `sim.start`: совпадение `fsm_state`, `paused`, `speed`
   - для `sim.rcs.fire`: подтверждение через `propulsion.rcs.command_pct` и `time_left_s`
13. Если effect подтверждён:
   - ORION публикует objective update в `qiki.events.v1.operator.objectives`
   - обновляет QIKI consequence
   - для `hostile_rcs_intercept_burst` публикует combat consequence event в `qiki.events.v1.operator.combat`
14. Если effect не подтверждён:
   - consequence остаётся `pending`
15. Если процедура не завершилась успешно:
   - objective update публикуется со статусом `failed`

## 3. Subscriptions map

### 3.1 ORION runtime subscriptions

Подписки создаются в `OrionVApp._connect_and_subscribe()` через `NATSClient`.

| Subject | Transport | Subscriber in ORION | Role |
| --- | --- | --- | --- |
| `qiki.telemetry` | core NATS | `subscribe_system_telemetry()` | Основная telemetry/snapshot truth для effect checks |
| `qiki.radar.v1.tracks` | JetStream | `subscribe_tracks()` | Актуальные radar tracks |
| `qiki.events.v1.>` | core NATS | `subscribe_events()` | Общий event ingress, включая objective/audit/combat/operator/system events |
| `qiki.responses.control` | core NATS | `subscribe_control_responses()` | ACK/control response intake |
| `qiki.responses.qiki` | core NATS | `subscribe_qiki_responses()` | Ответы QIKI на intents |

### 3.2 Hydration subscriptions / persisted read path

ORION не только живо подписывается, но и читает persisted state из JetStream:

| Persisted source | How | Why |
| --- | --- | --- |
| `QIKI_EVENTS_V1` / `qiki.events.v1.operator.objectives` | `fetch_last_event_json(stream=EVENTS_STREAM_NAME, subject=OPERATOR_OBJECTIVES)` | boot hydration последней observation objective |
| `QIKI_EVENTS_V1` / wildcard history | `fetch_events_history()` | replay/history support |

### 3.3 Q-Core side subscriptions relevant to ORION contour

В canonical contour `q_core_agent/qiki_orion_intents_service.py` подписывается на:

| Subject | Role |
| --- | --- |
| `qiki.intents` | Основной ingress operator intents |
| `qiki.secrets.v1.openai_api_key` | runtime secret update/status |
| `qiki.events.v1.operator.objectives` | local cache latest objectives |
| `qiki.events.v1.operator.actions` | follow-up synthesis back into objective updates |

## 4. Publications map

### 4.1 Publications by ORION

| Subject | Publisher in ORION | Purpose |
| --- | --- | --- |
| `qiki.intents` | `_publish_qiki_intent()` | Отправка operator intent в QIKI |
| `qiki.commands.control` | `_publish_sim_command()` | Исполнение direct sim command или procedure step |
| `qiki.events.v1.operator.actions` | `_publish_operator_action()` / `_publish_audit_event()` | operator action audit |
| `qiki.events.v1.operator.procedures` | `_publish_procedure_audit()` / `_run_procedure()` | procedure lifecycle audit |
| `qiki.events.v1.operator.objectives` | `_publish_observation_objective_update()` | objective state transitions |
| `qiki.events.v1.operator.combat` | `_publish_operator_event()` from `_execute_qiki_pending_procedure()` | combat consequence after confirmed hostile procedure |
| `qiki.events.v1.operator.incidents` | `_publish_audit_event()` from `_on_event()` | incident-open audit |

### 4.2 Publications not owned by ORION but required by the contour

| Subject | Owner in canonical contour | Role |
| --- | --- | --- |
| `qiki.responses.qiki` | `q-core-intents` | legality/reply/proposal response |
| `qiki.events.v1.operator.objectives` | `q-core-intents` and ORION | seed/update objective contour |
| `qiki.events.v1.audit` | `q-core-intents`, registrar, other services | hidden observation audit and event audit stream |
| `qiki.responses.control` | `q-sim-service` | control ACK / execution response |
| `qiki.telemetry` | `q-sim-service` publisher path | telemetry truth for effect confirmation |

### 4.3 Persisted boot hydration via JetStream

Persisted boot hydration для ORION сегодня доказана для observation objective:

1. Events stream `QIKI_EVENTS_V1` создаётся `nats-js-init`
2. Subject wildcard stream: `qiki.events.v1.>`
3. `q-core-intents` публикует `qiki.events.v1.operator.objectives`
4. JetStream хранит последнее сообщение subject
5. При boot ORION вызывает `_hydrate_last_observation_objective_from_jetstream()`
6. `NATSClient.fetch_last_event_json()` читает last message через `js.get_last_msg()`
7. ORION синтетически прогоняет payload через `_on_event()` как `EVENTS_REPLAY`

Это именно persisted hydration, а не live-only subscription.

## 5. ProcedureEngine role

`ProcedureEngine` канонически не вынесен в отдельный сервис и не является owner subjects. Его роль локальная и строго orchestration-level внутри ORION.

### Что делает ProcedureEngine

- грузит procedure definitions из файлов
- хранит registry процедур
- хранит execution state текущей процедуры
- пошагово вызывает already-existing control path:
  - publish command
  - wait for ACK
  - emit procedure audit

### Чего ProcedureEngine не делает

- не подписывается на NATS сам
- не владеет `qiki.commands.control`
- не владеет `qiki.responses.control`
- не публикует напрямую telemetry
- не переносит execution в другой сервис

Итог: `ProcedureEngine` это локальный orchestrator для multi-step control execution поверх уже существующего command/ack path.

## 6. ACK/effect proof chain

### 6.1 Direct `NATS_COMMAND` proof chain

1. ORION публикует `CommandMessage` в `qiki.commands.control`
2. `q-sim-service.control_commands_loop()` принимает команду
3. `sim_service.apply_control_command(cmd)` исполняет её
4. `q-sim-service` публикует response в `qiki.responses.control`
5. ORION получает response через `_on_control_response()`
6. `_wait_for_ack()` матчится по:
   - `command_id` / `request_id`
   - success payload
   - `kind` или `payload.command_name` или `payload.status`
7. После ACK ORION ждёт telemetry effect через `_wait_for_qiki_effect()`
8. Только после effect consequence считается `confirmed`

### 6.2 `ORION_PROCEDURE` proof chain

1. ORION получает procedure proposal в `qiki.responses.qiki`
2. Оператор подтверждает через `q confirm`
3. `ProcedureEngine.run()` выполняет шаги
4. Каждый шаг идёт через тот же `qiki.commands.control`
5. Каждый шаг ждёт ACK через тот же `qiki.responses.control`
6. После завершения всех шагов ORION отдельно ждёт post-procedure telemetry effect
7. Только после этого:
   - objective update становится `confirmed`
   - QIKI consequence обновляется
   - при hostile procedure публикуется combat consequence event

### 6.3 Что здесь доказано, а что нет

Доказано кодом:

- ACK owner = `q-sim-service`
- ORION сам ждёт и ACK, и telemetry effect
- `NATS_COMMAND` и `ORION_PROCEDURE` имеют разный execution path после confirm

Не доказано как generic framework:

- `_wait_for_qiki_effect()` сегодня явно реализует точечный effect-check для `sim.dock.release`
- procedure effect checks покрывают конкретные shape:
  - `sim.start`
  - `sim.rcs.fire`

То есть canonical chain существует полностью, но effect matcher пока command/procedure-specific, а не универсальный.

## 7. Entry-point drift inventory

### 7.1 Legacy / redundant entrypoints

| Artifact | Drift |
| --- | --- |
| `src/qiki/services/operator_console/main.py` | Сам файл прямо помечен как `LEGACY / ARCHIVE ENTRYPOINT`, требует `ALLOW_LEGACY_OPERATOR_CONSOLE=1` |
| `src/qiki/services/operator_console/main_orion.py` | Исторический non-V path, не canonical ORION V entrypoint |
| `docker-compose.operator_orionv.yml` | Не новый contour, а только альтернативный override запуска того же ORION V через `python -m ...main_orion_v` |
| `docker-compose.operator_legacy.yml` | Явный legacy overlay с `profiles: ["legacy"]` и запуском `qiki.services.operator_console.legacy.main_orion` |
| `docker-compose.yml` | Mixed older contour: поднимает operator-console, но не является canonical runtime basis для текущего ORION contour |

### 7.2 Dockerfile CMD vs compose command

Есть прямой drift:

- `src/qiki/services/operator_console/Dockerfile`
  - default `CMD ["python", "main_orion.py"]`
- `docker-compose.operator.yml`
  - runtime override `command: python main_orion_v.py`

Итог:

- canonical runtime truth сейчас задаётся compose overlay
- Dockerfile default отстаёт и сам по себе уводит в non-canonical path

### 7.3 Drift по owner `qiki.responses.control`

В коде canonical owner ACK subject = `q-sim-service`.

Но drift существует в документации:

- `docs/ARCHITECTURE.md`
  - утверждает, что `faststream-bridge` подписан на `qiki.commands.control` и публикует `qiki.responses.control`
- фактический canonical path:
  - `q_sim_service/grpc_server.py` принимает `qiki.commands.control`
  - `q_sim_service/grpc_server.py` публикует `qiki.responses.control`

Дополнительная деталь:

- в `faststream-bridge/app.py` остаётся latent/alternate path для `qiki.intents`
- но доказанного control-response publisher на `qiki.responses.control` в canonical contour здесь не требуется для ORION path

## 8. Что в ORION канонично, а что legacy

### Канонично

- `src/qiki/services/operator_console/main_orion_v.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/procedure_engine.py`
- `src/qiki/services/operator_console/clients/nats_client.py`
- `config/orion_v/procedures/*.json`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/q_sim_service/grpc_server.py`
- `src/qiki/shared/nats_subjects.py`
- `src/qiki/shared/models/qiki_chat.py`
- `docker-compose.phase1.yml`
- `docker-compose.operator.yml`
- `scripts/run_orion_v_live.sh`

### Legacy / non-canonical / drift-bearing

- `src/qiki/services/operator_console/main.py`
- `src/qiki/services/operator_console/main_orion.py`
- `src/qiki/services/operator_console/legacy/main_orion.py`
- `docker-compose.operator_legacy.yml`
- `docker-compose.operator_orionv.yml`
- `docker-compose.yml`
- `src/qiki/services/operator_console/Dockerfile` default CMD
- `docs/ARCHITECTURE.md` фрагмент с bridge-as-control-response-owner

## 9. Canonical path-defining files

Это минимальный набор файлов, которые реально определяют canonical ORION path и по которым можно ставить следующие задачи:

1. `docker-compose.phase1.yml`
2. `docker-compose.operator.yml`
3. `scripts/run_orion_v_live.sh`
4. `src/qiki/services/operator_console/main_orion_v.py`
5. `src/qiki/services/operator_console/orion_v/app.py`
6. `src/qiki/services/operator_console/orion_v/procedure_engine.py`
7. `config/orion_v/procedures/safe_pause_resume.json`
8. `config/orion_v/procedures/safe_pause_slow_resume.json`
9. `config/orion_v/procedures/hostile_rcs_intercept_burst.json`
10. `src/qiki/services/operator_console/clients/nats_client.py`
11. `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
12. `src/qiki/services/q_sim_service/grpc_server.py`
13. `src/qiki/shared/models/qiki_chat.py`
14. `src/qiki/shared/nats_subjects.py`

## 10. Short operational conclusions

- `NATS_COMMAND` и `ORION_PROCEDURE` уже разведены кодом после `q confirm`.
- ORION не owner legality; он owner operator-side confirm/execute/effect confirmation contour.
- Control ACK canonical owner сейчас `q-sim-service`.
- ProcedureEngine каноничен только как локальный orchestrator внутри ORION.
- Persisted boot hydration через JetStream для observation objective уже является частью canonical path.
