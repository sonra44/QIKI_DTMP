# QIKI_CODEX_AUDIT_FOR_TASKING

> Historical / superseded pre-closure audit.
>
> This file captures blocker-era analysis before the post-closure stabilization baseline recorded on 2026-03-24 and 2026-03-25 UTC.
> Do not use it as the current tasking baseline for active work.
>
> Current source-of-truth entrypoints for this slice:
> - [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md)
> - [TASK_OUT/observation_contour_dossier.md](/home/sonra44/QIKI_DTMP/TASK_OUT/observation_contour_dossier.md)
> - [TASK_OUT/minimal_regression_pack_wrapper.md](/home/sonra44/QIKI_DTMP/TASK_OUT/minimal_regression_pack_wrapper.md)
> - [docs/CUTOVER_PLAN.md](/home/sonra44/QIKI_DTMP/docs/CUTOVER_PLAN.md)
> - [docs/ORION_V_RUNBOOK.md](/home/sonra44/QIKI_DTMP/docs/ORION_V_RUNBOOK.md)
>
> Any statements below that describe `signature_changed` as proof-stage/open blocker belong to that historical audit context.

## 1. Краткое описание проекта

`QIKI_DTMP` по фактическому коду и текущим compose-контурам является не "платформой вообще", а стеком для космического sim-game / operator cockpit:

- источник мира и truth-данных: `q_sim_service`;
- message bus и event backbone: `NATS + JetStream`;
- преобразование radar truth и часть event/runtime plumbing: `faststream_bridge`;
- операторская поверхность: `operator_console` / `ORION V`;
- QIKI intent/proposal слой: `q_core_agent.qiki_orion_intents_service`;
- BIOS/status слой: `q_bios_service`;
- audit/logging слой: `registrar`.

Основание:

- код и compose: [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml), [docker-compose.operator.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml), [src/qiki/services/q_sim_service/grpc_server.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py), [src/qiki/services/operator_console/main_orion_v.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main_orion_v.py);
- продуктовый контекст: [LOG.MD](/home/sonra44/QIKI_DTMP/LOG.MD), [README.md](/home/sonra44/QIKI_DTMP/README.md);
- restart/runbook слой: [docs/RESTART_CHECKLIST.md](/home/sonra44/QIKI_DTMP/docs/RESTART_CHECKLIST.md), [scripts/run_orion_v_live.sh](/home/sonra44/QIKI_DTMP/scripts/run_orion_v_live.sh).

Главный вывод для tasking:

- поддерживаемый runtime сегодня строится вокруг `Phase1 + ORION V + q-core-intents`;
- в репозитории есть заметный слой alternate/legacy entrypoints и compose-файлов;
- до постановки точечных задач нужно разделять:
  - канонический runtime path;
  - support path;
  - legacy/archive path.

## 2. Источники истины и метод анализа

### 2.1. Порядок доверия

Использован заданный порядок:

1. код, compose, config, tests;
2. RE-документы;
3. прочая документация;
4. архивные/task/analysis документы только как вспомогательный контекст.

### 2.2. Что реально использовано

Основные runtime-источники:

- compose:
  - [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)
  - [docker-compose.operator.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml)
  - [docker-compose.qcore-intents.yml](/home/sonra44/QIKI_DTMP/docker-compose.qcore-intents.yml)
  - [docker-compose.shell_os.yml](/home/sonra44/QIKI_DTMP/docker-compose.shell_os.yml)
  - [docker-compose.yml](/home/sonra44/QIKI_DTMP/docker-compose.yml)
  - [docker-compose.minimal.yml](/home/sonra44/QIKI_DTMP/docker-compose.minimal.yml)
  - [docker-compose.operator_orionv.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator_orionv.yml)
  - [docker-compose.operator_legacy.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator_legacy.yml)
- канонические subject/stream имена:
  - [src/qiki/shared/nats_subjects.py](/home/sonra44/QIKI_DTMP/src/qiki/shared/nats_subjects.py)
- ключевые entrypoints:
  - [src/qiki/services/q_sim_service/grpc_server.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py)
  - [src/qiki/services/q_core_agent/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/main.py)
  - [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py)
  - [src/qiki/services/faststream_bridge/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/app.py)
  - [src/qiki/services/operator_console/main_orion_v.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main_orion_v.py)
  - [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py)
  - [src/qiki/services/q_bios_service/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_bios_service/main.py)
  - [src/qiki/services/registrar/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/registrar/main.py)
  - [src/qiki/services/qiki_chat/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/qiki_chat/main.py)
  - [src/qiki/services/shell_os/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/shell_os/main.py)
- ключевые tests:
  - [tests/integration/test_control_ack_envelope.py](/home/sonra44/QIKI_DTMP/tests/integration/test_control_ack_envelope.py)
  - [tests/integration/test_faststream_bridge.py](/home/sonra44/QIKI_DTMP/tests/integration/test_faststream_bridge.py)
  - [tests/integration/test_system_mode_boot_event_stream.py](/home/sonra44/QIKI_DTMP/tests/integration/test_system_mode_boot_event_stream.py)
  - [tests/integration/test_xpdr_gating_flow.py](/home/sonra44/QIKI_DTMP/tests/integration/test_xpdr_gating_flow.py)
  - [tests/integration/test_radar_flow.py](/home/sonra44/QIKI_DTMP/tests/integration/test_radar_flow.py)
  - [tests/integration/test_radar_tracks_flow.py](/home/sonra44/QIKI_DTMP/tests/integration/test_radar_tracks_flow.py)
  - [tests/unit/test_qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/tests/unit/test_qiki_orion_intents_service.py)
  - [tests/unit/test_orion_v_qiki_loop.py](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_qiki_loop.py)
  - [tests/unit/test_orion_v_cockpit.py](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_cockpit.py)
- RE-документ, реально полезный для runtime:
  - [docs/RESTART_CHECKLIST.md](/home/sonra44/QIKI_DTMP/docs/RESTART_CHECKLIST.md)

### 2.3. Важное ограничение источников

- В репозитории не найден отдельный набор документов вида `RE_QIKI_*`.
- Из RE-слоя практически полезным для этого прохода оказался только [docs/RESTART_CHECKLIST.md](/home/sonra44/QIKI_DTMP/docs/RESTART_CHECKLIST.md).
- Старые task/analysis документы использовались только там, где нужно было локализовать уже известный blocker `signature_changed`; runtime-истина при этом бралась из кода.

### 2.4. Метод

- сначала определён фактический launch contour по compose и entrypoints;
- затем по каждому сервису выделены:
  - реальная роль;
  - точки запуска;
  - входы/выходы;
  - канонический path;
  - alternate/legacy path;
  - drift и blocker-места;
- затем разложены end-to-end цепочки;
- затем собран tasking map: что уже можно отдавать агенту локально, а что нельзя без фиксации общего канона.

## 3. Каноническая карта сервисов

### 3.1. Канонический runtime-контур

Текущий канонический контур:

- `nats`
- `nats-js-init`
- `q-sim-service`
- `faststream-bridge`
- `q-bios-service`
- `q-core-intents`
- `qiki-dev`
- `operator-console` через overlay [docker-compose.operator.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml)
- `registrar` как audit/support сервис

Основание:

- [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)
- [docker-compose.operator.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml)
- [docs/RESTART_CHECKLIST.md](/home/sonra44/QIKI_DTMP/docs/RESTART_CHECKLIST.md)

### 3.2. Канонические сервисы по факту

