# Handover — QIKI_DTMP (2025-12-14)

## Что сделано
- Архивный клон переименован: `/home/sonra44/QIKI_DTMP_LOCAL` → `/home/sonra44/QKDTMPLOC` (чтобы не путать с каноном `/home/sonra44/QIKI_DTMP`).
- Доки/путаница путей:
  - `QIKI_DTMP/README.md` теперь требует работать из git-root (команды `git rev-parse --show-toplevel` для Bash/PowerShell).
  - `QIKI_DTMP/RADAR.md` добавлен как индекс по Radar v1.
  - `QIKI_DTMP/docs/asyncapi/radar_v1.yaml` добавлен как stub AsyncAPI (источник правды — `protos/radar/v1/radar.proto`).
  - `QIKI_DTMP/IMPLEMENTATION_ROADMAP.md` исправлены битые относительные ссылки на RADAR/journal.
  - `QIKI_DTMP/CONTEXT_HANDOVER.md`, `QIKI_DTMP/DOCKER_FIRST_ANALYSIS.md`, `QIKI_DTMP/TECHNICAL_ANALYSIS_GIT_BASH.md` примеры путей обновлены/обобщены; в историческом журнале merge упоминания `QIKI_DTMP_LOCAL` оставлены как история.
- Лаунчеры Operator Console:
  - `QIKI_DTMP/run_console.ps1` теперь self-locating (`$PSScriptRoot`) и запускает консоль через `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml run --rm --build operator-console`.
  - `QIKI_DTMP/run_console.bat` теперь self-locating (`pushd %~dp0`), исправлена проверка запущенности NATS и тоже запускает через compose overlay.
- Compose config проверен: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml config` → OK, только warning: `version` is obsolete.

## Runtime состояние
- Выполнен restart Phase1: `docker compose -f docker-compose.phase1.yml up -d --build`.
- NATS health: `curl -sf http://localhost:8222/healthz` → `{ "status": "ok" }`.
- `qiki-nats-phase1` и `qiki-sim-phase1` healthy; `nats-js-init` exited (one-shot).
- ВАЖНО: стек оставлен поднятым (не `down`).

## TODO_NEXT
1) Уточнить у пользователя: оставить стек поднятым или выполнить `docker compose -f docker-compose.phase1.yml down`.
2) (Опционально) убрать `version:` из `docker-compose.phase1.yml` и `docker-compose.operator.yml` чтобы убрать warnings.
3) После стабилизации доков вернуться к приоритетам (Operator Console / Event Store / Step-A / QoS) по выбору пользователя.
