# ORION OS — System Logic & “Physics” Reference

**Project:** QIKI_DTMP  
**Scope of this document:** what ORION *is*, how it runs, how data flows through it, and how it maps to the bot’s physical model.  
**Non-goal:** radar UX/graphics work (radar is explicitly not a priority right now).

---

## 1) What ORION is

ORION is the **Operator Console TUI** (“Shell OS”) built on **Textual**. It is a stable cockpit “chrome” (header/sidebar/inspector/command dock) with multiple screens that all follow the same interaction model:

**table/list → selection → inspector**, with a **global command bus** always available.

### Core UX invariants (non-negotiable)

- **Bilingual everywhere:** `EN/RU` on every label/value (no spaces around `/`).
- **No UI abbreviations:** do not shorten words in the UI to “sys/diag/etc”.
- **No-mocks:** if data is missing, show `N/A/НД` (never invent zeros).
- **Stable chrome:** switching screens changes content, not layout.

---

## 2) Runtime topology (what runs)

In Phase1 the operator console is typically launched via:

- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`

Key services involved:

- **`qiki-operator-console`**: runs ORION (`src/qiki/services/operator_console/main_orion.py`).
- **`qiki-nats-phase1`**: NATS (core subjects + JetStream).
- **`qiki-sim-phase1` / `q-sim-service`**: simulation & bridge components (control plane + telemetry/events).

`docker-compose.operator.yml` sets:

- `NATS_URL=nats://qiki-nats-phase1:4222`
- `GRPC_HOST=q-sim-service`, `GRPC_PORT=50051` (control/bridge path)
- `PYTHONPATH=/workspace/src:/workspace/generated:/app`

---

## 3) Data plane (NATS subjects)

Canonical names are defined in `src/qiki/shared/nats_subjects.py`:

### Telemetry

- `qiki.telemetry` (`SYSTEM_TELEMETRY`)

### Events

- `qiki.events.v1.>` (`EVENTS_V1_WILDCARD`)

### Radar (non-priority, keep stable)

- `qiki.radar.v1.tracks` (`RADAR_TRACKS`)
- `qiki.radar.v1.tracks.sr` (`RADAR_TRACKS_SR`)
- `qiki.radar.v1.frames.lr` (`RADAR_FRAMES_LR`)

### Control (commands + responses)

- `qiki.commands.control` (`COMMANDS_CONTROL`)
- `qiki.responses.control` (`RESPONSES_CONTROL`)

---

## 4) ORION internal data model (how UI stores “truth”)

ORION intentionally keeps UI state separate from transport state.

### 4.1 EventEnvelope (UI envelope)

Inside ORION, incoming messages are normalized into an `EventEnvelope`:

- `event_id` — unique id (UI-side)
- `type` — derived logical type (e.g. `telemetry`, `mission`, `power`, …)
- `source` — usually `nats`
- `ts_epoch` — receipt timestamp
- `level` — normalized severity
- `subject` — NATS subject (if present)
- `payload` — raw decoded JSON payload

### 4.2 SnapshotStore (last-known state + freshness)

`SnapshotStore` keeps **last-known** envelopes by:

- **type** (e.g. latest `telemetry`)
- optional **type + key** (e.g. latest event per `subject`/id)

It also derives **freshness** (`FRESH/СВЕЖО`, `STALE/УСТАРЕЛО`, `DEAD/НЕТ`) by thresholds:

- telemetry: fresh `< 30s`, stale `< 300s`, else dead
- mission/task: fresh `< 300s`, stale `< 3600s`, else dead
- power: fresh `< 60s`, stale `< 900s`, else dead
- default: fresh `< 60s`, stale `< 600s`, else dead

This is the backbone for “state viewers” like `Summary/Сводка`, `Power systems/Система питания`, `Diagnostics/Диагностика`, `Mission control/Управление миссией`.

---

## 5) UI chrome (layout + screens)

ORION layout is defined in `OrionApp.compose()`:

- **Sidebar/Навигация** (left): list of screens + hotkeys.
- **Header** (top): ONLINE + key physical/health readouts.
- **Inspector/Инспектор** (right): details of current selection.
- **Bottom bar**: `command/команда>` input + keybar.

Screens (current set):

- `System/Система` (F1)
- `Radar/Радар` (F2) — non-priority, stability only
- `Events/События` (F3)
- `Console/Консоль` (F4)
- `Summary/Сводка` (F5)
- `Power systems/Система питания` (F6)
- `Diagnostics/Диагностика` (F7)
- `Mission control/Управление миссией` (F8)

---

## 6) Command bus (operator interaction)

### 6.1 Command input

The input widget is `#command-dock`. It is focused on mount to reduce friction in tmux workflows.

### 6.2 Command grammar (current)

Commands are parsed in `OrionApp._run_command()`:

- `help/помощь/?/h` — help panel
- `screen <name>` / `экран <имя>` — switch screen
- bare screen aliases: `system`, `система`, `events`, …
- `filter <text>` / `filter off` / `filter` (clears) — events text filter
- `type <name>` / `type off` — events type filter
- `simulation.*` or `симуляция.*` — canonicalized and published to control bus (`sim.*` internally)

