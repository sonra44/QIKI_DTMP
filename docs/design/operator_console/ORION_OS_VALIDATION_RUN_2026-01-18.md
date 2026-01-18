# ORION Shell OS — Validation Run (2026-01-18)

Цель: зафиксировать воспроизводимую проверку ORION в Docker по чеклисту `ORION_OS_VALIDATION_CHECKLIST.md`.

Дата: 2026-01-18  
Окружение: Docker Compose (`docker-compose.phase1.yml` + `docker-compose.operator.yml`)

## 0) Preflight (runtime)

- ✅ Run via Docker:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console q-bios-service q-sim-service nats`
- ✅ Health (compose):
  - `nats` — `healthy`
  - `q-sim-service` — `healthy`
  - `operator-console` — `healthy`
  - `q-bios-service` — `healthy`
- ✅ BIOS доступен (HTTP):
  - `curl -fsS http://localhost:8080/healthz` → `{"ok": true}`
  - `curl -fsS http://localhost:8080/bios/status` → валидный `BiosStatus` JSON
- ✅ BIOS публикует события в NATS (no-mocks):
  - subject: `qiki.events.v1.bios_status`
  - проверка подпиской из `qiki-dev`: событие получено, `all_systems_go=True`, `post_results_len=23`

## 1) Global invariants (must always hold)

- ✅ Missing data показывается как `N/A/—` (в логах TUI видно `Bus/Шина N/A/—`, `Radiator/Радиатор N/A/—` и т.п.)
- ✅ Авто-тесты operator_console прошли (`pytest`): i18n/лейблы/структура компонентов/инциденты/правила/статус-бар
- ⚠️ Tmux resize stability — требуется ручная валидация (см. чеклист раздел 5)

## 2) Input/Output dock (calm operator loop)

- ✅ Авто-тесты проходят (фокус/маршрутизация/QIKI routing/UI components)
- ⚠️ Визуальная проверка “typed text visibility + overflow” — требуется ручная валидация (TUI)

## 3) Events/События — incidents workflow

- ✅ Авто-тесты проходят (pause/unread, store, rules, toggle in app)
- ⚠️ Ручная проверка hotkeys (`F3`, `Ctrl+Y`, `A`, `X`, `R`) — рекомендуется при следующем интерактивном прогоне

## 4) Inspector/Инспектор contract

- ✅ Авто-тесты проходят (структура/компоненты)
- ⚠️ Ручная проверка selection-driven поведения — рекомендуется

## 5) Chrome stability under tmux resizing

- ⚠️ Требуется ручная валидация в tmux (узкий/широкий терминал, низкая высота)

## 6) Non-priority radar safety

- ✅ Авто-тесты operator_console прошли; крэша при загрузке не видно по логам
- ⚠️ Ручное подтверждение `F2` “не падает” — рекомендуется

## 7) Rules/Правила — quick enable/disable + reload

- ✅ Авто-тесты проходят (incident_rules + toggle in app)
- ⚠️ Ручная проверка “Reload rules/Перезагрузить правила” кнопкой — рекомендуется

## Smoke результаты (сухой остаток)

- Стек поднимается и живой.
- BIOS сервис отвечает по HTTP и публикует `qiki.events.v1.bios_status` (no-mocks).
- Авто-тесты ORION/BIOS/sim проходят.

## Post-run hardening (после прогона)

- Порт BIOS на хосте ограничен до loopback, чтобы не ловить внешние сканеры:
  - `docker-compose.phase1.yml`: `127.0.0.1:8080:8080` (внутри docker-сети доступ по `http://q-bios-service:8080` остаётся прежним).

