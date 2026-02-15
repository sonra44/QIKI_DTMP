# TASK-0031 — Multi-Console Distributed Mode (Shared Radar Session)

## Что сделано
- Добавлен transport v1 на TCP JSON-lines:
  - `src/qiki/services/q_core_agent/core/session_server.py`
  - `src/qiki/services/q_core_agent/core/session_client.py`
- Реализован протокол сообщений:
  - `HELLO`, `STATE_SNAPSHOT`, `EVENT`
  - `CONTROL_REQUEST`, `CONTROL_GRANTED`, `CONTROL_RELEASE`
  - `HEARTBEAT`, `ERROR`
- В `MissionControlTerminal` добавлены режимы:
  - `QIKI_SESSION_MODE=standalone|server|client`
  - server запускает session server и стримит shared feed
- client подписывается, рендерит удалённый snapshot/events, при разрыве показывает `NO_DATA / SESSION LOST`
- D1: при disconnect клиент немедленно переводится в `truth_state=NO_DATA`, `session_lost=True`, HUD содержит `SESSION LOST`.
- D1: клиент эмитит `SESSION_LOST` в EventStore с `{client_id, ts, reason}`.

## Lease и управление вводом
- На сервере одновременно один controller.
- `CONTROL_GRANTED` выдаётся с lease (`lease_ms`), heartbeat продлевает lease.
- При просрочке heartbeat сервер эмитит `CONTROL_EXPIRED`, снимает контроль и рассылает `CONTROL_RELEASE`.
- D2: контроль lease проверяется отдельным timer-loop (`lease_check_ms`), а не только по heartbeat.
- D2: при истечении lease без heartbeat сервер рассылает `CONTROL_EXPIRED` и пишет `CONTROL_EXPIRED` в EventStore.
- Команды ввода от не-controller отклоняются с `ERROR(code=not_controller)`.

## EventStore интеграция
- Сервер пишет server-side lifecycle события в `EventStore`:
  - `CONTROL_GRANTED`
  - `CONTROL_RELEASED`
  - `CONTROL_REVOKED`
  - `CONTROL_EXPIRED`
- Клиент не подменяет truth: при disconnect публикуется локальный snapshot с `truth_state=NO_DATA`.

## Plugin architecture интеграция
- Добавлены plugin kinds:
  - `session_transport`
  - `input_router`
- Встроенные реализации зарегистрированы в `radar_plugins.py`.
- Обновлены профили в `src/qiki/resources/plugins.yaml`:
  - default/sim/dev/prod/production/no_situational
  - `multiconsole_server`
  - `multiconsole_client`

## ENV knobs
- `QIKI_SESSION_MODE` (`standalone|server|client`)
- `QIKI_SESSION_HOST` (default `127.0.0.1`)
- `QIKI_SESSION_PORT` (default `8765`)
- `QIKI_SESSION_CLIENT_ID` (default `<hostname>-<pid>`)

## Ручная проверка
1. Сервер:
```bash
QIKI_SESSION_MODE=server python -m qiki.mission_control_terminal --real-input
```
2. Клиент #1:
```bash
QIKI_SESSION_MODE=client QIKI_SESSION_CLIENT_ID=op-1 python -m qiki.mission_control_terminal --real-input
```
3. Клиент #2:
```bash
QIKI_SESSION_MODE=client QIKI_SESSION_CLIENT_ID=op-2 python -m qiki.mission_control_terminal --real-input
```
4. Проверка handover:
- запросить контроль с клиента 1
- отправить input с клиента 2 → `ERROR not_controller`
- release с клиента 1, запрос с клиента 2 → `CONTROL_GRANTED`

## Ограничения v1
- Transport без auth/TLS (локальный режим).
- Snapshot compact, без полной сериализации pipeline internals.
- Client mode рендерит shared feed, но не выполняет ingest/fusion/situational локально.
