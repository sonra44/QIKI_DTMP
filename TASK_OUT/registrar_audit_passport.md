# registrar audit passport

## 1. Runtime role

`registrar` is a canonical audit/support service in the Phase1 contour, not a truth owner and not a policy owner.

- Actual entrypoint is `python src/qiki/services/registrar/main.py` from `src/qiki/services/registrar/Dockerfile:27`; `docker-compose.phase1.yml` starts the container without overriding that command.
- Runtime role in code is narrow and mechanical: subscribe to selected bus subjects, append locally, republish a normalized audit copy (`src/qiki/services/registrar/main.py:95-149`).
- The service does not compute world truth, legality, routing, control decisions, or operator meaning. Those stay upstream in `q_sim_service`, `faststream_bridge`, `q_core_intents`, and ORION.
- This matches the intended contour note that `registrar` is an audit/support service, but only as a black-box recorder/forwarder, not as source-of-truth owner (`QIKI_CODEX_AUDIT_FOR_TASKING.md:651-731`).

## 2. Inputs

### Accepted streams

- `qiki.radar.v1.frames`
  - subscriber: `handle_radar_frame()` (`src/qiki/services/registrar/main.py:95-124`)
  - consumed fields: `frame_id`, `sensor_id`, `detections`
  - recorded as:
    - local `SENSOR_EVENT` with `RegistrarCode.RADAR_FRAME_RECEIVED`
    - republished audit record with `event_type=RADAR_FRAME_RECEIVED`

- `qiki.events.v1.>`
  - subscriber: `handle_system_events()` (`src/qiki/services/registrar/main.py:127-148`)
  - behavior: wraps any incoming event payload as a local `SYSTEM_EVENT`, then republishes a normalized audit record with `event_type=SYSTEM_EVENT`

### Input contract observations

- The code subscribes by subject only. Unlike `faststream_bridge`, `registrar` does not declare `durable=...`, `pull_sub=True`, or `stream=JStream(...)` on its subscribers. There is no code proof that registrar ingress is durable or catch-up capable (`src/qiki/services/registrar/main.py:95-127` vs `src/qiki/services/faststream_bridge/app.py:445-450`).
- `tools/js_init.py` does create JetStream stream/consumer config for events and radar, including `events_audit_pull`, but there is no evidence in registrar code that it binds to those consumers (`tools/js_init.py:56-136`, `tools/js_init.py:180-190`).
- No HTTP or RPC intake exists. The stage0 doc claim about an “API приёма событий” is doc drift, not runtime fact (`docs/stage0_actual_plan.md:31-34`).

## 3. Outputs / persistence

### What registrar writes

- Local append-only JSONL-style file: `/var/log/qiki/registrar.log`
  - configured in `src/qiki/services/registrar/main.py:44`
  - append behavior in `src/qiki/services/registrar/core/service.py:73-80`
- Republished audit events on `qiki.events.v1.audit`
  - emitted by `_publish_audit()` with CloudEvents headers and `Nats-Msg-Id` (`src/qiki/services/registrar/main.py:66-77`)
  - published into stream `QIKI_EVENTS_V1` by default (`src/qiki/services/registrar/main.py:34-36`)
- Boot marker on startup
  - local `BOOT_EVENT` only via `register_boot_event()` during `after_startup` (`src/qiki/services/registrar/main.py:80-92`, `src/qiki/services/registrar/core/service.py:82-92`)

### Storage / retention behavior actually proven

- JetStream events stream is configured file-backed with bounded `max_age`, bounded `max_bytes`, and duplicate window through `tools/js_init.py` (`tools/js_init.py:56-64`, `tools/js_init.py:115-123`).
- In Phase1 compose, `nats-js-init` enables the events stream and sets:
  - `EVENTS_STREAM=QIKI_EVENTS_V1`
  - `EVENTS_SUBJECTS=qiki.events.v1.>`
  - `EVENTS_MAX_AGE_SEC=3600`
  - `EVENTS_MAX_BYTES=10485760`
  - `EVENTS_AUDIT_SUBJECT=qiki.events.v1.audit`
  - `EVENTS_AUDIT_DURABLE=events_audit_pull`
  (`docker-compose.phase1.yml:286-295`)
