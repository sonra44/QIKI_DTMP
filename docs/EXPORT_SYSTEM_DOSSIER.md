# QIKI_DTMP — System Dossier (Export)

**Purpose:** one export-ready document that consolidates the **architecture**, **contracts**, **hardware/physics**, **ORION Shell OS design**, **QIKI/QCore design**, and the **current implementation plan + implemented milestones**.

**Last updated (UTC):** 2026-01-08  
**Repository:** `QIKI_DTMP`  
**Baseline master commit:** `9e946e1`  

> ⚠️ This dossier is a consolidation layer. When conflicts exist, defer to the “sources of truth” explicitly called out in each section.

---

## 0) Navigation (what to read first)

1) **Runtime reality (Phase1):** `docs/ARCHITECTURE.md`  
2) **ORION “Shell OS” system logic:** `docs/design/operator_console/ORION_OS_SYSTEM.md`  
3) **ORION↔QIKI contract (canonical):** `docs/design/operator_console/CANONICAL_SPEC_ORION_QIKI.md`  
4) **Hardware/physics source of truth:** `docs/design/hardware_and_physics/bot_source_of_truth.md`  
5) **QCore/QIKI brain model:** `docs/design/q-core-agent/neuro_hybrid_core_design.md`, `docs/design/q-core-agent/bot_core_design.ru.md`  
6) **No-mocks UI policy:** `docs/operator_console/REAL_DATA_MATRIX.md`  

---

## 1) System summary (what this project is)

**QIKI_DTMP** is a Phase1 “Digital Twin + Operator Shell OS” stack:

- **q-sim-service** simulates the world/sensors/actuators (gRPC).
- **NATS (+ JetStream)** is the message bus for telemetry, events, radar, control, and ORION↔QIKI protocol.
- **QCore Agent (qiki-dev)** is the headless “brain runtime”: collects context, evaluates rules, generates proposals (and later may execute approved actions).
- **ORION Operator Console** is a Textual TUI “Shell OS” for the operator: stable cockpit chrome, bounded incident workflow, calm command loop, and a deterministic rendering of QIKI proposals.

**Hard safety invariant (MVP):** no automatic actions/execution. Everything is **proposals-only**.

---

## 2) Runtime topology (Phase1 containers, ports, readiness)

Source: `docs/ARCHITECTURE.md`, `docs/RESTART_CHECKLIST.md`

### 2.1 Containers (Phase1)

- `qiki-nats-phase1` — NATS + JetStream (ports `4222`, `8222`)
- `q-sim-service` / `qiki-sim-phase1` — simulation gRPC (port `50051`), также публикует radar frames в NATS/JetStream
- `qiki-faststream-bridge-phase1` — NATS bridge/handlers for radar + control topics
- `qiki-dev-phase1` — QCore Agent runtime (`qiki.services.q_core_agent`)
- `qiki-operator-console` — ORION console (`src/qiki/services/operator_console/main_orion.py`)
- observability: Grafana/Loki/Promtail (Phase1 monitoring)

### 2.2 Core ports

- NATS client: `nats://localhost:4222` (inside docker: `nats://qiki-nats-phase1:4222`)
- NATS monitoring: `http://localhost:8222/healthz`
- q-sim-service gRPC: `localhost:50051` (inside docker: `q-sim-service:50051`)

### 2.3 Startup / health

See the full reproducible checklist: `docs/RESTART_CHECKLIST.md`.

Canonical commands:

```bash
cd QIKI_DTMP
docker compose -f docker-compose.phase1.yml up -d --build
docker compose -f docker-compose.phase1.yml ps
curl -sf http://localhost:8222/healthz
```

---

## 3) Message bus: NATS subjects and contracts

### 3.1 Contract policy (how subjects/protos evolve)

Source: `docs/CONTRACT_POLICY.md`

- Protobuf/gRPC: never reuse field numbers, only additive changes, breaking changes → new version.
- NATS: prefer versioned subjects (e.g. `qiki.radar.v1.*`), parallel-run v1/v2 during migration.
- JetStream: set dedup window, use `Nats-Msg-Id` header, bounded retention.

### 3.2 Phase1 subjects (major groups)

Source: `src/qiki/shared/nats_subjects.py`, `docs/ARCHITECTURE.md`