### 6.3 Where command output goes

Operator-facing responses should be **deterministic**: every command must write to the **Console/Консоль** feed (not to Events).

Currently ORION writes command/system messages via `_console_log()` into `#console-table`.

---

## 7) Events vs Console (two different channels)

### Events/События

Events are a **high-frequency stream** (telemetry-adjacent): good for audit, debugging, “what happened”.

Target UX (design intent):

- bounded buffer (ring)
- filters (type/source/severity/text)
- grouping/dedup into “incidents”
- pause/freeze + unread counters

### Console/Консоль

Console is the **operator dialogue**:

- command confirmations
- errors / parse failures
- responses from control plane (`qiki.responses.control`)

Console must feel “calm” and always predictable.

---

## 8) Inspector/Инспектор (selection-driven details)

Inspector is **selection-driven**:

- If you highlight a row, inspector shows details for that row.
- If there is no selection, inspector shows `N/A/НД`.

Target structure inside inspector:

1) `Summary/Сводка` (what is it + status + age)
2) `Fields/Поля` (canonical key/value)
3) `Raw JSON/Сырой JSON` (safe preview)
4) `Actions/Действия` (future: ack, export, open related)

---

## 9) “Physics” mapping (bot model → telemetry → ORION)

ORION does not implement physics; it **observes** physics through telemetry/events and presents it in operator-friendly form.

### 9.1 Canonical physical model

Physical/structural source-of-truth is in:

- `docs/design/hardware_and_physics/bot_source_of_truth.md`

Key facts used for operator context:

- Coordinate system: **Z up, X forward, Y left**
- Center of mass: `[0.0, 0.0, 0.1] m`
- Docking: 2 bayonet ports + power bridge
- Propulsion: RCS 16 thrusters, ZTT/FTG principles, PWM-style impulse control

### 9.2 ORION header readouts (telemetry fields)

Header values are derived from telemetry payload normalized by `TelemetrySnapshotModel.normalize_payload()`:

- `battery` → `Battery/Батарея`
- `hull.integrity` → `Hull/Корпус`
- `radiation_usvh` → `Radiation/Радиация` (`microsieverts per hour/микрозиверты в час`)
- `temp_external_c` → `External temperature/Наружная температура`
- `temp_core_c` → `Core temperature/Температура ядра`
- freshness/age comes from `SnapshotStore` thresholds

**ONLINE/В СЕТИ** is not “magic”: it requires NATS connectivity and `FRESH/СВЕЖО` telemetry.

---

## 10) Current gaps (explicit)

- Events UX is still too “tail-like” (needs incident model + freeze/unread).
- Console output should be visible near input (persistent calm area).
- Inspector needs stricter, uniform structure per selection kind.
- Radar must remain stable but is not being developed right now.

---

## 11) Implementation plan (detailed, linear, no branching)

### Step 1 — Split operator dialogue from event firehose (UI)

Goal: command responses always appear in a calm, always-visible area.

- Add a bottom “console strip” adjacent to the command input:
  - last N (e.g. 5–10) console lines visible on every screen
  - full Console/Консоль screen remains the scrollback/history view
- Route all command feedback to `_console_log()` (no writing into Events).

Acceptance:

- typing `help` produces output in Console strip + Console screen
- Events screen does not receive command chatter

### Step 2 — Events become “Incidents” (bounded, actionable)

Goal: operator can *do something* with events.

- Maintain a ring buffer (size configurable).
- Introduce incident key: `type+source+subject` (minimum viable).
- Table shows incidents: last time, severity, type, source, subject, count, age.
- Add freeze mode:
  - user scroll/highlight → `PAUSED/ПАУЗА` and unread counter
  - explicit `live/живо` command to resume auto-follow
- Add ack/clear:
  - `ack <id>` to acknowledge incident
  - `clear` to clear acknowledged

Acceptance:

- events table does not grow without bound
- operator can filter, pause, and acknowledge

### Step 3 — Inspector contracts (uniform, bilingual)

Goal: inspector becomes the main “details pane”, not random JSON.

- Define per-kind renderers (`event`, `incident`, `track`, `console`, `summary_block`, …).
- Normalize all field labels to bilingual `EN/RU`.
- Ensure long values fold (never forced abbreviations).

Acceptance:

- selecting any row produces a consistent inspector structure

### Step 4 — Docs + tests

- Extend `src/qiki/services/operator_console/tests` with:
  - “no-mocks” invariants
  - incident aggregation behavior
  - console strip always renders

---

## 12) Pointers (code)

- ORION UI: `src/qiki/services/operator_console/main_orion.py`
- NATS client: `src/qiki/services/operator_console/clients/nats_client.py`
- Canonical subjects: `src/qiki/shared/nats_subjects.py`
- TDE design spec: `docs/design/operator_console/TDE_DESIGN_ORION.md`
- Physical source-of-truth: `docs/design/hardware_and_physics/bot_source_of_truth.md`

