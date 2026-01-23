# Truth Table: текущая архитектура Phase1 (QIKI_DTMP)

Дата: 2026-01-23  
Статус: factual snapshot + gaps (не канон приоритетов)  

Цель: зафиксировать “что правда сейчас” по стеку Phase1: сервисы, контракты, subjects/streams, точки входа и наблюдаемые симптомы.

## Evidence (как было проверено)

- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml config --services`
- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps`
- `docker logs --tail=120 qiki-nats-js-init`
- `docker logs --tail=120 qiki-faststream-bridge-phase1`
- Serena: чтение `docker-compose.phase1.yml`, `docker-compose.operator.yml`, `src/qiki/shared/nats_subjects.py`, ключевых файлов сервисов.

## 1) Runtime stack (Docker compose)

### 1.1 Сервисы (compose `--services`)

- `nats` (JetStream, monitoring `:8222`)
- `nats-js-init` (инициализация JetStream streams + durables)
- `q-sim-service` (gRPC `:50051`, simulation + telemetry publish)
- `q-sim-radar` (radar frame generation/publish)
- `faststream-bridge` (FastStream/NATS: bridge + radar processing + intents)
- `q-bios-service` (HTTP `:8080` + NATS publish bios_status)
- `qiki-dev` (Q-Core agent)
- `operator-console` (ORION TUI)
- observability: `loki`, `promtail`, `grafana`
- `registrar` (audit/events)

### 1.2 Контейнеры “живые сейчас” (compose `ps`)

Сейчас поднято:

- `qiki-nats-phase1` (healthy), порты `4222`, `8222`
- `qiki-nats-js-init` (completed/ran ранее)
- `qiki-sim-phase1` (q-sim-service, healthy)
- `qiki-sim-radar-phase1` (q-sim-radar, running)
- `qiki-faststream-bridge-phase1` (running)
- `qiki-bios-phase1` (healthy), проброс `127.0.0.1:8080->8080`
- `qiki-dev-phase1` (running)
- `qiki-operator-console` (healthy)

## 2) Канонические NATS имена (subjects/streams/durables)

Источник: `src/qiki/shared/nats_subjects.py`

### 2.1 Streams

- `QIKI_RADAR_V1`
- `QIKI_EVENTS_V1`

### 2.2 JetStream durables (ядро + ORION)

- `radar_frames_pull`
- `radar_tracks_pull`
- `operator-console-sr`
- `operator-console-lr`
- `operator-console-tracks`

### 2.3 Subjects

- Radar:
  - `qiki.radar.v1.frames`
  - `qiki.radar.v1.frames.lr`
  - `qiki.radar.v1.tracks`
  - `qiki.radar.v1.tracks.sr`
- Telemetry:
  - `qiki.telemetry`
- Control:
  - `qiki.commands.control`
  - `qiki.responses.control`
- QIKI intents/replies:
  - `qiki.intents`
  - `qiki.responses.qiki`
- Events:
  - `qiki.events.v1.>`
  - `qiki.events.v1.audit`

## 3) JetStream init (реальный контракт streams/consumers)

Источник: `tools/js_init.py` + env в `docker-compose.phase1.yml` (`nats-js-init`).

- Radar stream:
  - `RADAR_STREAM=QIKI_RADAR_V1`
  - `RADAR_SUBJECTS=qiki.radar.v1.*`
  - Durables: `radar_frames_pull` (filter `qiki.radar.v1.frames`), `radar_tracks_pull` (filter `qiki.radar.v1.tracks`)
- Events stream:
  - `EVENTS_STREAM=QIKI_EVENTS_V1`
  - `EVENTS_SUBJECTS=qiki.events.v1.>`
  - Audit durable: `events_audit_pull` (filter `qiki.events.v1.audit`)

Observed evidence: `docker logs qiki-nats-js-init` печатает `JetStream stream  updated`.

## 4) Контракты между сервисами

### 4.1 gRPC: Q-Sim API

Реальность (код):

- `src/qiki/services/q_sim_service/grpc_server.py` поднимает gRPC на `:50051`
- Методы (по реализациям/генерёнке):
  - `HealthCheck(HealthCheckRequest) -> HealthCheckResponse(status="SERVING")`
  - `GetSensorData(GetSensorDataRequest) -> GetSensorDataResponse(reading=...)`
  - `SendActuatorCommand(...)` (см. generated API; используется Q-Core)

Док‑референс: `docs/analysis/protos_q_sim_api.proto.md` (proto в `proto/` сейчас отсутствует/пустой; контракт живёт в `generated/*`).

### 4.2 HTTP: Q-BIOS service

Реальность (код):

Файл `src/qiki/services/q_bios_service/handlers.py`:
- `GET /healthz` → `{ok: true}`
- `GET /bios/status` → JSON status payload
- иначе → 404