- Telemetry: `qiki.telemetry`
- Events: `qiki.events.v1.>` (wildcard)
- Radar:
  - frames: `qiki.radar.v1.frames` + `qiki.radar.v1.frames.lr`
  - tracks: `qiki.radar.v1.tracks` + `qiki.radar.v1.tracks.sr`
- Control plane:
  - commands: `qiki.commands.control`
  - responses: `qiki.responses.control`

---

## 4) ORION Operator Console (Shell OS)

Primary sources:
- `docs/design/operator_console/ORION_OS_SYSTEM.md`
- `docs/design/operator_console/ORION_OS_VALIDATION_CHECKLIST.md`
- `docs/operator_console/REAL_DATA_MATRIX.md`
- `docs/design/operator_console/ABBREVIATIONS_POLICY.md`
- `docs/design/operator_console/MFD_SCALABLE_LAYOUT.md`
- `docs/design/operator_console/TUI_RESEARCH_PATTERNS.md`

### 4.1 UX invariants

- **Bilingual everywhere:** `EN/RU` on every label/value, no spaces around `/`.
- **No-mocks UI:** missing data must render as honest `N/A/НД` / `Not available/Нет данных` or “No incidents/Инцидентов нет”.
- **Stable chrome:** header + sidebar + inspector + bottom bar must not “reflow into chaos”.
- **Events are not a dumb tail-log:** events should become *incidents* (dedup + ack + clear + pause/unread).
- **Calm operator loop:** command input + output (calm strip) must be readable in tmux splits.

### 4.2 Screens (Shell OS concept)

The current ORION model is “screen set + stable chrome”:

- `System/Система` (F1)
- `Radar/Радар` (F2) — non-priority: stability only
- `Events/События` (F3)
- `Console/Консоль` (F4)
- `Summary/Сводка` (F5)
- `Power systems/Система питания` (F6)
- `Diagnostics/Диагностика` (F7)
- `Mission control/Управление миссией` (F8)

### 4.3 Validation checklist (operator-driven)

Run and record ✅/❌ in: `docs/design/operator_console/ORION_OS_VALIDATION_CHECKLIST.md`.

Key checks:
- input text visible + does not overflow border
- calm output always visible
- events pause/unread + ack/clear
- inspector contract structure
- tmux resize stability
- rules screen: reload + enable/disable toggle (if present in the current branch)

### 4.4 Abbreviations policy

Default is “no abbreviations”, but **exceptions are allowed only** in dense zones and must be discoverable via Help glossary:

Source: `docs/design/operator_console/ABBREVIATIONS_POLICY.md`

### 4.5 “No-mocks” data matrix

Source: `docs/operator_console/REAL_DATA_MATRIX.md`

This document is the **UI truth table**:
- what each panel shows
- what NATS/gRPC/file source feeds it
- what the honest empty state must be

---

## 5) ORION↔QIKI integration (proposals-only)

### 5.1 Canonical spec (contract-first)

Source: `docs/design/operator_console/CANONICAL_SPEC_ORION_QIKI.md`

MVP rules:
- ORION is UI only.
- QIKI/QCore is headless and returns structured proposals.
- **No auto-actions**: any “actions” field must stay empty.

### 5.2 Implemented protocol (current PR series A–G)

These are the implemented milestones (feature branches; merge order is important):

**PR1 (Stage A) — Schemas & subjects**  
Branch: `feature/orion-qiki-schemas-subjects-a` @ `55efea1`  
- Adds `qiki.intent.v1` / `qiki.proposals.v1` and Pydantic schemas (`IntentV1`, `ProposalV1`, `ProposalsBatchV1`).

**PR2 (Stage B) — ORION publishes intent**  
Branch: `feature/orion-publish-intent-v1-b` @ `be099c5`  
- `q:` / `//` routes to NATS publish of `IntentV1` (non-blocking).

**PR3 (Stage C) — QCore intent bridge stub proposals**  
Branch: `feature/qcore-intent-stub-proposals-c` @ `dd4d58b`  
- Subscribes to intents, validates, publishes stub `ProposalsBatchV1`.

**PR4 (Stage D) — ORION displays proposals**  
Branch: `feature/orion-display-proposals-d` @ `cd34190`  
- Subscribes to proposals and renders in ORION (not mixed with incidents).