- Local file persistence is only “mkdir parent + append one JSON line”. There is no code evidence of rotation, truncation, archival, checksum, or compaction (`src/qiki/services/registrar/core/service.py:48-80`).

## 4. Audit source-of-record boundaries

### What is source of record

- For raw runtime truth: `registrar` is not source of record.
  - Radar truth stays with `q_sim_service` on `qiki.radar.v1.frames`.
  - Operator/proposal/objective meaning stays with the original publisher (`q_core_intents`, `faststream_bridge`, ORION, etc.).
- For registrar-local evidence that registrar itself observed and transformed something:
  - `/var/log/qiki/registrar.log` is the only explicit registrar-owned append trail.
- For shared bus-level audit copies:
  - `QIKI_EVENTS_V1 / qiki.events.v1.audit` is a shared audit bus, not an exclusive registrar ledger.

### Why it is not exclusive

- `q_core_intents` directly publishes hidden-observation audit events to `qiki.events.v1.audit` (`src/qiki/services/q_core_agent/qiki_orion_intents_service.py:374-402`, `src/qiki/services/q_core_agent/qiki_orion_intents_service.py:3582-3584`, `src/qiki/services/q_core_agent/qiki_orion_intents_service.py:3637-3639`).
- `faststream_bridge` directly publishes proposal-accept audit events to `qiki.events.v1.audit` (`src/qiki/services/faststream_bridge/app.py:377-395`).
- Existing runtime registry already acknowledges multi-publisher reality on the audit subject (`TASK_OUT/runtime_registry.md:25`).

### What registrar must not do architecturally

- Must not be described as owner of world truth, radar truth, legality truth, or operator meaning.
- Must not be treated as the only publisher on `qiki.events.v1.audit`.
- Must not be used to infer “if registrar has it, then the original owner is registrar”. At most it proves observation/forwarding by registrar.
- Must not replace upstream owner subjects in incident or blocker analysis.

## 5. Failure / degradation behavior

### Proven behavior

- Startup depends on NATS being healthy in compose (`docker-compose.phase1.yml:243-254`).
- If local file write fails, registrar logs an error and continues; no retry or alternate sink exists (`src/qiki/services/registrar/core/service.py:73-80`).
- If audit republish fails, registrar logs a warning and continues; file write has already happened in both handlers (`src/qiki/services/registrar/main.py:66-77`, `src/qiki/services/registrar/main.py:102-123`, `src/qiki/services/registrar/main.py:140-148`).

### Temporary NATS loss

- There is no code proof of registrar-specific reconnect/backfill handling, no explicit disconnect events, and no replay path in registrar code.
- Because subscribers are declared without explicit durable/pull/stream settings, there is no evidence-backed guarantee that registrar catches up after a temporary gap.
- Best evidence-backed statement:
  - if a message reaches a handler and republish fails, registrar still leaves a local file record;
  - if NATS is unavailable before delivery, registrar has no proven way to observe or reconstruct the missed event.

### Recursion / duplication risk

- Infinite self-recursion is partially guarded: registrar skips events where `source=="registrar"` and `event_type` is `SYSTEM_EVENT` or `RADAR_FRAME_RECEIVED` (`src/qiki/services/registrar/main.py:130-135`).
- That guard is narrow. Third-party messages already published to `qiki.events.v1.audit` are still matched by `qiki.events.v1.>` and get wrapped once more as registrar `SYSTEM_EVENT`.
- Result:
  - no clear infinite loop from current code path,
  - but real one-step duplication / re-audit noise risk exists for external audit events.

## 6. What registrar helps prove

### Useful for blocker investigations

