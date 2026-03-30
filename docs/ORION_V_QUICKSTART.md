# ORION V Quickstart

ORION V is the default operator console.
Legacy ORION is isolated and starts only with the legacy profile/override.

## Run Phase1 baseline

```bash
docker compose -f docker-compose.phase1.yml up -d --build
docker compose -f docker-compose.phase1.yml ps
```

Phase1 now includes the canonical QIKI intent listener by default:

- `q-core-intents` owns `qiki.intents -> qiki.responses.qiki`
- `faststream-bridge` keeps radar/system duties and does not handle live QIKI intents in the default stack

## Run ORION V (default)

```bash
docker compose \
  -f docker-compose.phase1.yml \
  -f docker-compose.operator.yml \
  up -d --build operator-console
```

Interactive live console under tmux:

```bash
./scripts/run_orion_v_live.sh
```

Important:
- canonical live path for ORION V under `tmux` is a fresh TTY via `./scripts/run_orion_v_live.sh`
- do not use `docker attach qiki-operator-console` as the default interactive path
- script source of truth remains `docker exec -it qiki-operator-console python main_orion_v.py`
- `docker-compose.operator.yml` is the only supported default overlay for ORION V
- `docker-compose.operator_orionv.yml` is preserved as a transitional/non-canonical override
- `docker attach` may leave ORION V without proper alternate-screen / mouse mode in tmux and cause dirty redraw, repeated headers, cursor jumps, and unstable click behavior