**PR7 (Stage G) — Factory/Mission modes and gating**  
Branch: `feature/env-modes-gating-pr7` @ `ae094e0`  
- Adds `qiki.environment.v1` + `qiki.environment.v1.set` and mode-aware proposal verbosity.

> Detailed report and PR7 spec live in that branch:
> - `docs/design/operator_console/ORION_QIKI_PR1_PR7_REPORT.md`
> - `docs/design/operator_console/ORION_QIKI_ENV_MODES_PR7.md`

### 5.3 OpenAI in NeuralEngine (optional; proposals-only)

Implementation lives in PR5 (see §9).

Hard rules:
- OpenAI keys/config only via ENV (never in repo).
- Strict JSON-only output; validate before use; fallback on any error.
- Enforce proposals-only at the boundary (strip any model “actions” fields).

---

## 6) QCore Agent (QIKI brain runtime)

Primary sources:
- `docs/design/q-core-agent/neuro_hybrid_core_design.md`
- `docs/design/q-core-agent/bot_core_design.md` / `docs/design/q-core-agent/bot_core_design.ru.md`
- `docs/design/q-core-agent/bios_design.md`
- `docs/design/q-core-agent/proposal_evaluator.md`
- `docs/ARCHITECTURE.md`

### 6.1 Q-Mind (Rule + Neural + Arbiter)

Source: `docs/design/q-core-agent/neuro_hybrid_core_design.md`

- Rule Engine: safety/guardrails, deterministic proposals
- Neural Engine: adaptive analysis (LLM-backed in PR5, proposals-only)
- Arbiter: prioritizes safety (rules first), then neural, then issues final decisions (execution is out-of-scope in MVP)

### 6.2 bot_core

Source: `docs/design/q-core-agent/bot_core_design.ru.md`

- persistent bot identity `QIKI-YYYYMMDD-XXXXXXXX`
- static config via `bot_config.json`
- raw sensor in / actuator out boundaries
- runtime buffer of last-known values

### 6.3 BIOS concept

Source: `docs/design/q-core-agent/bios_design.md`

- reads `bot_physical_specs.json`
- performs POST for ports/components
- publishes ready/error and exposes status APIs
- explicitly no business logic in BIOS

---

## 7) Hardware / physics (bot specification)

**Source of truth:** `docs/design/hardware_and_physics/bot_source_of_truth.md`

Key parameters (canonical):
- Coordinate system: **Z up, X forward, Y left**
- Center of mass: **`[0.0, 0.0, 0.1] m`**
- Hull: **dodecahedron (12 faces)**; each face is a module slot
- Docking: **2 bayonet ports** with power/data bridge cascade
- Propulsion: **RCS 16 thrusters** (4 clusters × 4) + ZTT/FTG symmetry principles
- Control principle: impulse/PWM-like thrust scheduling (bang-bang/PWPF style)

Hardware contracts pipeline:
- `docs/design/hardware_and_physics/bot_physical_specs_design.md` (contract format + docgen steps)

---

## 8) Development rules and quality gates

Primary sources:
- `docs/QIKI_DTMP_METHODOLOGICAL_PRINCIPLES_V1.md`
- `docs/CONTRACT_POLICY.md`
- `docs/RESTART_CHECKLIST.md`

Highlights:
- Docker-first for runs/tests.
- Tests pyramid: unit → integration → (minimal) e2e; Textual UI tests via `pytest`.
- Contract-first for message schemas and evolvable subjects.
- Security: never commit secrets; scan for tokens; logs without sensitive payloads.

---

## 9) Implementation status: what is merged vs in flight

### 9.1 On master (as of `9e946e1`)

ORION incidents workflow (Stages 5–7) is already merged and tested on master.

### 9.2 Feature branches to be merged (current)

These branches are pushed to origin and ready for PR review/merge:

- **PR6 — N/A semantics + empty states**  
  Branch: `feature/orion-na-quality-pr6` @ `a296b84`  
  Adds acceptance checklist doc: `docs/design/operator_console/ORION_QIKI_ACCEPTANCE.md` (in that branch).

- **PR5 — OpenAI in NeuralEngine (proposals-only)**  
  Branch: `feature/neuralengine-openai-proposals-pr5` @ `e9f1fe8`  
  Adds enforced tests to guarantee proposals-only even if model tries to emit actions.