| Сервис | Статус |
| --- | --- |
| `q_sim_service` | канонический truth/source сервис |
| `q_core_agent` | канонический модуль, но с двумя разными deployment-ролями |
| `faststream_bridge` | канонический для radar/system_mode; не канонический для intents в default contour |
| `operator_console / ORION V` | каноническая operator surface |
| `q_bios_service` | канонический support/status сервис |
| `registrar` | канонический audit/support сервис |
| `qiki_chat` | secondary/alternate path, не входит в default contour |
| `shell_os` | support/ops UI overlay, не default contour |

### 3.3. Вторичные / support / legacy компоненты

Support:

- `qiki-dev` как dev/test runner и контейнер, из которого запускаются проверки;
- `nats-js-init` как bootstrap JetStream;
- `shell_os` как overlay для host/runtime-инспекции;
- `registrar` как аудитный "black box".

Legacy / archive / alternate:

- [src/qiki/services/operator_console/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main.py)
- [src/qiki/services/operator_console/main_orion.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main_orion.py)
- [src/qiki/services/operator_console/main_live.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main_live.py)
- [src/qiki/services/operator_console/main_full.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main_full.py)
- [src/qiki/services/operator_console/main_enhanced.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main_enhanced.py)
- [src/qiki/services/operator_console/main_integrated.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main_integrated.py)
- standalone `qiki_chat` service on subject `qiki.chat.v1`;
- старые compose-контуры `[docker-compose.yml](/home/sonra44/QIKI_DTMP/docker-compose.yml)` и `[docker-compose.minimal.yml](/home/sonra44/QIKI_DTMP/docker-compose.minimal.yml)`.

## 4. Разбор каждого сервиса

### 4.1. `q_sim_service`

Реальная роль:

- truth/source сервиса мира и симуляции;
- держит simulation state;
- отдаёт gRPC API;
- публикует telemetry;
- публикует radar truth;
- публикует sim events;
- принимает control commands по NATS и сам публикует control ACK.

Главный entrypoint:

- канонический: [src/qiki/services/q_sim_service/grpc_server.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py)
- alternate: [src/qiki/services/q_sim_service/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/main.py)

Как запускается:

- в supported contour: `python -m qiki.services.q_sim_service.grpc_server` из [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)

Участие в compose:

- [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)
- [docker-compose.yml](/home/sonra44/QIKI_DTMP/docker-compose.yml)
- [docker-compose.minimal.yml](/home/sonra44/QIKI_DTMP/docker-compose.minimal.yml)

Основные зависимости:

- `NATS_URL`
- `tools/ensure_generated.sh`
- protobuf stubs в `generated/`
- world model внутри [src/qiki/services/q_sim_service/service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py)

Входящие каналы / API / subjects / endpoints:

- gRPC:
  - `HealthCheck`
  - `GetSensorData`
  - `SendActuatorCommand`
  - `GetRadarFrame`
- NATS subscribe:
  - `qiki.commands.control` через `control_commands_loop` в [grpc_server.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py)

Исходящие каналы / API / subjects / endpoints:

- `qiki.responses.control` публикуется самим `q_sim_service`
- `qiki.telemetry`
- `qiki.radar.v1.frames`
- `qiki.radar.v1.frames.lr`
- `qiki.radar.v1.tracks.sr`
- `qiki.events.v1.sensor.thermal`
- `qiki.events.v1.sensor.thermal.trip`
- `qiki.events.v1.power.bus`
- `qiki.events.v1.power.pdu`

Что выглядит каноническим runtime path:

- `grpc_server.py` + `QSimService.tick()` + NATS control loop;
- тесты подтверждают именно этот path:
  - [tests/integration/test_control_ack_envelope.py](/home/sonra44/QIKI_DTMP/tests/integration/test_control_ack_envelope.py)
  - [tests/integration/test_sim_start_speed.py](/home/sonra44/QIKI_DTMP/tests/integration/test_sim_start_speed.py)
  - [tests/integration/test_sim_pause_effects.py](/home/sonra44/QIKI_DTMP/tests/integration/test_sim_pause_effects.py)
  - [tests/integration/test_sim_stop_effects.py](/home/sonra44/QIKI_DTMP/tests/integration/test_sim_stop_effects.py)

Что выглядит legacy / alternate / archive path:

- standalone `main.py` без gRPC и без явного compose-контракта;
- прямой `SendActuatorCommand` по gRPC существует, но operator runtime в основном использует NATS command path.

Признаки architectural drift:

- `q_sim_service` сам публикует `qiki.responses.control`, а не bridge;
- при этом в ORION client есть комментарий про "control responses emitted by FastStream bridge" в [src/qiki/services/operator_console/clients/nats_client.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/clients/nats_client.py), что конфликтует с кодом;
- subject `qiki.radar.v1.tracks.sr` по имени выглядит как track-stream, но публикуется из `radar_publisher.py` как frame-like payload. Это не обязательно баг, но это явная naming ambiguity.

Незавершённости / риски / ambiguity:

- не зафиксирован отдельный документ, который объясняет почему SR поток называется `tracks.sr`, хотя он идёт из radar publisher;
- alternate entrypoint `main.py` не описан как официально неподдерживаемый;
- часть control-команд существует фактически в `apply_control_command`, но не сведена в единый runtime command contract.

Что надо сделать, чтобы довести сервис до рабочего состояния:

- зафиксировать и проверить единый список поддерживаемых `COMMANDS_CONTROL`;
- отдельно задокументировать truth subjects и типы payload;
- доказать supported/non-supported launch path.

Какие задачи можно ставить агенту отдельно:

- составить runtime command registry по `apply_control_command`;
- собрать contract map по gRPC и NATS outputs;
- сделать доказательный smoke по telemetry/radar/event subjects;
- проверить и документировать SR/LR/union radar topics.

Какие задачи нельзя ставить без фиксации общего канона:

- переименование `qiki.radar.v1.tracks.sr`;
- перенос ownership control ACK на bridge;
- изменение способа запуска `q_sim_service`.

Критерии Done для задач по сервису:

- доказан запуск через canonical compose;
- список входов/выходов подтверждён кодом и smoke/integration tests;
- alternate path либо помечен как legacy, либо покрыт отдельным supported статусом;
- нет неоднозначности, кто публикует control ACK и какие subjects truth-критичны.

### 4.2. `q_core_agent`

Реальная роль:

- модуль не является одним однозначным сервисом, а имеет две разные runtime-роли:
  - `main.py`: agent tick loop с gRPC/BIOS ingestion;
  - `qiki_orion_intents_service.py`: канонический intent/proposal слой для ORION/QIKI.

Главные entrypoints:

- [src/qiki/services/q_core_agent/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/main.py)
- [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py)

Как запускается:

- `qiki-dev`: `python -m qiki.services.q_core_agent.main --grpc`
- `q-core-intents`: `python -m qiki.services.q_core_agent.qiki_orion_intents_service`

Участие в compose:

- `main.py` как command контейнера `qiki-dev` в [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)
- `q-core-intents` как отдельный сервис в [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)
- исторический overlay в [docker-compose.qcore-intents.yml](/home/sonra44/QIKI_DTMP/docker-compose.qcore-intents.yml)

Основные зависимости:

- gRPC к `q-sim-service` через `GrpcDataProvider`
- HTTP к `q-bios-service` через `BIOS_URL`
- NATS для intents/objectives/actions/secrets

Входящие каналы / API / subjects / endpoints:

- `main.py`:
  - gRPC `GetSensorData`
  - HTTP `GET /bios/status`
- `qiki_orion_intents_service.py`:
  - `qiki.intents`
  - `qiki.events.v1.operator.objectives`
  - `qiki.events.v1.operator.actions`
  - `qiki.secrets.v1.openai_api_key`

Исходящие каналы / API / subjects / endpoints:

- `main.py`:
  - собственного внешнего supported output path почти не видно; в основном обновляет internal context / state store / event_store
- `qiki_orion_intents_service.py`:
  - `qiki.responses.qiki`
  - `qiki.events.v1.operator.objectives`
  - `qiki.events.v1.audit` для hidden observation events

Что выглядит каноническим runtime path:

- для operator/QIKI contour канонический path даёт именно `qiki_orion_intents_service.py`;
- `docs/RESTART_CHECKLIST.md` ссылается именно на `q-core-intents`;
- default Phase1 compose поднимает именно отдельный сервис `q-core-intents`.

Что выглядит legacy / alternate / archive path:

- `main.py --mock`;
- `main.py` как самостоятельный "brain" без явной связи с operator contour;
- старый standalone `qiki_chat` path, который функционально частично пересекается с intent logic.

Признаки architectural drift:

- одно имя "q_core_agent" покрывает две разные runtime-функции;
- `main.py` в default contour запускается внутри `qiki-dev`, но текущий operator path не использует его как owner intents/proposals;
- `GrpcDataProvider.get_proposals()` возвращает `[]`, то есть предложение в operator path сегодня приходит не из `main.py`, а из `qiki_orion_intents_service.py`.

Незавершённости / риски / ambiguity:

- не зафиксировано, нужен ли `qiki-dev -> main.py --grpc` в production-like runtime или это dev/runtime support;
- role split между "agent health/safe mode/context" и "QIKI intent engine" не сведён в явный subsystem contract;
- `fetch_bios_status()` кэширует HTTP BIOS в фоне: это осознанное поведение, но его легко принять за прямой synchronous truth path, если не читать код.

Что надо сделать, чтобы довести сервис до рабочего состояния:

- разделить на уровне docs/runtime map роль `main.py` и роль `qiki_orion_intents_service.py`;
- зафиксировать, какой из них обязателен в supported contour;
- собрать отдельный command/policy map для QIKI intents.

Какие задачи можно ставить агенту отдельно:

- паспорт `qiki_orion_intents_service.py` по intent/proposal paths;
- аудит `main.py` как health/state/safe-mode loop;
- карта зависимостей `GrpcDataProvider`;
- smoke/dossier по BIOS URL + gRPC + NATS inputs этого модуля.

Какие задачи нельзя ставить без фиксации общего канона:

- удаление `main.py` из runtime;
- перенос intent ownership обратно в `faststream_bridge`;
- объединение `qiki_chat` и `q_core_intents` без продуктового решения.

Критерии Done:

- отдельно описаны supported deployment роли;
- по каждой роли определены inputs/outputs и owner-функция;
- устранена ambiguity между `q-core-intents` и `qiki-dev/main.py`;
- intent path подтверждён кодом и smoke/tests.

### 4.3. `faststream_bridge`

Реальная роль:

- канонический bridge для radar frames -> radar tracks;
- публикует boot-time `system_mode`;
- опционально может обрабатывать `qiki.intents`, но в default contour это отключено.

Главный entrypoint:

- [src/qiki/services/faststream_bridge/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/app.py)

Как запускается:

- `faststream run qiki.services.faststream_bridge.app:app` через Dockerfile [src/qiki/services/faststream_bridge/Dockerfile](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/Dockerfile)

Участие в compose:

- [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)
- [docker-compose.yml](/home/sonra44/QIKI_DTMP/docker-compose.yml)
- [docker-compose.minimal.yml](/home/sonra44/QIKI_DTMP/docker-compose.minimal.yml)
- environment override в [docker-compose.qcore-intents.yml](/home/sonra44/QIKI_DTMP/docker-compose.qcore-intents.yml)

Основные зависимости:

- `NATS_URL`
- JetStream stream `QIKI_RADAR_V1`
- guard table / lag monitor / mode store

Входящие каналы / API / subjects / endpoints:

- JetStream subscriber на `qiki.radar.v1.frames`
- alternate intent subscriber на `qiki.intents`

Исходящие каналы / API / subjects / endpoints:

- `qiki.radar.v1.tracks`
- `qiki.events.v1.radar.guard`
- `qiki.events.v1.system_mode`
- alternate `qiki.responses.qiki`
- alternate publish в `qiki.commands.control` при ACCEPT proposal
- `qiki.events.v1.audit` для `proposal_accept`

Что выглядит каноническим runtime path:

- radar pipeline;
- boot persisted `system_mode` event.

Основание:

- [src/qiki/services/faststream_bridge/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/app.py)
- [tests/integration/test_radar_flow.py](/home/sonra44/QIKI_DTMP/tests/integration/test_radar_flow.py)
- [tests/integration/test_radar_tracks_flow.py](/home/sonra44/QIKI_DTMP/tests/integration/test_radar_tracks_flow.py)
- [tests/integration/test_system_mode_boot_event_stream.py](/home/sonra44/QIKI_DTMP/tests/integration/test_system_mode_boot_event_stream.py)

Что выглядит legacy / alternate / archive path:

- intent handling в `handle_qiki_intent`;
- reuse `qiki_chat.handler` inside bridge.

Признаки architectural drift:

- код bridge умеет делать intents, но default contour специально выключает это через `QIKI_INTENTS_SUBJECT=qiki.intents.faststream_disabled`;
- одновременно существует отдельный сервис `q-core-intents`, который уже делает эту работу;
- overlay [docker-compose.qcore-intents.yml](/home/sonra44/QIKI_DTMP/docker-compose.qcore-intents.yml) выглядит как transitional artefact, потому что current phase1 уже содержит `q-core-intents`.

Незавершённости / риски / ambiguity:

- intent ownership между bridge и q-core-intents исторически раздвоен;
- fallback path `QIKI_ALLOW_BRIDGE_FALLBACK` существует и должен считаться opt-in, а не каноном;
- без явной фиксации канона легко поставить задачу "чинить intents в bridge" и попасть мимо поддерживаемого contour.

Что надо сделать, чтобы довести сервис до рабочего состояния:

- закрепить, что supported role сервиса = radar + system_mode, а не default intent engine;
- явно обозначить статус `handle_qiki_intent`;
- проверить, что supported compose не даёт double replies.

Какие задачи можно ставить агенту отдельно:

- паспорт radar truth pipeline;
- аудит JetStream lag monitor и guard events;
- документирование `system_mode` persisted boot path.

Какие задачи нельзя ставить без фиксации общего канона:

- перенос intent ownership в bridge;
- удаление `handle_qiki_intent`;
- изменение subject'ов `qiki.intents/qiki.responses.qiki`.

Критерии Done:

- доказан single-owner intent contour;
- radar pipeline подтверждён integration tests;
- mode boot event устойчиво сохраняется в JetStream;
- fallback не считается скрытым default behavior.

### 4.4. `operator_console / ORION V`

Реальная роль:

- каноническая operator surface;
- читает telemetry/tracks/events/control responses/QIKI responses;
- публикует control commands, operator actions, objective updates, audit events;
- локально исполняет `ORION_PROCEDURE` через `ProcedureEngine`.

Главный entrypoint:

- [src/qiki/services/operator_console/main_orion_v.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main_orion_v.py)

Как запускается:

- container command в [docker-compose.operator.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml)
- canonical live path под tmux: [scripts/run_orion_v_live.sh](/home/sonra44/QIKI_DTMP/scripts/run_orion_v_live.sh)

Участие в compose:

- overlay [docker-compose.operator.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml)
- старый contour [docker-compose.yml](/home/sonra44/QIKI_DTMP/docker-compose.yml)
- redundant overlay [docker-compose.operator_orionv.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator_orionv.yml)
- legacy overlay [docker-compose.operator_legacy.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator_legacy.yml)

