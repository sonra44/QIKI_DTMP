# QIKI / CODEX CLI skill plan

## 1. Executive summary

### Archive roles
- `QIKI_DTMP.zip` is the live repository and the freshest technical source.
- `RE_QIKI_Active_Package.zip` is a strong reconstructed analysis/governance package and is useful as a map of architecture, risks, and reading order.
- For current slice status, code + fresh repo task outputs should outrank older analysis notes when they conflict.

### Core architecture observed
- `q_sim_service` + `world_model` is the physical runtime truth source.
- NATS/JetStream + shared subject canon + proto/contracts is the message spine.
- ORION V is the primary operator surface.
- `faststream_bridge` is not only glue: it handles routing, radar normalization and one intent path.
- `q_core_agent` contains a real decision/tick pipeline and also owns the richer `qiki_orion_intents_service` path on the canonical stack.
- BIOS and registrar are real side layers, but not single-source owners of all truth in their domains.

### Sensor/data findings
- The simulator uses `bot_config.json` and `world_model` to expose a config-driven `sensor_plane`.
- Radar truth is split into LR/SR publications and a union frame subject.
- ORION sensor UI expects a broader logical sensor registry than the currently visible sim output, so aliasing and projection discipline matter.
- The repo already contains real record/replay and export utilities; “data study” should build on these, not reinvent them.

### Important status nuance
- The RE package historically described `signature_changed live path` as the main unresolved blocker at the time that package was assembled.
- In the live repo’s active canon, [ACTIVE_TASKS_QIKI_DTMP.md](~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md) and `TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md` already treat that blocker as closed, and the board is in hardening/regression/cleanup mode.
- Therefore: RE package is excellent for orientation, but current-slice decisions should follow the active board, current task dossiers, and code.

---

## 2. Recommended CODEX CLI skills

Below, “skill” means a specialized working role / tasking profile for a terminal agent like Codex CLI.

### Skill 1 — `qiki-architecture-navigator`
**Purpose**
Build and maintain a precise map of the active architecture, entrypoints, and runtime contours.

**When to trigger**
- “Where does this feature live?”
- “Which service owns this behavior?”
- “What is canonical vs legacy here?”

**Primary inspection targets**
- `README.md`
- `docker-compose.phase1.yml`
- `docker-compose.operator.yml`
- `src/qiki/shared/nats_subjects.py`
- `src/qiki/services/**`
- `RE_QIKI_Architecture_Verification_Note.md`
- `RE_QIKI_Risks_and_Unresolved_Zones.md`

**Expected output**
- active runtime contour map
- owner candidates
- canonical path vs support/legacy path list
- “don’t touch before verifying” zones

**Why this matters**
The repo is large and transitional; without a navigator, Codex will make wrong edits in secondary entrypoints.

---

### Skill 2 — `qiki-runtime-contour-verifier`
**Purpose**
Verify that the canonical Phase1 + ORION stack is really the contour being reasoned about.

**When to trigger**
- before debugging runtime behavior
- before declaring something “broken” or “fixed”
- after compose/env changes

**Primary inspection targets**
- `docker-compose.phase1.yml`
- `docker-compose.operator.yml`
- `scripts/run_orion_v_live.sh`
- `scripts/run_minimal_regression_pack.sh`
- `docs/ORION_V_RUNBOOK.md`
- `TASK_OUT/final_stabilization_and_baseline.md`

**Checks**
- which containers are expected
- whether `faststream-bridge` intent handling is disabled in canonical stack
- whether `q-core-intents` owns `qiki.intents` on the live contour
- whether ORION runs `main_orion_v.py`

**Expected output**
- canonical/not-canonical verdict
- missing service list
- active subject ownership summary
- next safe command to run

---

### Skill 3 — `qiki-sensor-plane-auditor`
**Purpose**
Audit the full sensor plane from bot config -> world model -> telemetry payload -> ORION hardware view.

**When to trigger**
- sensor values missing in UI
- sensor status mismatch
- “is this sensor simulated or mocked?”
- adding a new sensor

**Primary inspection targets**
- `src/qiki/services/q_core_agent/config/bot_config.json`
- `src/qiki/services/q_sim_service/core/world_model.py`
- `src/qiki/services/q_sim_service/service.py`
- `src/qiki/services/operator_console/orion_v/hardware_view_model/collector.py`
- `src/qiki/shared/models/telemetry.py`

**Checks**
- which sensor subplanes are enabled
- how status/reason/limits are computed
- whether telemetry payload exports the field
- whether ORION registry expects different aliases/keys

**Expected output**
- sensor matrix: configured / simulated / exported / rendered
- missing-link diagnosis
- exact patch location

---

### Skill 4 — `qiki-radar-track-debugger`
**Purpose**
Trace radar data from simulator truth into frame publication, bridge processing, track generation, and ORION consumption.

**When to trigger**
- radar visible in one surface but not another
- track instability
- SR/LR confusion
- transponder ID leakage or absence problems