Публикация событий BIOS в NATS:
- `docker-compose.phase1.yml` задаёт:
  - `NATS_EVENT_SUBJECT=qiki.events.v1.bios_status`
  - `BIOS_PUBLISH_ENABLED=1`
  - `BIOS_PUBLISH_INTERVAL_SEC=5.0`

Наблюдение (важно): в tail логов `qiki-bios-phase1` есть `WARNING:q_bios_service:NATS publish failed: nats: no servers available for connection`.
Это требует отдельного расследования (см. Gaps).

### 4.3 NATS: FastStream bridge

Источник: `src/qiki/services/faststream_bridge/app.py`

- Sub/Pub control:
  - subscribe: `qiki.commands.control`
  - publish: `qiki.responses.control`
- Sub/Pub QIKI intents:
  - subscribe: `qiki.intents`
  - publish: `qiki.responses.qiki`
- Radar ingest:
  - subscribe (JetStream pull): `qiki.radar.v1.frames` (`durable=radar_frames_pull`, `stream=QIKI_RADAR_V1`)
  - publish tracks via `RadarTrackPublisher` на `qiki.radar.v1.tracks`

Observed evidence: в `docker logs qiki-faststream-bridge-phase1` постоянно идут строки вида
`QIKI_RADAR_V1 | qiki.radar.v1.frames | ... - Radar frame received ... - Processed`.

### 4.4 NATS: ORION operator console

Источник: `docker-compose.operator.yml` + `src/qiki/services/operator_console/main_orion.py` + `src/qiki/services/operator_console/clients/nats_client.py`.

Подписки:
- system telemetry: `qiki.telemetry` (plain NATS)
- events wildcard: `qiki.events.v1.>` (plain NATS)
- control responses: `qiki.responses.control` (plain NATS)
- QIKI responses: `qiki.responses.qiki` (plain NATS)
- radar/tracks (JetStream): subject’ы `qiki.radar.v1.tracks.sr`, `qiki.radar.v1.frames.lr`, `qiki.radar.v1.tracks` с durables:
  - `operator-console-sr`
  - `operator-console-lr`
  - `operator-console-tracks`

Публикации:
- QIKI intent: publish на `qiki.intents` (см. `main_orion.py` — отправка `req` в `QIKI_INTENTS`)
- control: publish на `qiki.commands.control`

Замечание: `docker logs qiki-operator-console` практически не пригоден для анализа (там TUI escape sequences). Для диагностики ORION лучше использовать tmux `capture-pane` в панели, где запущен ORION, либо отдельный file-logger.

### 4.5 NATS: Q-Sim control commands consumer

Источник: `src/qiki/services/q_sim_service/grpc_server.py`

- Есть background loop, который (если `CONTROL_NATS_ENABLED` не выключен) подписывается на `qiki.commands.control` и применяет команды через `sim_service.apply_control_command`.

## 5) “Слои ОС” (как это выглядит в реальном коде)

PDF-идея “boot → kernel → services/drivers → modules → UI” можно сопоставить так:

- “Boot layer” (реальность): порядок старта контейнеров/healthchecks в compose + `nats-js-init` (подготовка streams/durables).
- “Kernel” (реальность): `qiki-dev` (Q-Core agent) с tick loop:
  - `src/qiki/services/q_core_agent/core/tick_orchestrator.py`: update_context → handle_bios → handle_fsm → evaluate_proposals → make_decision.
- “Drivers/Services” (реальность): `q-bios-service`, `q-sim-service`, `faststream-bridge`, `registrar`.
- “Modules” (реальность): radar publisher (`q-sim-radar`), rule/neural modules внутри Q-Core (см. `docs/analysis/*`).
- “UI” (реальность): `operator-console` (ORION TUI).

## 6) Gaps / риски (то, что стоит улучшать дальше)

1) BIOS NATS publish reliability:
   - Есть observed `NATS publish failed` в логах BIOS при том, что NATS healthy.
   - Нужно понять: это только при старте/перезапуске или постоянная проблема; добавить backoff/retry/логирование причины.
2) BIOS HTTP endpoints vs “идея из PDF”:
   - Сейчас реально только `/healthz` и `/bios/status`. Если нам нужны `hot_reload_config`/`soft_reboot` и per-component status — это отдельный контракт/задача.
3) ORION observability:
   - `docker logs` не читаем из-за TUI. Нужен отдельный диагностический вывод (file logger) или формальный способ capture (tmux).
4) Plug-and-play:
   - Сейчас есть конфиг‑driven загрузка (`bot_config.json`), но нет явного “module registry/discovery” слоя. Решать, нужен ли он и какой минимальный контракт.

## 7) Next action (привязка к плану)

Дальше: выбрать 1 gap (лучший кандидат сейчас — BIOS NATS publish reliability, потому что это “факт‑симптом”) и открыть отдельную задачу/PR с чётким DoD и evidence.