Основные зависимости:

- NATS core + JetStream через [src/qiki/services/operator_console/clients/nats_client.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/clients/nats_client.py)
- local procedure files:
  - [config/orion_v/procedures/safe_pause_resume.json](/home/sonra44/QIKI_DTMP/config/orion_v/procedures/safe_pause_resume.json)
  - [config/orion_v/procedures/safe_pause_slow_resume.json](/home/sonra44/QIKI_DTMP/config/orion_v/procedures/safe_pause_slow_resume.json)
  - [config/orion_v/procedures/hostile_rcs_intercept_burst.json](/home/sonra44/QIKI_DTMP/config/orion_v/procedures/hostile_rcs_intercept_burst.json)

Входящие каналы / API / subjects / endpoints:

- `qiki.telemetry`
- `qiki.radar.v1.tracks`
- `qiki.events.v1.>`
- `qiki.responses.control`
- `qiki.responses.qiki`
- boot hydration через `JetStream get_last_msg` для persisted events

Исходящие каналы / API / subjects / endpoints:

- `qiki.commands.control`
- `qiki.intents`
- `qiki.events.v1.operator.actions`
- `qiki.events.v1.operator.objectives`
- `qiki.events.v1.operator.procedures`
- `qiki.events.v1.operator.incidents`
- `qiki.events.v1.operator.combat`
- `qiki.events.v1.audit` через `_publish_audit_event`

Что выглядит каноническим runtime path:

- `main_orion_v.py` -> `OrionVApp`;
- `docker-compose.phase1.yml + docker-compose.operator.yml`;
- live TTY через `./scripts/run_orion_v_live.sh`.

Что выглядит legacy / alternate / archive path:

- [src/qiki/services/operator_console/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main.py) явно помечен как archived;
- `main_orion.py`, `main_live.py`, `main_full.py`, `main_enhanced.py`, `main_integrated.py` не являются каноническими entrypoints;
- Dockerfile по умолчанию всё ещё имеет `CMD ["python", "main_orion.py"]`, что конфликтует с каноном.

Признаки architectural drift:

- явный конфликт между:
  - каноном `main_orion_v.py` в compose и docs;
  - default Dockerfile CMD `main_orion.py`;
- несколько entrypoint-файлов рядом с каноническим;
- NATS client содержит комментарий про control responses от bridge, хотя фактический publisher сейчас `q_sim_service`;
- ORION выполняет часть operator-to-execution path локально через `ProcedureEngine`, а не через отдельный orchestration service; это не баг само по себе, но это должна быть явная часть канона.

Незавершённости / риски / ambiguity:

- наблюдательная ветка с `review_required -> hold_for_recheck -> resume_observation` уже кодирована, но не вся полностью доказана live для каждого результата;
- `signature_changed` формально существует в code path и schema, но остаётся proof-stage;
- множественные legacy entrypoints увеличивают риск случайного запуска "не того" UI.

Что надо сделать, чтобы довести сервис до рабочего состояния:

- зафиксировать ORION V как единственный поддерживаемый operator entrypoint;
- собрать runbook уровня "subscribe/publish/ack/procedure" по фактическому коду;
- закрыть live-proof gaps по observation contours.

Какие задачи можно ставить агенту отдельно:

- карта ORION subscriptions/publications;
- аудит ProcedureEngine + procedure files;
- аудит observation contour path;
- аудит control ack -> telemetry confirmation path;
- audit dossier по incident/audit publications.

Какие задачи нельзя ставить без фиксации общего канона:

- удаление legacy entrypoints;
- перенос ProcedureEngine наружу из ORION;
- перепривязка operator path на другой service owner.

Критерии Done:

- канонический launch path однозначен;
- поддерживаемые subjects и execution paths задокументированы;
- procedure files, ack path и telemetry confirmation доказаны;
- `signature_changed` либо live-proven, либо формально зафиксирован как unsupported result в supported contour.

### 4.5. `q_bios_service`

Реальная роль:

- support/status сервис;
- делает gRPC health-check к `q-sim-service`;
- строит BIOS payload из bot config + sim health;
- отдаёт HTTP API;
- публикует `qiki.events.v1.bios_status`.

Главный entrypoint:

- [src/qiki/services/q_bios_service/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_bios_service/main.py)

Как запускается:

- `python -m qiki.services.q_bios_service.main` в [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)

Участие в compose:

- только в [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)

Основные зависимости:

- `BOT_CONFIG_PATH`
- `SIM_GRPC_HOST/SIM_GRPC_PORT`
- `NATS_URL`

Входящие каналы / API / subjects / endpoints:

- gRPC `HealthCheck` к `q-sim-service`
- HTTP requests:
  - `/healthz`
  - `/bios/status`
  - `/bios/component/<id>`
  - `/bios/reload`

Исходящие каналы / API / subjects / endpoints:

- HTTP payloads по endpoints выше
- `qiki.events.v1.bios_status`

Что выглядит каноническим runtime path:

- `main.py` + HTTP + NATS publish;
- consumption from `q_core_agent` через `BIOS_URL`.

Что выглядит legacy / alternate / archive path:

- alternate path не обнаружен; сервис выглядит относительно чистым.

Признаки architectural drift:

- `BOT_CONFIG_PATH` указывает на конфиг внутри `q_core_agent`, то есть BIOS truth structurally зависит от конфигурации другого сервиса;
- это не обязательно ошибка, но это сильная coupling-точка.

Незавершённости / риски / ambiguity:

- нет отдельного compose outside Phase1;
- зависимость на bot config path стоит считать частью канона, пока не доказано обратное.

Что надо сделать, чтобы довести сервис до рабочего состояния:

- формально закрепить contract BIOS HTTP + BIOS event;
- отдельно доказать, кто потребляет `qiki.events.v1.bios_status`, а кто HTTP `/bios/status`.

Какие задачи можно ставить агенту отдельно:

- service passport по HTTP/NATS контракту;
- smoke по `/healthz`, `/bios/status`, `/bios/component/<id>`;
- audit bot-config coupling.

Какие задачи нельзя ставить без фиксации общего канона:

- перенос BIOS truth из HTTP в чисто event-driven contour;
- отвязка от `q_core_agent` bot config.

Критерии Done:

- контракт HTTP и NATS сведён в один документ;
- известны все runtime consumers;
- подтверждено, что `BIOS_URL` и `qiki.events.v1.bios_status` не конфликтуют как dual sources.

### 4.6. `registrar`

Реальная роль:

- audit/support сервис;
- пишет audit в файл;
- подписывается на radar frames и wildcard system events;
- републикует audit records в `qiki.events.v1.audit`.

Главный entrypoint:

- [src/qiki/services/registrar/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/registrar/main.py)

Как запускается:

- через Dockerfile [src/qiki/services/registrar/Dockerfile](/home/sonra44/QIKI_DTMP/src/qiki/services/registrar/Dockerfile), контейнер `registrar` в [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)

Участие в compose:

- [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml)
- [docker-compose.yml](/home/sonra44/QIKI_DTMP/docker-compose.yml)
- [docker-compose.minimal.yml](/home/sonra44/QIKI_DTMP/docker-compose.minimal.yml)

Основные зависимости:

- NATS / FastStream
- volume `/var/log/qiki`

Входящие каналы / API / subjects / endpoints:

- `qiki.radar.v1.frames`
- `qiki.events.v1.>`

Исходящие каналы / API / subjects / endpoints:

- локальный лог-файл `/var/log/qiki/registrar.log`
- `qiki.events.v1.audit`

Что выглядит каноническим runtime path:

- wildcard audit backbone на event subjects;
- radar frame audit.