- Registrar startup happened:
  - local `BOOT_EVENT` proves service booted and opened its local sink.
- A radar union frame reached registrar:
  - `RADAR_FRAME_RECEIVED` proves at least `frame_id`, `sensor_id`, and `detections_count` were seen by registrar.
  - This is useful to separate:
    - “q-sim never published”
    - from “publisher emitted but registrar never saw it”
    - from “registrar saw it but downstream audit republish failed”.
- Some event payload crossed the `qiki.events.v1.>` surface and was seen by registrar:
  - registrar `SYSTEM_EVENT` proves observation of that payload by wildcard intake.
- External audit-side facts remain useful, even when not owned by registrar:
  - `q_core_intents` hidden observation events on `qiki.events.v1.audit` are useful for observation blocker timelines.
  - `faststream_bridge` proposal-accept audit events are useful for legality/execution investigations.

### What registrar cannot prove

- It cannot prove world state correctness.
- It cannot prove command legality or proposal ownership.
- It cannot prove that every event in `qiki.events.v1.audit` was authored by registrar.
- It cannot prove absence of dropped events during NATS degradation.
- It cannot provide a complete replay ledger for upstream subjects.

### What is missing for normal forensic diagnosis

- No persisted original NATS metadata: no stream sequence, consumer sequence, redelivery count, or ack status.
- No explicit capture of original subject on registrar-generated wrapper records except inside nested payload conventions.
- No correlation field linking ingress event to republished audit record beyond copied payload and generated `event_id`.
- Radar audit keeps only `frame_id`, `sensor_id`, `detections_count`; it drops raw detections, track IDs, timing deltas, and header metadata.
- Code enum suggests comms/NATS lifecycle events (`NATS_CONNECTED`, `NATS_DISCONNECTED`) exist conceptually, but runtime code does not emit them (`src/qiki/services/registrar/core/codes.py`, `rg RegistrarCode usage` only shows radar-frame use in runtime code).
- No built-in file rotation or retention proof for `/var/log/qiki/registrar.log`.

## 7. Drift / ambiguity

- `docs/stage0_actual_plan.md:32` says registrar should have an event intake API and local file rotation. Code has neither API nor rotation.
- `docs/0_step.md:205-211` says `qiki.events.v1.audit` retention is “work-queue + max_age” and registrar is a singleton writing everything significant. Current `tools/js_init.py` proves file-backed stream with `max_age`/`max_bytes`, but that exact “work-queue” wording is not reflected in code, and audit subject is not single-writer.
- `TASK_OUT/runtime_registry.md:11` says entrypoint is `python -m qiki.services.registrar.main` via container default. Actual Docker default is `python src/qiki/services/registrar/main.py`.
- `TASK_OUT/runtime_registry.md:25` already notes multi-publisher reality on `qiki.events.v1.audit`; this should override any lingering interpretation that registrar exclusively owns that subject.
- Registrar code ranges are broader than runtime use:
  - docs/plan mention `BOOT_OK`, `SENSOR_IO_OK` style code-based events,
  - runtime currently emits boot/sensor/system events, but only the radar path clearly injects a `RegistrarCode` in live code (`src/qiki/services/registrar/main.py:102-110`).

## 8. Minimal next task candidates

- Prove live degradation behavior narrowly:
  - capture one controlled NATS interruption window and verify exactly what survives in `/var/log/qiki/registrar.log` versus `QIKI_EVENTS_V1 / qiki.events.v1.audit`.
- Build a recursion/noise dossier:
  - publish one direct external audit event from `q_core_intents` or a probe and verify whether registrar wraps it once as `SYSTEM_EVENT`.
- Produce a forensic-gap matrix for registrar only:
  - ingress subject
  - source timestamp
  - registrar ingest timestamp
  - republish timestamp
  - local file line presence
  - JetStream persistence presence
- Sync docs to current evidence only:
  - remove unproven claims about intake API, single-writer audit, and rotating local file.