Pilot one-line variant:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build
```

## Уровни (F1-F7)

- `F1` Кокпит: сводка состояния (`Состояние`, `Энергия`, `Движение и безопасность`, `Угрозы`, `Инциденты и действия`).
- `F2` Подсистемы: динамический список модулей + детализация выбранного модуля.
- `F3` Глубокий анализ: активные инциденты и последние события из ограниченного хранилища.
- `F4` Сырой поток: телеметрия и события в виде JSON.
- `F6` Журнал действий: операторский аудит (`actions/procedures/incidents`) с фильтром и пагинацией.
- `F7` Состояние системы: метрики runtime (`Событий в секунду`, `Глубина очереди`, задержки, CPU/память, подписки).

Fallback commands for terminals where function keys are not delivered:
- `f1`, `f2`, `f3`, `f4`, `f6`, `f7`
- `help`
- `q` / `quit`

## Архитектура модулей подсистем

Contract lives in `src/qiki/services/operator_console/orion_v/modules/base.py` and defines:
- `render_summary(state)`
- `render_details(state)`
- `sources_of_truth()`

Текущие встроенные модули:
- `Энергия` (`modules/power.py`)
- `Терморежим` (`modules/thermal.py`)
- `Связь` (`modules/comms.py`)
- `Стыковка` (`modules/docking.py`)

F2 automatically discovers modules from `orion_v/modules/*.py` (except helper files). New modules are loaded without editing F2 core code.

How to add a new subsystem module:
1. Create a module class implementing `SubsystemModule`.
2. Add it to `default_modules()` in `modules/__init__.py`.
3. Restart ORION V overlay container.

## Работа с инцидентами (overlay + F3)

Level-0 overlay appears when active severity `C`/`A` incidents exist and require acknowledgement.

Selection and actions:
- `Up/Down` or commands `inc next` / `inc prev` to change selected incident.
- `ack` or `ack <incident_id>` to acknowledge selected incident.
- `clear` to clear acknowledged incidents.
- `select <incident_id>` to jump to a specific incident.

Безопасность: `ack` и `clear` всегда открывают диалог подтверждения (`Подтвердить/Отмена`) перед действием.

## Фильтры и пагинация (F3/F4)

Supported filters:
- severity: `sev WARN`, `sev C`, `sev WARN,C`, `sev all`
- subsystem: `subsys thermal`, `subsys power`, `subsys all`
- time range (seconds): `range 300`, `range all`

Pagination:
- keyboard: `PgUp` / `PgDn`
- commands: `page prev`, `page next`

These controls keep UI responsive when event volume is high (>1000), because only one page is rendered at a time.

## Процедуры (Command Sequences)

Procedure files are loaded from `config/orion_v/procedures/` (`.json` or `.yaml`) and follow:
- `name`
- `steps[]`
- `command`
- `expected_ack`
- `timeout`
- `on_fail` (`abort` or `continue`)

Operator commands:
- `proc list`
- `proc run <name>`
- `proc status`

Execution is sequential, waits for acknowledgements from `qiki.responses.control`, and writes audit events to:
- `qiki.events.v1.operator.actions`
- `qiki.events.v1.operator.incidents`
- `qiki.events.v1.operator.procedures`

## Режим анализа истории (JetStream replay)

Replay commands:
- `replay on [seconds]` (default 900)
- `replay status`
- `replay off`

When replay is enabled:
- ORION V loads recent events from JetStream (`QIKI_EVENTS_V1`) as historical source.
- F3/F4 use replay data without breaking live mode.
- F4 includes minimal trend summaries for `SOC`, `Temperature`, `Voltage`.
- A control banner is shown: `REPLAY MODE — CONTROL DISABLED`.
- `ack/clear` and `proc run ...` are blocked until `replay off`.

## Устойчивость сессии / reconnect

- В заголовке NATS-состояние показывается явно: `Связь установлена`, `Переподключение`, `Связь отсутствует`.
- NATS reconnect uses safe auto-resubscribe with duplicate-subscription protection.
- Replay/live toggles do not create extra event subscriptions.

## Команды аудита

- `audit all`
- `audit actions`
- `audit procedures`
- `audit incidents`
- `audit level`
- `audit replay`

Pagination for F6 uses the same keys/commands:
- `PgUp` / `PgDn`
- `page prev` / `page next`

## Команда help

`help` shows:
- level navigation (`f1..f4`, `f6`, `f7`)
- incident commands (`select`, `inc next`, `inc prev`, `ack`, `clear`)
- module focus command (`module <slug>`)
- filter/pagination commands
- procedure commands
- replay commands
- audit filter commands

## Environment variables

- `ORIONV_MAX_EVENTS` (default `500`): max size of in-memory bounded events store.
- `ORIONV_EVENTS_PREVIEW` (default `12`): number of recent events shown in Deep/Raw and overlay preview.
- `ORIONV_EVENTS_PAGE_SIZE` (default `50`): page size for F3/F4 list rendering.
- `ORIONV_MAX_AUDIT_EVENTS` (default `1000`): max size of in-memory audit trail store (F6).
- `ORIONV_AUDIT_PAGE_SIZE` (default `50`): page size for F6 audit rendering.
- `ORIONV_PROCEDURES_DIR` (default `/workspace/config/orion_v/procedures`): directory for command sequence definitions.
- `NATS_URL` (default `nats://nats:4222`): broker endpoint for telemetry/events subscriptions.

## Legacy fallback run (isolated)

```bash
docker compose \
  -f docker-compose.phase1.yml \
  -f docker-compose.operator.yml \
  -f docker-compose.operator_legacy.yml \
  --profile legacy \
  up -d --build operator-console
```

For isolated legacy checks under `tmux`, use the explicit legacy entrypoint:

```bash
docker exec -it qiki-operator-console python -m qiki.services.operator_console.legacy.main_orion
```

This legacy path is preserved for compatibility only and is not part of the supported ORION V launch canon.

## Rehearsal / Cutover References

- Cutover plan and rollback commands: `docs/CUTOVER_PLAN.md`
- Operational runbook: `docs/ORION_V_RUNBOOK.md`
- Stage 6 rehearsal evidence: `TASKS/TASK_20260226_stage6_cutover_rehearsal.md`
- Stage 7 primary switch evidence: `TASKS/TASK_stage7_primary_switch.md`
- Stage 7 final cutover evidence: `TASKS/TASK_stage7_final_cutover.md`
