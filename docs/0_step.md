Ок. Ниже — жёсткий, исполнимый промт для реализации Этап-0 (Каркас). Это не «описание», а чек-лист + заготовки кода/контрактов. Делай по пунктам — получишь стабильный фундамент, куда потом безболезненно воткнём радар, фьюжн и всё остальное.

Цель Этап-0

Зафиксировать интерфейсы и шину событий так, чтобы любой последующий модуль (радар, фьюжн, PXE, UI) подключался без правки контрактов.

Выходные артефакты (DoD)

shared/specs/BotSpec.yaml (+ валидатор).

.proto пакеты: qiki.common.v1, qiki.sensors.v1, qiki.control.v1, qiki.events.v1, qiki.api.v1.

gRPC сервис QSimAPIService (stream данных/команд) — пустые заглушки работают.

EventBus (NATS/JetStream) с темами/ключами/ретеншенами, без бизнес-логики.

Registrar (audit-лог, коды 1xx…9xx) — пишет события.

Health/metrics (Prometheus) — базовые метрики и лейблы.

CI: линт/тайпчек/юниты + docker-compose поднимает «минимальную вселенную» и закрывает acceptance.

Структура репозитория (минимум)
shared/
  specs/BotSpec.yaml
  models/          # pydantic + converters (proto<->py)
  registrar/       # event schema + sink
protos/
  qiki/common/v1/common.proto
  qiki/sensors/v1/sensors.proto
  qiki/control/v1/control.proto
  qiki/events/v1/events.proto
  qiki/api/v1/api.proto
services/
  q_sim_service/       # сим-заглушка (источник данных)
  q_core_agent/        # мозг-заглушка (подписчик/эмиттер событий)
  faststream_bridge/   # NATS/JetStream мост
ops/
  docker-compose.yml
  nats/jetstream-init.sh
  prometheus/prometheus.yml
tests/
  e2e/test_bootstrap.py

BotSpec (зафиксировать схему, без цифр)

shared/specs/BotSpec.yaml — сухая спецификация компонентов и их портов (как в наших черновиках). Для Этап-0 достаточно каркаса:

version: 1
kind: BotSpec
metadata:
  id: QIKI-DODECA-01
components:
  hull:        { type: structure, provides: [collision_mesh, hardpoints[]] }
  power:       { type: dc_bus,  provides: [dc_out, energy_status] }
  propulsion:  { type: propulsors, provides: [motion_command] }
  sensors:     { type: sensing_suite, provides: [sensor_frame] }
  comms:       { type: datalink }
  shields:     { type: defensive, provides: [shield_status] }
  navigation:  { type: nav_stack, provides: [nav_state] }
  protocols:   { type: executor }
event_bus:
  channels: [SensorFrame, TrackSet, ProtocolCmd, EnergyStatus, ShieldStatus, NavState, RegistrarEvent]


Валидатор (pydantic) должен:

проверять наличие обязательных provides/consumes;