Что выглядит legacy / alternate / archive path:

- alternate paths явно не обнаружены.

Признаки architectural drift:

- сервис одновременно пишет в файл и публикует events;
- recursion block реализован кодом, но требует отдельного runtime proof для уверенности, что `audit` не начинает сам себя замыкать на неожиданных event_type/source комбинациях.

Незавершённости / риски / ambiguity:

- в supported contour не видно отдельного retention/rotation policy;
- не доказано, какие downstream consumers реально используют `qiki.events.v1.audit`.

Что надо сделать, чтобы довести сервис до рабочего состояния:

- собрать proof по audit fan-in/fan-out;
- зафиксировать retention/logging expectations.

Какие задачи можно ставить агенту отдельно:

- audit path dossier;
- recursion guard audit;
- file/log rotation audit.

Какие задачи нельзя ставить без фиксации общего канона:

- переезд с file-backed audit на pure event audit;
- изменение subject-аudit схемы.

Критерии Done:

- доказана схема `input events -> registrar -> audit event + file`;
- нет бесконтрольной рекурсии;
- явно определён supported retention policy.

### 4.7. `qiki_chat`

Реальная роль:

- standalone NATS RPC сервис на `qiki.chat.v1`;
- оборачивает тот же `qiki_chat.handler`, который используется как library из `faststream_bridge`;
- в default contour не является каноническим intent service.

Главный entrypoint:

- [src/qiki/services/qiki_chat/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/qiki_chat/main.py)

Как запускается:

- прямой `python ...`, но Dockerfile и compose для него не найдены.

Участие в compose:

- в исследованных compose-файлах отсутствует.

Основные зависимости:

- NATS;
- shared model `QikiChatRequestV1/QikiChatResponseV1`.

Входящие каналы / API / subjects / endpoints:

- `qiki.chat.v1`

Исходящие каналы / API / subjects / endpoints:

- response через NATS request/reply;
- proposals с `COMMANDS_CONTROL` в payload.

Что выглядит каноническим runtime path:

- каноническим path не выглядит.

Что выглядит legacy / alternate / archive path:

- весь сервис сейчас выглядит alternate path relative to `qiki.intents/qiki.responses.qiki`.

Признаки architectural drift:

- дублирование domain logic:
  - `qiki_chat.handler`
  - `faststream_bridge.handle_qiki_intent`
  - `q_core_agent.qiki_orion_intents_service`
- subject `qiki.chat.v1` живёт рядом с каноническим `qiki.intents`.

Незавершённости / риски / ambiguity:

- непонятен support tier этого сервиса;
- он легко может стать ложной точкой входа для нового агента.

Что надо сделать, чтобы довести сервис до рабочего состояния:

- либо явно пометить как unsupported/alternate;
- либо дать ему отдельный supported contour и compose.

Какие задачи можно ставить агенту отдельно:

- service passport только на тему "used/unused in default contour";
- найти реальные runtime consumers.

Какие задачи нельзя ставить без фиксации общего канона:

- удаление сервиса;
- merge этого сервиса в `q-core-intents` или bridge.

Критерии Done:

- support tier формально определён;
- понятно, кто и зачем должен использовать `qiki.chat.v1`, либо это path официально исключён из supported runtime.

### 4.8. `shell_os`

Реальная роль:

- support/ops TUI overlay;
- показывает host/runtime inspection данные: psutil, Docker CLI, NATS reachability;
- не является частью product operator contour.

Главный entrypoint:

- [src/qiki/services/shell_os/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/shell_os/main.py)

Как запускается:

- через overlay [docker-compose.shell_os.yml](/home/sonra44/QIKI_DTMP/docker-compose.shell_os.yml)

Участие в compose:

- только [docker-compose.shell_os.yml](/home/sonra44/QIKI_DTMP/docker-compose.shell_os.yml)

Основные зависимости:

- `psutil`
- `docker` CLI в контейнере/окружении
- `NATS_URL`

Входящие каналы / API / subjects / endpoints:

- прямых product subjects не использует;
- делает локальные host/runtime probes.

Исходящие каналы / API / subjects / endpoints:

- только локальный Textual UI.

Что выглядит каноническим runtime path:

- support overlay path, не default product path.

Что выглядит legacy / alternate / archive path:

- не legacy, но secondary.

Признаки architectural drift:

- overlay использует external network `qiki_dtmp_qiki-network-phase1`, тогда как основной compose объявляет `qiki-network-phase1`;
- это рабочий bridge path, но он требует знания Docker network naming, а не следует напрямую из product docs.

Незавершённости / риски / ambiguity:

- сервис легко перепутать с продуктовой operator surface;
- неясно, считается ли он supported user-facing feature или только internal ops tool.

Что надо сделать, чтобы довести сервис до рабочего состояния:

- зафиксировать support tier;
- описать, для каких задач он нужен, а для каких нет.

Какие задачи можно ставить агенту отдельно:

- overlay runbook;
- audit host probing and failure messages;
- network dependency proof.

Какие задачи нельзя ставить без фиксации общего канона:

- включение `shell_os` в default contour;
- попытка использовать его как замену ORION V.

Критерии Done:

- support status формально определён;
- documented launch path не конфликтует с operator contour;
- понятно, какие host/runtime probes считаются supported.

## 5. Карта runtime contours / compose / launch paths

### 5.1. Что есть в репозитории

| Compose | Оценка |
| --- | --- |
| [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml) | основной canonical runtime contour |
| [docker-compose.operator.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml) | canonical overlay для ORION V |
| [docker-compose.qcore-intents.yml](/home/sonra44/QIKI_DTMP/docker-compose.qcore-intents.yml) | transitional / redundant overlay |
| [docker-compose.shell_os.yml](/home/sonra44/QIKI_DTMP/docker-compose.shell_os.yml) | support overlay |
| [docker-compose.operator_orionv.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator_orionv.yml) | redundant command-only overlay |
| [docker-compose.operator_legacy.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator_legacy.yml) | explicit legacy overlay |
| [docker-compose.yml](/home/sonra44/QIKI_DTMP/docker-compose.yml) | старый broad contour, не лучший source of current runtime truth |
| [docker-compose.minimal.yml](/home/sonra44/QIKI_DTMP/docker-compose.minimal.yml) | старый minimal contour, не current canonical contour |

### 5.2. Какие contour'ы выглядят canonical

Canonical:

- `docker compose -f docker-compose.phase1.yml up -d --build`
- затем `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d operator-console`
- для live operator TTY: `./scripts/run_orion_v_live.sh`

Основание:

- [README.md](/home/sonra44/QIKI_DTMP/README.md)
- [docs/RESTART_CHECKLIST.md](/home/sonra44/QIKI_DTMP/docs/RESTART_CHECKLIST.md)
- [scripts/run_orion_v_live.sh](/home/sonra44/QIKI_DTMP/scripts/run_orion_v_live.sh)

### 5.3. Какие contour'ы выглядят experimental / legacy / archive

Experimental / transitional:

- [docker-compose.qcore-intents.yml](/home/sonra44/QIKI_DTMP/docker-compose.qcore-intents.yml)
  - причина: phase1 уже содержит `q-core-intents`, overlay дублирует и при этом всё ещё нужен только для historical disable-bridge semantics.

Legacy / archive:

- [docker-compose.operator_legacy.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator_legacy.yml)
- [docker-compose.yml](/home/sonra44/QIKI_DTMP/docker-compose.yml)
- [docker-compose.minimal.yml](/home/sonra44/QIKI_DTMP/docker-compose.minimal.yml)

Redundant:

- [docker-compose.operator_orionv.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator_orionv.yml)
  - по сути только меняет command на `main_orion_v`, что уже делает [docker-compose.operator.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml).

### 5.4. Реальные launch paths

`Phase1`:

- поднимает `nats`, `nats-js-init`, `q-sim-service`, `q-bios-service`, `faststream-bridge`, `q-core-intents`, `registrar`, `qiki-dev`.

`Operator surface`:

- накладывает `operator-console` поверх `Phase1`.

`Live operator`:

- не `docker attach`;
- а `docker exec -it qiki-operator-console python main_orion_v.py` через [scripts/run_orion_v_live.sh](/home/sonra44/QIKI_DTMP/scripts/run_orion_v_live.sh).

### 5.5. Рассинхроны compose / Dockerfile / docs / entrypoints

Конфликт 1:

- [docker-compose.operator.yml](/home/sonra44/QIKI_DTMP/docker-compose.operator.yml) запускает `python main_orion_v.py`;
- [src/qiki/services/operator_console/Dockerfile](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/Dockerfile) по умолчанию содержит `CMD ["python", "main_orion.py"]`.

Вывод:

- runtime truth задаёт compose, а Dockerfile default уже устарел относительно канона.

Конфликт 2:

- [src/qiki/services/operator_console/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/main.py) прямо говорит, что архивирован;
- рядом остаются ещё несколько `main_*` entrypoints без столь же жёсткой маркировки.

Конфликт 3:

- [docker-compose.qcore-intents.yml](/home/sonra44/QIKI_DTMP/docker-compose.qcore-intents.yml) выглядит как overlay для ввода `q-core-intents`;
- текущий [docker-compose.phase1.yml](/home/sonra44/QIKI_DTMP/docker-compose.phase1.yml) уже включает `q-core-intents`.

Конфликт 4:

- comments/docs вокруг ORION уже считают owner intent path = `q-core-intents`;
- `faststream_bridge` всё ещё содержит active code path `handle_qiki_intent`.

### 5.6. Канонический launch path для operator surface

Нужно считать каноном:

1. поднять `Phase1`;
2. поднять `operator-console` через overlay `docker-compose.operator.yml`;
3. для живой интерактивной сессии использовать [scripts/run_orion_v_live.sh](/home/sonra44/QIKI_DTMP/scripts/run_orion_v_live.sh) под `tmux`.

### 5.7. Кто в реальности владеет intent execution в default contour

В default contour ownership разделён так:

- `q-core-intents` владеет:
  - разбором `qiki.intents`;
  - генерацией `qiki.responses.qiki`;
  - публикацией observation objective seed/update в части follow-up;
- `ORION V` владеет:
  - operator confirmation;
  - локальным исполнением `ORION_PROCEDURE`;
  - публикацией `qiki.commands.control` для прямых команд;
  - публикацией observation objective updates после execution result;
- `q_sim_service` владеет:
  - фактическим применением control commands;
  - публикацией `qiki.responses.control`.

То есть owner execution в default contour не один сервис, а связка:

- `q-core-intents` = proposal/policy/procedure preparation;
- `ORION V` = operator-mediated execution orchestrator;
- `q_sim_service` = command application owner.

### 5.8. Ambiguity между `faststream_bridge` и `q_core_agent / q-core-intents`

Да, ambiguity есть.

Подтверждённые факты:

- bridge умеет `handle_qiki_intent`;
- phase1 disable-ит этот path через `QIKI_INTENTS_SUBJECT=qiki.intents.faststream_disabled`;
- `q-core-intents` подписывается на настоящий `qiki.intents`.

Практический вывод:

- в supported contour owner intents = `q-core-intents`;
- код bridge по intents сейчас нужно считать alternate path, а не shared ownership.

### 5.9. Какие contour'ы надо считать поддерживаемыми

Поддерживаемые:

- `Phase1`
- `Phase1 + operator overlay`
- `Phase1 + run_orion_v_live.sh`
- `Phase1 + shell_os overlay` как support/ops contour

Неподдерживаемые или неочевидно поддерживаемые:

- `docker-compose.yml`
- `docker-compose.minimal.yml`
- direct legacy operator entrypoints
- standalone `qiki_chat` contour

## 6. Межсервисные цепочки

### 6.1. Truth path: от `q_sim_service` к остальным

Старт:

- `q_sim_service.tick()` в [src/qiki/services/q_sim_service/service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py)

Проходит через:

1. `q_sim_service` публикует:
   - telemetry в `qiki.telemetry`;
   - radar frames в `qiki.radar.v1.frames`;
   - LR/SR split subjects;
   - sim events в `qiki.events.v1.*`;
2. `faststream_bridge` читает `qiki.radar.v1.frames` и публикует `qiki.radar.v1.tracks`;
3. `ORION V` читает telemetry, tracks, events;
4. `q_core_agent` читает sensor truth через gRPC и BIOS через HTTP.

Подтверждено кодом:

- [src/qiki/services/q_sim_service/grpc_server.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py)
- [src/qiki/services/q_sim_service/radar_publisher.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/radar_publisher.py)
- [src/qiki/services/q_sim_service/telemetry_publisher.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/telemetry_publisher.py)
- [src/qiki/services/faststream_bridge/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/app.py)
- [src/qiki/services/operator_console/clients/nats_client.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/clients/nats_client.py)

Где возможны разрывы / drift:

- `qiki.radar.v1.tracks.sr` naming ambiguity;
- `faststream_bridge` читает union frames, а не `tracks.sr`;
- ORION подписан на `qiki.radar.v1.tracks`, а не на SR subject как основной operator truth.

Вероятный текущий blocker:

- не functional blocker для default contour, а blocker для ясности канона: неразъяснённый SR subject contract.

### 6.2. Operator path: от `operator_console` к execution/result

Старт:

- операторский input внутри ORION V.

Цепочка:

1. ORION получает QIKI response или прямую operator action;
2. ORION либо:
   - публикует `qiki.commands.control`, либо
   - исполняет локальную `ORION_PROCEDURE`;
3. `q_sim_service` применяет команду;
4. `q_sim_service` публикует `qiki.responses.control`;
5. ORION ждёт ack и затем ждёт telemetry effect;
6. ORION публикует objective/combat/audit update.

Подтверждено кодом:

- [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py)
- [src/qiki/services/operator_console/orion_v/procedure_engine.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/procedure_engine.py)
- [src/qiki/services/q_sim_service/grpc_server.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py)

Где возможны разрывы / drift:

- ORION client comment про control responses от bridge;
- ORION procedure execution является частью канонического path, но это легко пропустить, если смотреть только на внешние сервисы.

Вероятный blocker:

- отсутствие одного явного operator execution map документа.

### 6.3. Proposal / accept / control path

Старт:

- `ORION V` публикует `qiki.intents`.

Цепочка:

1. `q-core-intents` подписывается на `qiki.intents`;
2. строит `QikiChatResponseV1` с `proposals`;
3. ORION получает `qiki.responses.qiki`;
4. оператор подтверждает;
5. ORION исполняет:
   - `NATS_COMMAND` -> `qiki.commands.control`;
   - `ORION_PROCEDURE` -> local ProcedureEngine;
6. `q_sim_service` даёт `qiki.responses.control`;
7. ORION обновляет consequence и публикует operator/objective/audit events.

Subjects / handlers:

- `qiki.intents`
- `qiki.responses.qiki`
- `qiki.commands.control`
- `qiki.responses.control`
- `qiki.events.v1.operator.objectives`
- `qiki.events.v1.audit`

Подтверждено кодом:

- [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py)
- [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py)
- [tests/unit/test_qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/tests/unit/test_qiki_orion_intents_service.py)

Что существует только как alternate path:

- intent handling в `faststream_bridge`;
- standalone `qiki.chat.v1`.

Вероятный blocker:

- не функциональный, а канонический: нужно формально закрыть вопрос, что default owner intents = `q-core-intents`.

### 6.4. Observation / review / recheck / resume path

Старт:

- ORION публикует `safe observation ...` или `slow observation ...` в `qiki.intents`.

Цепочка:

1. `q-core-intents` строит safe/slow observation response;
2. при seed публикует `qiki.events.v1.operator.objectives`;
3. для deviation/slow route добавляет `follow_up_status=review_required`;
4. ORION после review публикует `qiki.events.v1.operator.actions`;
5. `q-core-intents` слушает `OPERATOR_ACTIONS` и публикует обновлённый objective payload;
6. ORION видит `hold_for_recheck` или `resume_observation`;
7. после resumed safe observation ORION выполняет procedure и публикует final objective update;
8. результат либо `reconfirmed`, либо `signature_changed`.

Подтверждено кодом:

- [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py)
- [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py)
- [schemas/asyncapi/qiki.events.v1.operator.objectives/v1/payload.schema.json](/home/sonra44/QIKI_DTMP/schemas/asyncapi/qiki.events.v1.operator.objectives/v1/payload.schema.json)
- [tests/unit/test_orion_v_qiki_loop.py](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_qiki_loop.py)

Где возможны разрывы / drift:

- часть contour держится на event feedback между `q-core-intents` и ORION;
- нет отдельного runtime dossier, который бы сводил весь contour в одном месте;
- `signature_changed` live proof не закрыт.

Вероятный blocker:

- именно live proof второго observation result.

### 6.5. Track / telemetry / radar path

Старт:

- `q_sim_service` генерирует radar frame.

Цепочка:

1. `q_sim_service` публикует `qiki.radar.v1.frames`;
2. `faststream_bridge.handle_radar_frame` читает union frames;
3. `frame_to_track()` превращает frame в track;
4. bridge публикует `qiki.radar.v1.tracks`;
5. ORION подписан на `qiki.radar.v1.tracks`;
6. опционально публикуются guard alerts в `qiki.events.v1.radar.guard`.

Подтверждено:

- кодом и tests:
  - [tests/integration/test_radar_flow.py](/home/sonra44/QIKI_DTMP/tests/integration/test_radar_flow.py)
  - [tests/integration/test_radar_tracks_flow.py](/home/sonra44/QIKI_DTMP/tests/integration/test_radar_tracks_flow.py)
  - [tests/integration/test_radar_guard_events.py](/home/sonra44/QIKI_DTMP/tests/integration/test_radar_guard_events.py)

Ambiguity:

- `qiki.radar.v1.tracks.sr` существует как отдельный subject, но default bridge path на него не опирается.

### 6.6. Audit path через `registrar`

Старт:

- любой radar frame или event в `qiki.events.v1.>`.

Цепочка:

1. `registrar` подписывается на `qiki.radar.v1.frames` и `qiki.events.v1.>`;
2. пишет собственный record через `RegistrarService`;
3. публикует `qiki.events.v1.audit`.

Дополнительно:

- ORION сам публикует operator audit events;
- `q-core-intents` публикует hidden observation events в `qiki.events.v1.audit`.

Подтверждено кодом:

- [src/qiki/services/registrar/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/registrar/main.py)

Blocker:

- нужен runtime proof полного audit fan-in/fan-out.

### 6.7. BIOS / status path

Старт:

- `q_bios_service` периодически вычисляет payload.

Цепочка:

1. `q_bios_service` делает gRPC `HealthCheck` к `q-sim-service`;
2. собирает status из bot config + health;
3. отдаёт HTTP `/bios/status`;
4. публикует `qiki.events.v1.bios_status`;
5. `q_core_agent` читает BIOS truth по HTTP `BIOS_URL`.

Подтверждено кодом:

- [src/qiki/services/q_bios_service/main.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_bios_service/main.py)
- [src/qiki/services/q_core_agent/core/bios_http_client.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/bios_http_client.py)

Ambiguity:

- event и HTTP оба существуют одновременно; код `q_core_agent` использует HTTP, а не event stream.

### 6.8. Intent path

Старт:

- `ORION V` -> `qiki.intents`.

Цепочка:

1. `q-core-intents` валидирует `QikiChatRequestV1`;
2. освежает snapshot через `GrpcDataProvider`;
3. строит `QikiChatResponseV1`;
4. иногда публикует `OPERATOR_OBJECTIVES` seed;
5. публикует `qiki.responses.qiki`;
6. ORION получает response и делает local execution path.

Подтверждено кодом:

- [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py)
- [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py)

### 6.9. Отдельно: `signature_changed` live path

Кратко:

- кодовая цепочка есть;
- unit-level path есть;
- schema path есть;
- live proof на current canonical stack не доказан.

Подробный разбор ниже, в отдельном разделе.

## 7. Отдельный разбор `signature_changed`

### 7.1. Где найдено

Код:

- [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py)
- [src/qiki/services/operator_console/orion_v/screens/cockpit.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/screens/cockpit.py)
- [src/qiki/services/operator_console/orion_v/screens/systems.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/screens/systems.py)

Схема/контракт:

- [schemas/asyncapi/qiki.events.v1.operator.objectives/v1/payload.schema.json](/home/sonra44/QIKI_DTMP/schemas/asyncapi/qiki.events.v1.operator.objectives/v1/payload.schema.json)
- [schemas/asyncapi/qiki.events.v1.operator.objectives/v1/README.md](/home/sonra44/QIKI_DTMP/schemas/asyncapi/qiki.events.v1.operator.objectives/v1/README.md)

Tests:

- [tests/unit/test_orion_v_qiki_loop.py](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_qiki_loop.py)
- [tests/unit/test_orion_v_cockpit.py](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_cockpit.py)

Smoke / task dossier:

- [tools/orion_v_qiki_observation_objective_seed_smoke.py](/home/sonra44/QIKI_DTMP/tools/orion_v_qiki_observation_objective_seed_smoke.py)
- [TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md](/home/sonra44/QIKI_DTMP/TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md)

### 7.2. Реальная межсервисная цепочка сценария

1. оператор проходит contour `slow observation` / `review` / `hold_for_recheck` / `resume_observation`;
2. `q-core-intents` на resumed `safe observation` строит `QikiChatResponseV1` с `ORION_PROCEDURE=safe_pause_resume` и кладёт текущий track snapshot в параметры action;
3. ORION выполняет procedure;
4. ORION берёт `current_objective` + refreshed live track snapshot;
5. `_build_resume_observation_result()` сравнивает:
   - тот же `track_id`
   - другой `track_label`
6. если оба условия выполнены, ORION публикует `observation_result_status=signature_changed` в `qiki.events.v1.operator.objectives`;
7. ORION cockpit/systems и QIKI consequence projection отображают этот результат.

### 7.3. Что уже реализовано

- `signature_changed` есть в schema;
- `signature_changed` есть в ORION logic;
- ORION умеет проецировать его в consequence/UI;
- unit tests покрывают same-contour changed-label path;
- smoke harness уже умеет честно падать с явным precondition failure.

### 7.4. Что не доказано на live path

Не доказано:

- что current canonical stack реально даёт same-contour transition:
  - `same track_id`
  - `different non-empty track_label`

По текущему evidence:

- `sim.xpdr.mode=SPOOF` меняет telemetry XPDR truth;
- но не даёт честно доказанный same-contour label flip на resumed observation target.

Основание:

- [tools/orion_v_qiki_observation_objective_seed_smoke.py](/home/sonra44/QIKI_DTMP/tools/orion_v_qiki_observation_objective_seed_smoke.py)
- [TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md](/home/sonra44/QIKI_DTMP/TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md)

### 7.5. Где вероятный текущий blocker

Вероятный blocker находится не в UI-rendering и не в schema, а в live truth chain между:

- `q_sim_service` transponder mode mutation;
- radar truth / track identity continuity;
- `q_core_intents` target-track selection;
- ORION resumed-track snapshot comparison.

Наиболее узкая формулировка blocker:

- current canonical stack не доказывает same-contour `track_label` flip на resumed observation target после `sim.xpdr.mode=SPOOF`.

### 7.6. Какие сервисы участвуют в закрытии blocker

- `q_sim_service`
- `faststream_bridge`
- `q_core_agent.qiki_orion_intents_service`
- `operator_console / ORION V`
- smoke harness в [tools/orion_v_qiki_observation_objective_seed_smoke.py](/home/sonra44/QIKI_DTMP/tools/orion_v_qiki_observation_objective_seed_smoke.py)

### 7.7. Практический вывод для tasking

По `signature_changed` уже можно ставить только задачи вида:

- доказать live trigger;
- локализовать, где теряется same-contour label flip;
- проверить continuity `track_id` / `track_label` между sim truth, bridge truth и ORION snapshot.

Нельзя ставить "закрыть фичу" как будто осталось только UI.

## 8. Главные architectural drifts и blockers

### 8.1. Главные drifts

1. `intent ownership drift`
   - `faststream_bridge` и `q-core-intents` оба умеют intent handling;
   - default contour реально использует только `q-core-intents`.

2. `operator entrypoint drift`
   - ORION V каноничен по compose/docs;
   - Dockerfile default всё ещё legacy `main_orion.py`.

3. `compose contour drift`
   - `phase1` уже включает `q-core-intents`;
   - отдельный overlay для `qcore-intents` остался как transitional artefact.

4. `subject naming drift`
   - `qiki.radar.v1.tracks.sr` по имени неочевиден относительно payload/source.

5. `service role drift`
   - `q_core_agent` как название сервиса покрывает два разных runtime лица.

6. `qiki_chat drift`
   - standalone `qiki.chat.v1` path жив, но не входит в canonical contour.

7. `comment/doc drift`
   - ORION NATS client говорит про control responses от bridge;
   - код показывает publisher = `q_sim_service`.

### 8.2. Главные blockers

1. Не до конца закреплён supported runtime contour.
2. Не формализован single source of truth для intent owner.
3. `signature_changed` остаётся proof-stage.
4. Не собран единый command/subject registry для runtime path.
5. Не сведён audit path в доказательный contour dossier.

## 9. Что нужно сделать по каждому сервису

### `q_sim_service`

- собрать command registry по `apply_control_command`;
- зафиксировать truth subjects и payload owners;
- проверить SR/LR/union naming contract;
- подтвердить supported entrypoint = `grpc_server.py`.

### `q_core_agent`

- разделить runtime роли `main.py` и `qiki_orion_intents_service.py`;
- зафиксировать support tier каждой роли;
- собрать intent/proposal/policy map;
- проверить dependency contract `gRPC + BIOS HTTP + NATS`.

### `faststream_bridge`

- зафиксировать supported role = radar/system_mode;
- пометить intent path как alternate или deprecated-in-runtime;
- собрать JetStream/radar/event map;
- проверить no-double-reply contour.

### `operator_console / ORION V`

- закрепить единственный supported launch path;
- собрать operator execution map;
- собрать observation contour dossier;
- отдельно локализовать `signature_changed` blocker;
- обозначить legacy entrypoints как archival surface.

### `q_bios_service`

- свести HTTP/NATS contracts;
- доказать consumers;
- задокументировать coupling к bot config.

### `registrar`

- собрать audit path dossier;
- проверить recursion guard;
- определить retention/log expectations.

### `qiki_chat`

- решить support tier;
- либо объявить alternate/unsupported;
- либо найти реальных потребителей и дать contour.

### `shell_os`

- зафиксировать support/ops статус;
- описать launch/use cases;
- не смешивать с product operator surface.

## 10. Tasking map для будущих задач агенту

### 10.1. Что уже можно ставить как локальные задачи

- `q_sim_service`: command registry, telemetry/event contract map, radar subject evidence pass.
- `q_core_agent.qiki_orion_intents_service`: intent/proposal/objective map.
- `faststream_bridge`: radar/system_mode passport.
- `operator_console`: ProcedureEngine map, subscription/publication map, observation contour map.
- `q_bios_service`: HTTP/NATS contract audit.
- `registrar`: audit fan-in/fan-out proof.
- `shell_os`: support overlay passport.
- `qiki_chat`: actual usage audit.

### 10.2. Что требует сначала фиксации канонического runtime contour

- любые задачи на перенос intent ownership;
- любые задачи на deprecate/remove `qiki_chat`;
- любые задачи на деактивацию `faststream_bridge.handle_qiki_intent`;
- любые задачи на переименование radar subjects;
- любые задачи на cleanup multiple operator entrypoints;
- любые задачи на перевод ORION procedure execution в отдельный сервис.

### 10.3. P0

- зафиксировать supported runtime contour и single owner `qiki.intents`;
- собрать formal runtime map по `Phase1 + operator`;
- локализовать blocker `signature_changed` на live truth chain;
- собрать command/subject registry по canonical path;
- собрать operator execution map с owners и ack/effect proof.

### 10.4. P1

- audit dossier по `q_bios_service`;
- audit dossier по `registrar`;
- доказательный SR/LR/union radar contract pass;
- cleanup docs/runtime comments drift без изменения behavior;
- support-tier решение для `qiki_chat` и `shell_os`.

### 10.5. P2

- приведение старых compose-файлов и entrypoints к явно archival status;
- унификация docs around supported launch paths;
- optional cleanup tasking после фиксации канона.

### 10.6. Какие задачи опасно ставить вслепую

- "починить intents в bridge";
- "удалить qiki_chat";
- "вынести procedure execution из ORION";
- "переименовать radar topics";
- "убрать legacy operator entrypoints";
- "закрыть signature_changed", не доказав live trigger.

## 11. Рекомендуемый порядок постановки задач

1. Зафиксировать документом supported runtime contour:
   - `Phase1`
   - `Phase1 + operator overlay`
   - owner `q-core-intents`
   - owner control ACK = `q_sim_service`
2. Сделать единый runtime registry:
   - services
   - entrypoints
   - subjects
   - endpoints
   - supported vs alternate paths
3. Сделать operator execution dossier:
   - `qiki.intents -> qiki.responses.qiki -> confirm -> qiki.commands.control / ORION_PROCEDURE -> ack -> telemetry effect`
4. Сделать observation contour dossier:
   - `safe`
   - `slow`
   - `review_required`
   - `hold_for_recheck`
   - `resume_observation`
   - `reconfirmed`
   - `signature_changed`
5. Сделать targeted blocker investigation по `signature_changed`.
6. После этого ставить локальные сервисные задачи:
   - `q_bios_service`
   - `registrar`
   - `shell_os`
   - `qiki_chat`
7. Только после фиксации канона ставить cleanup/deprecation/refactor задачи.

## Итоговый короткий вывод

Проект уже имеет рабочий канонический runtime contour, но поверх него накопились:

- дубли entrypoints;
- transitional compose-файлы;
- alternate intent paths;
- несколько naming/comment drifts.

Для постановки качественных задач это уже достаточная база, но перед любыми архитектурными изменениями нужно сначала формально закрепить:

- supported contour;
- owner intents;
- owner control execution;
- status `signature_changed`.