- **PR7 — Env modes + gating**  
  Branch: `feature/env-modes-gating-pr7` @ `ae094e0`

Recommended merge order:
1) PR6 → master (data quality / UI honesty)
2) PR7 → master (modes/gating)
3) PR5 → master (OpenAI optional; stable fallback)

---

## 10) Document catalog (what exists and why)

This section is a “map of maps”. It is intentionally exhaustive at the file level, but each item is only one-line.

### 10.1 Top-level docs

- `docs/INDEX.md` — reading order / documentation index
- `docs/ARCHITECTURE.md` — Phase1 runtime topology + data flows
- `docs/RESTART_CHECKLIST.md` — reproducible bring-up for Phase1 (Radar v1 included)
- `docs/CONTRACT_POLICY.md` — contract evolution rules for proto/gRPC and NATS
- `docs/QIKI_DTMP_METHODOLOGICAL_PRINCIPLES_V1.md` — contributor/agent methodology
- `docs/NEW_QIKI_PLATFORM_DESIGN.md` — platform vision and principles (high-level)

### 10.2 Operator console design

- `docs/design/operator_console/ORION_OS_SYSTEM.md` — ORION system logic (Shell OS model)
- `docs/design/operator_console/ORION_OS_SYSTEM_MAP.md` — system map for ORION screens/panels
- `docs/design/operator_console/ORION_OS_VALIDATION_CHECKLIST.md` — operator-driven validation checklist
- `docs/design/operator_console/ORION_HEADER_REDESIGN_PLAN.md` — header redesign and stability plan
- `docs/design/operator_console/MFD_SCALABLE_LAYOUT.md` — scalable cockpit/MFD layout spec
- `docs/design/operator_console/ABBREVIATIONS_POLICY.md` — abbreviations policy (allowed zones + glossary rule)
- `docs/design/operator_console/TUI_RESEARCH_PATTERNS.md` — research notes from mature TUIs
- `docs/design/operator_console/COVAS_NEXT_RESEARCH.md` — external research notes (voice/assistant UI)
- `docs/design/operator_console/QIKI_INTEGRATION_PLAN.md` — linear plan for “brain” integration
- `docs/design/operator_console/CANONICAL_SPEC_ORION_QIKI.md` — canonical ORION↔QIKI spec
- Worklogs: `docs/design/operator_console/ORION_OS_WORKLOG_2025-12-30_4.md`, `_5.md`, `ORION_OS_WORKLOG_2025-12-31.md`

### 10.3 Operator console “real data” policy

- `docs/operator_console/REAL_DATA_MATRIX.md` — no-mocks policy matrix (what data comes from where)

### 10.4 Hardware / physics

- `docs/design/hardware_and_physics/bot_source_of_truth.md` — hardware/physics canonical doc
- `docs/design/hardware_and_physics/bot_physical_specs_design.md` — hardware contract format + docgen pipeline

### 10.5 Q-Core Agent design

- `docs/design/q-core-agent/neuro_hybrid_core_design.md` — Q-Mind (Rule/Neural/Arbiter)
- `docs/design/q-core-agent/bot_core_design.md` — bot_core (EN)
- `docs/design/q-core-agent/bot_core_design.ru.md` — bot_core (RU)
- `docs/design/q-core-agent/bios_design.md` — BIOS design
- `docs/design/q-core-agent/proposal_evaluator.md` — proposal evaluation logic

### 10.6 Analysis folder (auto-style documentation of code)

Directory: `docs/analysis/`

Contains per-module analysis snapshots, e.g.:
- `docs/analysis/agent.py.md`, `tick_orchestrator.py.md`, `neural_engine.py.md`, etc.

These are useful for “read the code without opening the code”, but are not the source of truth if code has moved.

---

## 11) Export checklist (for publishing)

- [ ] Ensure `docs/INDEX.md` links are valid (no missing files).
- [ ] Ensure no secrets in repo (`OPENAI_API_KEY`, tokens, Bearer headers).
- [ ] Ensure Phase1 starts cleanly in Docker (`docs/RESTART_CHECKLIST.md`).
- [ ] Ensure ORION validation checklist has a recent run result file (optional).
- [ ] Ensure PR branches are either merged or clearly documented as pending.