**Primary inspection targets**
- `src/qiki/services/q_sim_service/radar_publisher.py`
- `src/qiki/services/q_sim_service/service.py`
- `src/qiki/services/faststream_bridge/radar_handlers.py`
- `src/qiki/services/faststream_bridge/radar_track_store.py`
- `src/qiki/shared/models/radar.py`
- `src/qiki/services/operator_console/**`

**Checks**
- LR/SR split
- range-band tagging
- frame -> track association
- identity persistence
- ORION subscription/rendering

**Expected output**
- radar path timeline
- where truth is degraded or transformed
- recommended fix with minimal blast radius

---

### Skill 5 — `qiki-intent-ownership-guardian`
**Purpose**
Prevent accidental duplication or confusion between `faststream_bridge`, `q_core_agent`, and legacy `qiki_chat` paths.

**When to trigger**
- anything touching `qiki.intents`
- response duplication
- proposal accept/reject bugs
- operator command path changes

**Primary inspection targets**
- `docker-compose.phase1.yml`
- `src/qiki/services/faststream_bridge/app.py`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/qiki_chat/handler.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/shared/models/qiki_chat.py`

**Checks**
- who subscribes to `qiki.intents` in this contour
- who publishes `qiki.responses.qiki`
- whether bridge intent path is intentionally disabled
- whether legacy handler is being used accidentally

**Expected output**
- single-owner verdict for current contour
- risk of double replies
- safe edit zone
- migration/cleanup recommendation

---

### Skill 6 — `orion-v-regression-runner`
**Purpose**
Exercise the operator surface the way a human operator actually uses it.

**When to trigger**
- UI changes
- control loop changes
- observation flow changes
- after modifications in NATS payloads or telemetry structure

**Primary inspection targets**
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/**`
- `tools/orion_v_*_smoke.py`
- `docs/ORION_V_RUNBOOK.md`
- `TASK_OUT/observation_contour_dossier.md`

**Checks**
- telemetry freshness behavior
- QIKI request building
- pending action extraction
- observation follow-up gates
- help text / status transitions

**Expected output**
- operator-visible breakage list
- reproduction steps
- fix candidates ordered by user impact

---

### Skill 7 — `qiki-observation-contour-verifier`
**Purpose**
Protect the resumed observation / `signature_changed` contour from regressions.

**When to trigger**
- any change in observation objectives
- public track identity handling
- result projection or comparison labels
- tasking around “is the blocker really closed?”

