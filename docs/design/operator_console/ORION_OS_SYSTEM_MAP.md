# ORION OS — System Map, Layers, and Templates

**Purpose:** Provide a single, structured map of ORION (Operator Console) with layers, data flow, UI templates, and decision points. This is meant to guide redesign and LLM-based review.

---

## 1) Layers (Top → Bottom)

### 1.1 Operator Layer (Human)
- **Goal:** fast control + situational awareness with minimal cognitive load.
- **UI invariants:** bilingual `EN/RU` everywhere, no spaces around `/`.
- **Interaction model:** `table/list → selection → inspector` + always-available command input.

### 1.2 Presentation Layer (TUI)
- **Framework:** Textual (`src/qiki/services/operator_console/main_orion.py`).
- **Chrome:** Header / Sidebar / Inspector / Bottom bar.
- **Screens:** System, Radar (non‑priority), Events, Console, Summary, Power, Diagnostics, Mission.

### 1.3 View-Model / State Layer
- **SnapshotStore:** last-known state by type and per key + freshness thresholds.
- **SelectionContext:** single source of “what is highlighted now”.
- **EventEnvelope:** unified envelope for UI (type, source, ts, level, payload).

### 1.4 Transport Layer
- **NATS:** telemetry + events + control commands.
- Subjects in `src/qiki/shared/nats_subjects.py`.

### 1.5 Simulation / Physical Model
- **Telemetry source:** simulation/bridge services.
- **Physics truth:** `docs/design/hardware_and_physics/bot_source_of_truth.md`.

---

## 2) Data Flow Map (High Level)

**Telemetry → NATS → OrionApp → SnapshotStore → UI Panels/Tables**

- Telemetry (`qiki.telemetry`) is normalized by `TelemetrySnapshotModel.normalize_payload()`.
- `SnapshotStore` computes freshness and feeds:
  - Header (Link/Bat/Hull/Rad/Temps/Age/Fresh)
  - Summary / Power / Diagnostics / Mission tables

**Events → NATS → OrionApp → EventEnvelope → Events table + Inspector**

- Events (`qiki.events.v1.>`) are ingested, normalized, counted, aged.
- Events are a *high‑frequency stream*, not the operator dialogue.

**Commands → Input → OrionApp → NATS control bus → Console output**

- Commands must output in Console (calm area), not Events.
- Control subjects: `qiki.commands.control` / `qiki.responses.control`.

---

## 3) UI Template Map (Reusable Patterns)

### 3.1 Chrome Template (global)
- **Header**: short status cells, 2 rows; compact labels + tooltips.
- **Sidebar**: hotkeys + screen names.
- **Inspector**: details of current selection.
- **Bottom bar**: Output (calm log) + command input + keybar.

### 3.2 Screen Template: Table + Selection + Inspector
Used by **Events / Console / Summary / Power / Diagnostics / Mission**

- **Table:** rows are primary objects
- **Selection:** highlight row → selection context updates
- **Inspector:** renders details of the selection

### 3.3 System Dashboard Template
Used by **System screen**

- Grid of panels (Nav/Power/Thermal/Struct).
- Each panel is a small table of `Label Value` lines.
- On narrow terminals: reflow `2x2 → 1x4`.

### 3.4 Compact/Scaled Template
Used for small tmux panes

- Hide Inspector first, then Sidebar.
- Reduce table column widths.
- Keep header + bottom bar always visible.

---

## 4) Key UI Zones and Their Roles

### 4.1 Header (Status)
- Always visible.
- Shows the most critical state (Link/Bat/Hull/Rad/Temps/Freshness/Age).
- Abbreviations allowed (see policy); tooltips + Help glossary.

### 4.2 Events (Firehose)
- High‑frequency timeline of system activity.
- Good for audit and debugging.
- **Not** a place for operator command responses.

### 4.3 Console (Dialogue)
- Operator’s calm interaction surface.
- All command outputs and system responses belong here.

### 4.4 Inspector (Details)
- A stable detail layout; never a raw dump as the only view.
- Should contain: Summary → Fields → Raw JSON (preview).

---

## 5) Known UX Problem (Telemetry Noise)

**Problem:** Telemetry logs flood UI, while operator‑critical data is hidden.

**Expected fix path (conceptual):**
1) Partition streams: “Events” for firehose, “Console” for operator dialogue.
2) Add “Summary panels” for the 5‑10 most important live signals.
3) Elevate “Incidents” model: group events into actionable items.

---

## 6) Abbreviations / Bilingual Policy (Short)

- All labels are `EN/RU` with no spaces around `/`.
- Abbreviations allowed only in dense zones:
  - Header, tables, keybar, dense panels.
- Every abbreviation must be documented in `F9` glossary and in
  `docs/design/operator_console/ABBREVIATIONS_POLICY.md`.

---

## 7) Current System Boundaries

- **Radar:** not a priority. Must remain stable but no redesign now.
- **Focus:** cockpit/MFD readability + core operator workflows.

---

## 8) Pointers (Code + Docs)

- UI entry: `src/qiki/services/operator_console/main_orion.py`
- NATS subjects: `src/qiki/shared/nats_subjects.py`
- OS system reference: `docs/design/operator_console/ORION_OS_SYSTEM.md`
- Layout scaling spec: `docs/design/operator_console/MFD_SCALABLE_LAYOUT.md`
- Abbrev policy: `docs/design/operator_console/ABBREVIATIONS_POLICY.md`

