# QIKI Operator Console — матрица реальных данных (no-mocks policy)

Цель: зафиксировать **что именно** Operator Console показывает, **откуда** это берётся, и **как выглядит пустое состояние**, чтобы на экранах не появлялись “демо‑нули”/фейковые значения.

## Политика (коротко)

- **Никаких заглушек/моков в UI**: в виджетах не рисуем “пример трека”, “0.0 м/с” и т.п.
- Допустимы только:
  - **реальные данные** (NATS/JetStream/gRPC/файлы на диске),
  - **честные статусы** (`not connected`, `no messages yet`, `file not found`),
  - **N/A/—** для неизвестных значений.

## Целевой список экранов/панелей (по практике ground systems)

Основание: Open MCT, COSMOS, Yamcs (типовые роли: телеметрия, тренды, алерты, командование, события, replay).

| Экран/панель | Что отображаем | Нужный источник | Статус сейчас |
|---|---|---|---|
| Header / Status | ONLINE (свежесть), батарея, корпус, радиация, t_ext/t_core, возраст телеметрии | `qiki.telemetry` | есть |
| System / Telemetry | позиция/скорость/курс + базовые сенсоры | `qiki.telemetry` | есть |
| Trends / Graphs | тренды ключевых метрик (battery/temps/rad/velocity) | хранилище истории / replay (JetStream/TSDB) | нет |
| Limits / Alerts | out-of-limits, критические состояния, квитирование | события/лимит‑монитор (будущий) | нет |
| Events / Audit | поток событий и системных сообщений | `qiki.events.v1.>` | есть (подписка) |
| Commands / Procedures | отправка команд + статус выполнения | `qiki.commands.*` / gRPC | частично (sim команды) |
| Navigation / ADCS | ориентация (roll/pitch/yaw), IMU, режимы | телеметрия (`attitude.*`, `sensor_plane.imu.*`) | частично (attitude + IMU rates) |
| Sensors | внутренние сенсоры (IMU/radiation/proximity/solar/star tracker/magnetometer) | телеметрия (`sensor_plane.*`) | частично (IMU+radiation) |
| Power / EPS | SoC, power-in/out, PDU статусы, supercap, dock, NBL | `qiki.telemetry` | есть |
| Thermal | узлы температур + аварии перегрева | `qiki.telemetry` | есть |
| Propulsion / RCS | команда РДС, сопла (duty/valve), пропеллант, RCS power | `qiki.telemetry` (`propulsion.rcs.*`) + `qiki.commands.control` (`sim.rcs.*`) | есть (RCS) |
| Comms / Link | uplink/downlink, качество канала | телеметрия/сервис связи | нет |
| Radar / Perception | треки/кадры/угрозы | `qiki.radar.v1.*` | частично (tracks) |
| Docking / Bridge | статусы байонета, питание, мост | телеметрия (power.* + docking.*) + команды `power.dock.*`/`sim.dock.*` | частично |
| Replay / History | история телеметрии/событий | JetStream / TSDB | нет |

## MVP Phase 1 (только то, что реально доступно)

Фиксируем минимальный набор экранов/панелей, который разрешён к показу **сейчас**:

- Header / Status (ONLINE + свежесть, батарея, корпус, радиация, t_ext/t_core)
- System / Telemetry (позиция X/Y/Z, скорость, курс, ориентация roll/pitch/yaw, батарея, корпус, радиация, температуры, thermal nodes)
- Radar / Perception (tracks)
- Events / Logs (поток событий)
- Command Dock (sim команды и ответы)
- Power / EPS (шина, SoC, PDU, supercap, dock, NBL)
- Thermal (узлы температур, перегревы)
- Propulsion / RCS (только если телеметрия содержит `propulsion.rcs.*`)

Никакие другие панели не считаются активными, пока не появятся реальные источники.

## Матрица источников

| Экран/панель | Что показываем | Источник | Контракт/формат | Пустое состояние (честно) |
|---|---|---|---|---|
| Telemetry | позиция/скорость/курс/ориентация/батарея/корпус/радиация/температуры + Thermal nodes + Power Plane (soc, power in/out, шина, PDU/shed/faults, supercap, dock, NBL) + **MCQPU CPU/RAM (виртуальные, simulation-truth)** + (опц.) `propulsion.rcs.*` | NATS subject `qiki.telemetry` (`SYSTEM_TELEMETRY`) | JSON dict (TelemetrySnapshot v1; ключи: `schema_version=1`, `source`, `timestamp`, `ts_unix_ms`, `position.{x,y,z}`, `velocity`, `heading` (deg), `attitude.roll_rad`, `attitude.pitch_rad`, `attitude.yaw_rad` (rad), `battery`, `cpu_usage`, `memory_usage`, `hull.integrity`, `thermal.nodes[].{id,temp_c}`, `power.*` (см. модель), `radiation_usvh`, `temp_external_c`, `temp_core_c`; доп. ключи допустимы) | Таблица со строками‑метриками и значениями `N/A`, `Updated=—`; статус: `waiting for telemetry` |
| Radar Tracks | треки (id, range_m, bearing_deg, vr_mps, object_type/iff/quality/status если есть) | JetStream subject `qiki.radar.v1.tracks` (`RADAR_TRACKS`) | JSON → `qiki.shared.models.radar.RadarTrackModel` | Пустая таблица или 1 строка‑статус: `no tracks yet`; соединение NATS/JS отдельно |
| Radar Frames (опц.) | кадры радара (кол-во детекций, sensor_id, timestamp) | NATS/JetStream subject `qiki.radar.v1.frames` (`RADAR_FRAMES`) и/или `qiki.radar.v1.frames.lr` (`RADAR_FRAMES_LR`) | JSON → `qiki.shared.models.radar.RadarFrameModel` | `no frames yet` |
| Events / Audit (опц.) | guard/fsm/audit события | NATS subject `qiki.events.v1.>` (`EVENTS_V1_WILDCARD`), audit `qiki.events.v1.audit` | JSON (CloudEvents headers могут присутствовать) | `no events yet` |
| Quick Commands | старт/пауза/стоп/ресет (и др. команды) | gRPC в Q‑Sim Service (host/port из env) | пока “soft” client без сгенерённых stub’ов; health по состоянию канала | Кнопки доступны, но при `not connected` → лог + уведомление |
| Agent Chat | обмен сообщениями с Q‑Core Agent | gRPC в Q‑Core Agent (host/port из env) | зависит от будущих stub’ов; сейчас best‑effort client | `agent not connected` |
| Profile | BotSpec + hardware profile + “source of truth” документ | Файлы репо: `shared/specs/BotSpec.yaml`, `config/propulsion/thrusters.json`, `src/qiki/services/q_core_agent/config/bot_config.json`, `docs/design/hardware_and_physics/bot_source_of_truth.md` | чтение с диска (read-only) | `repo root not found` / `file not found` / `unavailable` |

## ENV-переменные, которые UI использует

- `NATS_URL` (пример: `nats://qiki-nats-phase1:4222`)
- `RADAR_TRACKS_SUBJECT` (опц., дефолт `qiki.radar.v1.tracks`)
- `RADAR_LR_SUBJECT` / `RADAR_SR_SUBJECT` (опц.)
- `GRPC_HOST` / `GRPC_PORT` (Q‑Sim)
- `AGENT_GRPC_HOST` / `AGENT_GRPC_PORT` (Q‑Core Agent, если отдельный endpoint)
- `QIKI_REPO_ROOT` (для Profile панели; в docker overlay это `/workspace`)