маппить BotSpec к runtime-конфигам (services/*/config/*.json).

Контракты .proto (заморозить)
1) Общие типы

protos/qiki/common/v1/common.proto

syntax = "proto3";
package qiki.common.v1;

message TimestampMono { uint64 nanos = 1; }   // монотоник
message Vec3 { double x = 1; double y = 2; double z = 3; }
message Pose3 { Vec3 pos = 1; Vec3 vel = 2; Vec3 euler = 3; Vec3 omega = 4; }
message ULID { string value = 1; }

2) Сенсоры (без LR/SR логики, но с запасом на будущее)

protos/qiki/sensors/v1/sensors.proto

syntax = "proto3";
package qiki.sensors.v1;
import "qiki/common/v1/common.proto";

enum RadarBand { RADAR_BAND_UNKNOWN = 0; RADAR_BAND_LR = 1; RADAR_BAND_SR = 2; }

message RadarDetection {
  qiki.common.v1.TimestampMono t = 1;
  double bearing = 2;    // рад
  double elevation = 3;  // рад
  double range = 4;      // м
  double snr = 5;
  bool   id_present = 6; // для SR будущем
  string id_hint   = 7;  // транспондер/iff (может быть пустым)
  RadarBand band   = 8;  // LR|SR|UNKNOWN
}

message RadarFrame {
  qiki.common.v1.TimestampMono t = 1;
  repeated RadarDetection det = 2;
  qiki.common.v1.Pose3 ego   = 3;
}

message Track {
  qiki.common.v1.ULID id   = 1;
  qiki.common.v1.TimestampMono t = 2;
  qiki.common.v1.Pose3 state = 3;  // pos/vel + yaw/pitch/roll/omega
  double quality = 4;              // 0..1, ковариации позже
  string source  = 5;              // "radar_lr", "radar_sr", "fusion"
  bool id_present = 6;
  string iff_id   = 7;
}

message TrackSet {
  qiki.common.v1.TimestampMono t = 1;
  repeated Track tracks = 2;
}

message EnergyStatus { double p_avail = 1; double p_peak = 2; }
message ShieldStatus { double sectors[4] = 1; }
message NavState { qiki.common.v1.Pose3 ego = 1; }

3) Управление

protos/qiki/control/v1/control.proto

syntax = "proto3";
package qiki.control.v1;
import "qiki/common/v1/common.proto";

enum FlightMode { FM_RAW = 0; FM_IDS = 1; }

message ThrusterCmd { uint32 index = 1; double force = 2; double duration = 3; }
message MotionCmdIDS { qiki.common.v1.Vec3 v_target = 1; qiki.common.v1.Vec3 omega_target = 2; }
message ModeCmd { FlightMode mode = 1; }

message ProtocolCmd {
  string name = 1;                // EVASIVE_BURN, ...
  map<string,string> params = 2;  // простая параметризация
}

4) События/коды (Registrar)

protos/qiki/events/v1/events.proto

syntax = "proto3";
package qiki.events.v1;
import "qiki/common/v1/common.proto";

enum Severity { EVT_INFO=0; EVT_WARN=1; EVT_ERROR=2; EVT_EMERG=3; }

message Event {
  qiki.common.v1.ULID id = 1;
  qiki.common.v1.TimestampMono t = 2;
  string src = 3;        // компонент
  uint32 code = 4;       // 1xx..9xx
  Severity severity = 5;
  string  msg = 6;
  bytes   payload = 7;   // опционально
}

5) gRPC API

protos/qiki/api/v1/api.proto

syntax = "proto3";
package qiki.api.v1;
import "qiki/sensors/v1/sensors.proto";
import "qiki/control/v1/control.proto";

service QSimAPIService {
  rpc StreamRadarFrames(google.protobuf.Empty) returns (stream qiki.sensors.v1.RadarFrame);
  rpc StreamTracks(google.protobuf.Empty) returns (stream qiki.sensors.v1.TrackSet);
  rpc SendThrusterCmd(stream qiki.control.v1.ThrusterCmd) returns (google.protobuf.Empty);
  rpc SetMode(qiki.control.v1.ModeCmd) returns (google.protobuf.Empty);
  rpc SendProtocol(qiki.control.v1.ProtocolCmd) returns (google.protobuf.Empty);
}

EventBus (NATS/JetStream) — темы/ключи

Сенсоры:

qiki.sensors.v1.frames (JSON/proto) — ключ radar, header Nats-Msg-Id для dedup.

qiki.sensors.v1.tracks — агрегированные треки.

Состояния:

qiki.status.v1.energy, qiki.status.v1.shields, qiki.status.v1.nav.

Команды:

qiki.control.v1.thruster (pub-sub, stream), qiki.control.v1.mode, qiki.control.v1.protocol.

События/лог:

qiki.events.v1.audit (persist), ретеншен JetStream: work-queue + max_age.

ops/nats/jetstream-init.sh — создаёт стримы/консьюмеров, задаёт ack_wait, max_deliver, retention=limits, discard=old.

Registrar (audit-лог)

Сервис-синглтон пишет всё значимое в qiki.events.v1.audit и локальный файл (rotating).

Коды по диапазонам:

1xx — bootstrap/health, 2xx — sensor IO, 3xx — control IO,

5xx — faults, 7xx — guard triggers, 9xx — emergency/abort.

Observability (минимум)

Prometheus метрики:

qiki_bus_msg_in_total{topic=...}, qiki_bus_msg_out_total{topic=...}

qiki_frame_latency_ms (сим→агент), qiki_stream_backpressure

qiki_registrar_events_total{severity,code}

Health: /healthz в каждом сервисе: OK + версия гита.

Сервисные заглушки (рабочий скелет)
q_sim_service (источник данных)

Таймер → формирует пустой RadarFrame (пока без физики), паблишит в NATS и стримит через gRPC.

Экспорт метрик.

q_core_agent (подписчик)

Подписывается на qiki.sensors.v1.frames, транслирует в TrackSet (просто копирует/оборачивает).

Принимает ModeCmd/ThrusterCmd/ProtocolCmd (логирует в Registrar).

faststream_bridge

Гейт между NATS EventBus и gRPC стримами (двунаправленно).

Контролируемый back-pressure (буферы/ограничители).

Конфиг/Фичи-флаги

QIKI_FEATURE_EMCON=false (пока не используется).

Частоты публикации кадров, лимиты JetStream — из env (12-фактор).

CI/CD (минимум)

ruff, mypy, pytest -q.

Генерация протобафов, проверка, что сервисы поднимаются из docker-compose up -d и healthz → 200.

E2E: тест, который подписывается на qiki.sensors.v1.frames и ждёт ≥1 кадра ≤2с; проверяет запись в qiki.events.v1.audit.

Acceptance Этап-0

docker-compose up поднимает: NATS, faststream_bridge, q_sim_service, q_core_agent, registrar, prometheus.

Команда make smoke проходит:

gRPC StreamRadarFrames отдаёт поток (пусть пустых детекций).

NATS на qiki.sensors.v1.frames получает ≥1 сообщение.

Registrar пишет событие 1xx BOOT_OK, 2xx SENSOR_IO_OK.

Метрики доступны на /metrics.

Ни одной «жёсткой» цифры или бизнес-логики сенсоров пока нет — только каркас.

Порядок выполнения (день-за-днём)

Смёржить .proto и сгенерить Python-артефакты.

Написать BotSpec валидатор (pydantic) + загрузчик профилей.

Поднять NATS/JetStream + скрипт инициализации.

Реализовать q_sim_service (таймер → пустые кадры).

Реализовать faststream_bridge (NATS↔gRPC, 2 темы туда/сюда).

Реализовать q_core_agent (подписка на frames → publish TrackSet).

Подключить Registrar, коды/формат событий.

Метрики/healthz, композ, e2e тест.

Важные инварианты (забить в код)

Стабильность контрактов: после Этап-0 .proto менять нельзя (только расширять через новые поля/oneof).

Идемпотентность в шине: Nats-Msg-Id + дедуп в консьюмерах.

Back-pressure: стримы не душат сервисы (лимиты буферов, drop-политика «latest wins» только на UI-ветке).

Traceability: каждое значимое событие → Registrar (ULID, монотоник).