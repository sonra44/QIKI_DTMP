# ORION Shell OS — Validation Results

**Date:** 2026-01-14  
**Stack:** `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml`  
**Console:** `docker attach qiki-operator-console` (tmux pane)

## Addendum: 2026-01-15 (boot + no-mocks UI readability)

- ✅ Stack health confirmed again: `nats`, `q-sim-service`, `q-bios-service`, `operator-console` are `healthy` in `docker compose ... ps`.
- ✅ BIOS smoke (real): `GET http://localhost:8080/healthz -> {"ok": true}` and `GET /bios/status` returns `post_results` list with device statuses.
- ✅ BootScreen is present (no-mocks):
  - Shows a cosmetic “cold boot” phase (no fake `%/ETA`).
  - Shows real `NET: NATS connected [OK]` once NATS is connected.
  - Waits for real BIOS event from NATS and can print row-by-row POST lines from payload.
  - Auto handover to main UI works.
- ✅ Virtual CPU/RAM (simulation-truth): `CPU/ЦП` and `Mem/Пам` show real MCQPU virtual telemetry values in the System dashboard (not VPS/container metrics).
- ✅ Missing-data placeholder is now compact `N/A/—` (still no-mocks; no invented zeros).
- ✅ Tests in Docker: `docker compose ... run --rm --no-deps operator-console pytest -q tests` → `142 passed`.

## 0) Preflight (runtime)

- ✅ Run via Docker (Phase1 + operator console): `up -d --build operator-console` + `docker attach`.
- ✅ Health confirmed: `ps` shows `healthy` for `nats`, `q-sim-service`, `operator-console`.

## 1) Global invariants (must always hold)

- ✅ Bilingual `EN/RU` labels (no spaces around `/`) observed across screens.
- ⚠️ Abbreviations exist in dense zones (keybar/header/etc). This is **allowed by policy** (`docs/design/operator_console/ABBREVIATIONS_POLICY.md`), but the checklist item “no abbreviations” is not literally true.
- ✅ Missing data is shown as `N/A/—` (compact, no-mocks).
- ✅ Chrome structure stable: header + sidebar + inspector + bottom bar present.

## 2) Input/Output dock (calm operator loop)

- ⚠️ Manual validation needed: input text visibility/overflow in `command/команда>` (requires interactive typing).
- ✅ `Output/Вывод` shows latest system messages and command echoes (e.g., `screen rules`, `reload rules`).
- ✅ Focus cycle improved: `Tab` now includes the Rules table as a focus target (so operators can reach it without hacks).
- ⚠️ Manual validation still needed: `Ctrl+E` and `Tab` behavior with long typing + navigation under “stress” (operator-driven).
- ✅ Input routing concept present: QIKI intents use prefix (`q:`), shell commands default (from hint line).

## 3) Events/События — incidents workflow

- ✅ `Ctrl+Y` toggles live/pause; `Output/Вывод` logs `Events paused/События пауза` and `Events live/События живое`.
- ⚠️ Unread/read/ack/clear/buffer limits not verified (no real incident stream observed during this run).

## 4) Inspector/Инспектор contract

- ✅ Inspector shows expected structure: `Summary/Сводка`, `Fields/Поля`, `Raw data (JSON)/Сырые данные (JSON)`, `Actions/Действия`.
- ✅ No selection → `N/A/—`.

## 5) Chrome stability under tmux resizing

- ✅ Narrow width shows truncation with `…` (no wrap chaos).
- ⚠️ Low height can reduce visible rows (e.g., Summary table); layout stays stable but operator may miss rows without scrolling.

## 6) Non-priority radar safety

- ✅ `F2` (Radar/Радар) does not crash the app.

## 7) Rules/Правила — quick enable/disable + reload

- ✅ Rules table loads after fix: `config/incident_rules.yaml` resolves to `/workspace/config/incident_rules.yaml` in Docker.
- ✅ Reload works via command: `reload rules` → `Incident rules reloaded/Правила инцидентов перезагружены: 3 (hash/хэш: ...)`.
- ✅ Toggle verified: `T` opens confirm dialog (`Y/N`), `Y` applies change and logs `Rule updated/Правило обновлено`.

## Notes: “CPU/ЦП” and “Mem/Пам” are virtual (simulation-truth)

- ✅ Real values observed in System panels and Summary after increasing tmux pane height.
- Source of truth for computation: `src/qiki/services/q_sim_service/core/mcqpu_telemetry.py`.
- Transport: `q-sim-service` publishes snapshots to NATS subject `qiki.telemetry` (enabled in `docker-compose.phase1.yml` via `TELEMETRY_NATS_ENABLED=1`).

## Notes: BIOS block requires `q-bios-service`

- ✅ When `q-bios-service` is started (`docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d q-bios-service`), Summary shows `BIOS/БИОС` as `OK/ОК` (and age updates).
- ✅ If `q-bios-service` is not running, Summary correctly shows `Not available/Нет данных` (no-mocks).