**Primary inspection targets**
- `TASK_OUT/final_stabilization_and_baseline.md`
- `TASK_OUT/observation_contour_dossier.md`
- `TASK_OUT/resumed_path_observability_hardening.md`
- `scripts/run_minimal_regression_pack.sh`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/operator_console/orion_v/app.py`

**Checks**
- objective continuity
- public track identity
- q-core identity
- current-slice baseline vs stale blocker-era wording

**Expected output**
- regression/no-regression verdict
- stale-doc warning if agent is reading historical notes as current truth
- exact observability gap if present

---

### Skill 8 — `qiki-contract-drift-auditor`
**Purpose**
Watch for drift between proto schemas, shared subjects, telemetry/radar models, and service usage.

**When to trigger**
- schema changes
- new subject introduction
- serialization bugs
- consumer breakage after “small” payload edits

**Primary inspection targets**
- `proto/`, `protos/`, `generated/`
- `src/qiki/shared/nats_subjects.py`
- `src/qiki/shared/models/**`
- `src/qiki/shared/converters/**`
- publisher/subscriber code across services

**Checks**
- subject canon vs hardcoded strings
- Pydantic models vs generated protobuf
- CloudEvents headers consistency
- backward compatibility risk

**Expected output**
- contract drift report
- incompatible producer/consumer pairs
- regeneration instructions

---

### Skill 9 — `qiki-record-replay-analyst`
**Purpose**
Use existing JSONL record/replay utilities to study incidents, telemetry, radar, and event timing.

**When to trigger**
- “изучение данных”
- incident replay
- timing drift investigation
- offline debugging without a full live session

**Primary inspection targets**
- `src/qiki/shared/record_replay.py`
- `tools/nats_record_jsonl.py`
- `tools/nats_replay_jsonl.py`
- `src/qiki/services/operator_console/utils/data_export.py`
- `src/qiki/services/q_core_agent/core/trace_export.py`

**Checks**
- which subjects to capture
- capture schema
- replay timing fidelity
- export filters and event envelopes

**Expected output**
- ready command lines for record/replay
- minimal subject list for the investigation
- timeline summary from JSONL

---

### Skill 10 — `qiki-environment-bootstrap-doctor`
**Purpose**
Detect environment mismatch early and force the agent back to the canonical Docker-first workflow.

**When to trigger**
- import errors
- protobuf mismatch
- pydantic mismatch
- direct host pytest failures
- broken local `.venv`

**Primary inspection targets**
- `README.md`
- Dockerfiles / compose files
- `requirements*.txt`
- generated protobuf version assumptions
- current shell env and interpreter

**Checks**
- host Python vs repo expectations
- pydantic v2 vs installed v1
- protobuf runtime vs generated code major version
- missing `nats`, `textual`, `faststream`
- whether Docker is the intended path

**Expected output**
- “stop using this host env” warning when needed
- canonical bootstrap sequence
- exact mismatch inventory

---

### Skill 11 — `qiki-bios-support-contract-checker`
**Purpose**
Check BIOS side-service health, payload semantics, and projection into ORION/Q-core expectations.

**When to trigger**
- BIOS panel inconsistency
- startup status anomalies
- support-tier contract changes

**Primary inspection targets**
- `src/qiki/services/q_bios_service/**`
- `TASK_OUT/qbios_contract_and_resilience.md`
- ORION BIOS-related projection code
- NATS event subjects for BIOS status

**Expected output**
- support-tier contract status
- side-service vs internal handler role split
- whether issue is current or historical/resolved

---

### Skill 12 — `qiki-legacy-boundary-classifier`
**Purpose**
Mark zones as canonical, transitional, support, historical, or suspected legacy before any cleanup/refactor.

**When to trigger**
- deleting old files
- moving entrypoints
- “can we remove this?”
- repo simplification work

**Primary inspection targets**
- `main*.py` families in operator console
- `ship_*`
- `mission_control*`
- legacy compose overlays
- RE risk notes and passports

**Expected output**
- keep / quarantine / deprecate / remove recommendation
- evidence level for each verdict

---

### Skill 13 — `qiki-doc-status-reconciler`
**Purpose**
Continuously reconcile RE package statements, repo baselines, and live code truth.

**When to trigger**
- tasking or planning based on docs
- disagreements between docs and code
- creating new audit/analysis packages

**Primary inspection targets**
- `RE_*.md`
- `TASK_OUT/*.md`
- active runbooks/docs
- changed code in the relevant slice

**Checks**
- stale blocker wording
- historical docs still presented as active truth
- risk/status drift

**Expected output**
- current-truth shortlist
- stale-doc shortlist
- update recommendations without rewriting history

---

### Skill 14 — `qiki-lore-to-mechanics-mapper`
**Purpose**
Keep gameplay/lore language aligned with the actual operator and simulation mechanics.

**When to trigger**
- naming a new mode, procedure, anomaly, hazard, or mission concept
- writing operator-facing text
- bridging product narrative with system behavior

**Primary inspection targets**
- `ЛОР.md`
- ORION UI wording
- incident/procedure/objective semantics
- sensor/combat/observation subsystems

**Expected output**
- lore-consistent terminology list
- mechanic mapping suggestions
- where current code already matches the narrative and where it does not

---

### Skill 15 — `qiki-task-dossier-writer`
**Purpose**
Produce branch/task-ready technical dossiers after analysis so work can proceed cleanly.

**When to trigger**
- after non-trivial debugging
- before opening a Codex branch
- before handing context to another agent

**Primary inspection targets**
- changed files
- runtime proof/evidence notes
- regression findings
- current active baseline docs

**Expected output**
- objective
- current truth
- constraints
- affected files
- validation plan
- rollback/risk notes

---

## 3. The first 6 skills to build first

If you want maximum leverage quickly, start in this order:

1. `qiki-architecture-navigator`
2. `qiki-runtime-contour-verifier`
3. `qiki-sensor-plane-auditor`
4. `qiki-intent-ownership-guardian`
5. `qiki-record-replay-analyst`
6. `orion-v-regression-runner`

This set covers the highest-cost mistakes currently visible in the repo: wrong contour, wrong owner, wrong sensor assumptions, and weak data-driven debugging.

---

## 4. Concrete prompts for Codex CLI

### Example prompt: architecture
> Build an active architecture map for QIKI_DTMP. Prefer code over docs. Treat `README.md`, `docker-compose.phase1.yml`, `docker-compose.operator.yml`, `src/qiki/shared/nats_subjects.py`, and `src/qiki/services/**` as primary evidence. Mark each entrypoint as canonical, transitional, support, or legacy.

### Example prompt: sensor audit
> Audit the full sensor path for QIKI_DTMP from `bot_config.json` through `world_model`, telemetry payload, NATS subjects, and ORION hardware view. Produce a matrix: configured / simulated / exported / rendered / missing.

### Example prompt: intent ownership
> Verify current `qiki.intents` ownership on the canonical Phase1 + ORION contour. Check compose env overrides, bridge subscribers, q-core intents service, and the legacy `qiki_chat` handler. Tell me who is the real intent owner in this contour and where double-reply risk still exists.

### Example prompt: record/replay
> For this bug, design the smallest useful JSONL capture plan using existing `record_replay.py` and tools. Tell me which NATS subjects to record, for how long, and how to replay them to reproduce the issue offline.

### Example prompt: doc reconciliation
> Reconcile RE package status with current repo baseline. Prefer code and current `TASK_OUT` docs. Mark every stale blocker-era statement as historical instead of current truth.
