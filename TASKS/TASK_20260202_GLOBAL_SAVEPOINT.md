# GLOBAL SAVEPOINT — ORION/QIKI_DTMP (2026-02-02)

Цель файла: зафиксировать «точку мира» (логика + доказательства + что дальше), чтобы не потерять контекст между перезапусками/сессиями.  
Правило: без v2/дублей, no-mocks, Docker-first, Serena-first.

## Репо / Git (единая база)

- `HEAD`: `d753d0f19f06ec17bb061a648030d5f8451ea510`
- `origin/main == origin/master == d753d0f19f06ec17bb061a648030d5f8451ea510`

## Инварианты (нерушимые)

- **No-mocks:** если данных нет — честное `N/A/—`, никаких подстановок.
- **No v2 / no duplicate NATS subjects:** расширяем существующие контракты backward-compatible.
- **Docker-first:** сборка/тесты/пруфы в Docker.
- **Serena-first:** поиск/правки через Serena.
- **Последовательность:** один вертикальный срез за раз.

## Что сделано в этой цепочке (последовательно, P0)

### 1) ORION Record/Replay control surface (локально, без новых контрактов)

- ORION поддерживает команды:
  - `record start [path] [duration_s]`
  - `record stop`
  - `replay <path> [speed=...] [prefix=...] [no_timing]`
  - `replay stop`
- Запись подписывается только на существующие subject’ы:
  - `qiki.telemetry`
  - `qiki.events.v1.>`
  - `qiki.radar.v1.tracks`
  - `qiki.responses.control`
- Реплей по умолчанию публикует обратно в исходные subject’ы; `prefix=...` — только для отладочной изоляции.

Файлы:
- `src/qiki/services/operator_console/main_orion.py`
- `src/qiki/services/operator_console/tests/test_record_replay_commands.py`

### 2) Live smoke Record/Replay (доказано на Phase1)

Команды в ORION:
- `record start /tmp/session.jsonl 5` → `Record started` → `Record finished`
- `replay /tmp/session.jsonl no_timing` → `Replay finished`

Пруфы:
- Файл создан внутри контейнера `qiki-operator-console`: `/tmp/session.jsonl` (~47 строк), содержит `ts_epoch` + `ts_ingest_epoch`.

### 3) Fix: `Mode/Режим` не зависает в `N/A` после рестарта

Проблема (доказано):
- ORION гидрирует режим через JetStream (`QIKI_EVENTS_V1`), но `qiki.events.v1.system_mode` не был персистентен:
  - `js.get_last_msg(QIKI_EVENTS_V1, qiki.events.v1.system_mode)` → `404/10037 no message found`
  - Поэтому после рестарта ORION мог остаться `Mode N/A` до ручной смены режима.

Решение:
- `faststream-bridge` публикует system_mode через JetStream publish (`stream=QIKI_EVENTS_V1`) + fallback на core-NATS.

Файлы:
- `src/qiki/services/faststream_bridge/app.py`
- `tests/unit/test_system_mode_boot_event.py`
- `tests/integration/test_system_mode_boot_event_stream.py` (в текущем виде может `skip`, если стэк не рестартился)

## Текущий стек (Phase1)

Команда:
- `docker compose -f docker-compose.phase1.yml ps`

Оверлей ORION:
- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console`

## Как продолжить (следующий шаг по плану)

Сделать доказательство system_mode boot «каноничным»:
1) Обновить `docs/RESTART_CHECKLIST.md`: добавить шаг проверки `js.get_last_msg(QIKI_EVENTS_V1, qiki.events.v1.system_mode)`.
2) Добавить/привести smoke-утилиту (если уже есть) `tools/system_mode_smoke.py`, чтобы после рестарта печатала `OK mode=...`.
3) После `docker compose ... up -d --build` запускать smoke и сохранять как пруф.

