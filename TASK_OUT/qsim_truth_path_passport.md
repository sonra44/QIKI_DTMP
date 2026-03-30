# q_sim_service truth path passport

## Subsystem Passport

### subsystem name

`q_sim_service`

### canonical role

Runtime truth owner for canonical contour physical state. It owns simulator time progression, world state, radar frame emission, telemetry snapshots, and minimal sim-origin events. It does not own policy, legality, or operator interpretation.

### source of truth

- Physical/runtime truth is born in `QSimService` plus `WorldModel`.
- gRPC truth seam is `src/qiki/services/q_sim_service/grpc_server.py` and `src/qiki/services/q_sim_service/service.py`.
- NATS truth seams are radar frame publish, telemetry snapshot publish, and sim event publish.
- Policy owner is not local: legality and downstream operational meaning live in `faststream_bridge` and consumer layers, not in `q_sim_service`.

### owning files/modules

- `src/qiki/services/q_sim_service/main.py`
- `src/qiki/services/q_sim_service/grpc_server.py`
- `src/qiki/services/q_sim_service/service.py`
- `src/qiki/services/q_sim_service/core/world_model.py`
- `src/qiki/services/q_sim_service/radar_publisher.py`
- `src/qiki/services/q_sim_service/telemetry_publisher.py`
- `src/qiki/services/q_sim_service/events_publisher.py`
- `src/qiki/shared/models/radar.py`
- `src/qiki/shared/models/telemetry.py`
- `src/qiki/shared/nats_subjects.py`

### inputs

- Config load: `main()` loads `config.yaml`, instantiates `QSimService`, then runs `sim_service.run()` in [`src/qiki/services/q_sim_service/main.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/main.py:10).
- Bot/hardware profile input: `QIKI_BOT_CONFIG_PATH` and `bot_config.json` drive comms enablement, xpdr init mode, and hardware hash in [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:49).
- Runtime env inputs: `RADAR_ENABLED`, `RADAR_NATS_ENABLED`, `TELEMETRY_NATS_ENABLED`, `EVENTS_NATS_ENABLED`, `NATS_URL`, `SYSTEM_TELEMETRY_SUBJECT`, `RADAR_TRANSPONDER_MODE`, `RADAR_TRANSPONDER_ID`.
- Control input: NATS `qiki.commands.control` consumer in [`src/qiki/services/q_sim_service/grpc_server.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py:132).
- gRPC actuator input: `SendActuatorCommand` writes into sim state in [`src/qiki/services/q_sim_service/grpc_server.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py:98).

### outputs

- gRPC `GetSensorData`: emits `SensorReading`; radar path carries `radar_data=proto_frame`, not `radar_track`, in [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:345).
- gRPC `GetRadarFrame`: emits raw radar frame on demand in [`src/qiki/services/q_sim_service/grpc_server.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py:107).
- NATS telemetry snapshot: `qiki.telemetry` by default, payload built by `_build_telemetry_payload()` and published by `TelemetryNatsPublisher.publish_snapshot()` in [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:680) and [`src/qiki/services/q_sim_service/telemetry_publisher.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/telemetry_publisher.py:68).
- NATS radar publish:
  - union frame subject `qiki.radar.v1.frames`
  - LR-only frame subject `qiki.radar.v1.frames.lr`
  - SR-only detection stream on subject `qiki.radar.v1.tracks.sr`
  in [`src/qiki/services/q_sim_service/radar_publisher.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/radar_publisher.py:18).
- NATS sim events:
  - `qiki.events.v1.sensor.thermal`
  - `qiki.events.v1.sensor.thermal.trip`
  - `qiki.events.v1.power.bus`
  - `qiki.events.v1.power.pdu`
  from `_maybe_publish_events()` and `_maybe_publish_thermal_trip_edges()` in [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:562) and [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:641).
- NATS control ACK: `qiki.responses.control` from `_build_control_response_payload()` in [`src/qiki/services/q_sim_service/grpc_server.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py:34).

### commands

- Accepted control commands in `apply_control_command()`:
  - `power.dock.on`
  - `power.dock.off`
  - `power.nbl.on`
  - `power.nbl.off`
  - `power.nbl.set_max`
  - `sim.start`
  - `sim.pause`
  - `sim.stop`
  - `sim.reset`
  - `sim.dock.engage`
  - `sim.dock.release`
  - `sim.rcs.stop`
  - `sim.rcs.fire`
  - `sim.xpdr.mode`
  in [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:176).
- `sim.xpdr.mode` accepts only `ON|OFF|SILENT|SPOOF`; comms-disabled hardware profile hard-rejects it.

### events / contracts

- Radar frame contract:
  - `RadarFrameModel` has `frame_id`, `sensor_id`, `timestamp`, `ts_event`, `ts_ingest`, `detections`.
  - `RadarDetectionModel` has range/bearing/elev/vr/snr/rcs plus `transponder_on`, `transponder_mode`, `transponder_id`, `range_band`, `id_present`.
  in [`src/qiki/shared/models/radar.py`](/home/sonra44/QIKI_DTMP/src/qiki/shared/models/radar.py:64).
- Telemetry contract:
  - top-level truth fields include `position`, `velocity`, `speed_m_s`, `velocity_xyz_m_s`, `heading`, `attitude`, `battery`, `power`, `docking`, `sensor_plane`, `comms`, `orbit`, `thermal`, `propulsion`, `radiation_usvh`, `temp_external_c`, `temp_core_c`, `hardware_profile_hash`, `sim_state`
  in [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:680) and [`src/qiki/shared/models/telemetry.py`](/home/sonra44/QIKI_DTMP/src/qiki/shared/models/telemetry.py:147).
- gRPC sensor contract:
  - q-core `GrpcDataProvider.get_sensor_data()` converts `GetSensorData.reading` into `SensorData`
  - when q-sim emits radar through gRPC, it is `SensorData.radar_frame`, not `SensorData.radar_track`
  in [`src/qiki/services/q_core_agent/core/grpc_data_provider.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/grpc_data_provider.py:152) and [`src/qiki/shared/converters/protobuf_pydantic.py`](/home/sonra44/QIKI_DTMP/src/qiki/shared/converters/protobuf_pydantic.py:310).

### dependencies

- `WorldModel` owns simulated physical state and gating like `radar_allowed` and `transponder_allowed`.
- `faststream_bridge` is downstream radar derivation/publish layer, not truth birth layer.
- `q-core` gRPC provider consumes q-sim sensor truth directly and can derive its own track identity from frames.
- ORION consumes bridge-published radar tracks plus telemetry/events and performs operator-facing comparison logic.

### operator-facing meaning

- ORION hardware and flight surfaces read q-sim telemetry as raw ship state.
- ORION radar identity cache reads bridge tracks, not raw q-sim frames.
- ORION `signature_changed` meaning is not q-sim-native; it is an operator projection computed later from downstream `track_id` plus label mutation.

### degraded / failure modes

- If sim is paused/stopped, telemetry and sensor data continue but radar publish is frozen in [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:503).
- If comms plane disabled by hardware profile, xpdr is forced `OFF` and control command is rejected.
- If world model load shedding or thermal rules disable transponder, telemetry can show mode plus `allowed=false` and degraded link metrics even when comms plane exists.
- q-sim does not publish durable track continuity as a first-class contract; downstream must derive it.

### provenance notes

- Runtime entrypoint proof: [`src/qiki/services/q_sim_service/main.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/main.py:10) and [`src/qiki/services/q_sim_service/grpc_server.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/grpc_server.py:194).
- Existing downstream evidence reused:
  - [`TASK_OUT/bridge_track_continuity_diagnostic.md`](/home/sonra44/QIKI_DTMP/TASK_OUT/bridge_track_continuity_diagnostic.md)
  - [`TASK_OUT/qcore_vs_orion_truth_comparison.md`](/home/sonra44/QIKI_DTMP/TASK_OUT/qcore_vs_orion_truth_comparison.md)
- Smoke/test evidence list gathered from:
  - `src/qiki/services/q_sim_service/tests/*`
  - `tests/integration/test_radar_lr_sr_fusion_sim_truth.py`
  - `tests/integration/test_radar_3d_sim_truth_nonzero_z.py`
  - `tests/integration/test_xpdr_gating_flow.py`
  - `tests/integration/test_control_ack_envelope.py`
  - `tests/integration/test_thermal_core_spike_event.py`
  - `tests/integration/test_thermal_core_trip_event.py`
  - `tests/integration/test_power_pdu_overcurrent_event.py`

### policy owner

- `q_sim_service` owns physical/runtime truth only.
- `faststream_bridge` owns radar frame to radar track derivation and track publication policy.
- `q-core` owns its own ingest interpretation and any local track-id synthesis from gRPC `radar_frame`.
- ORION owns operator-facing `signature_changed` comparison logic.

### canon vs projection notes

- Raw truth at q-sim:
  - world state
  - telemetry snapshot payload
  - radar frame detections
  - sim events
  - xpdr mode/id state
- Derived representation downstream:
  - bridge `RadarTrackStore` creates bridge-local `track_id` via `uuid4()` in [`src/qiki/services/faststream_bridge/radar_track_store.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:314).
  - q-core `WorldModel._track_from_detection()` creates local `track_id` from `uuid5(sensor_id, transponder_id-or-index)` when only frame truth exists in [`src/qiki/services/q_core_agent/core/world_model.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/world_model.py:117).
- Operator projection:
  - ORION caches bridge track payloads in `_latest_radar_tracks`
  - ORION uses `transponder_id or id or callsign` as visible label
  - ORION declares `signature_changed` only when same downstream `track_id` has a changed label
  in [`src/qiki/services/operator_console/orion_v/app.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py:432) and [`src/qiki/services/operator_console/orion_v/app.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py:1778).

### open risks

- q-sim does not self-publish a stable first-class radar `track_id`.
- `generate_radar_frame()` creates a fresh `sensor_id=uuid4()` every frame and `RadarFrameModel` auto-generates fresh `frame_id`, so frame identity is ephemeral, not stable track identity, in [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:434).
- For LR detection q-sim explicitly strips `transponder_id`; LR truth cannot carry identity by design.
- For SR detection, stable identity is only `transponder_id`, and that is mutable by mode.
- When `sim.xpdr.mode=SPOOF`, q-sim keeps object continuity physically but mutates external signature from `ALLY-*` to session-stable `SPOOF-*`; downstream layers may treat that as same object, new object, or missing identity depending on their own derivation rules.

### recommended next action

Capture one narrow supported resumed-observation window with synchronized evidence from:

- q-sim raw SR detection payload
- q-core gRPC-ingested `radar_frame` and local `world_snapshot`
- bridge `bridge_track_identity_mutation` / publish logs
- ORION `_latest_radar_tracks` snapshot and comparison log

Use one contour and one objective id only. Do not change subjects or execution logic.

## 1. q-sim runtime role

`q_sim_service` is the canonical runtime truth birthpoint for simulator-origin state. `main()` constructs `QSimService`; gRPC `serve()` constructs the same service, starts the gRPC server on `:50051`, and runs both the sim tick loop and NATS control consumer in background tasks. The core tick path is `tick() -> step() -> world_model.step() -> telemetry/events/sensor/radar publish` in [`src/qiki/services/q_sim_service/service.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py:503).

Truth ownership boundaries:

- q-sim owns world physics/state and the first externalized payloads.
- q-sim does not own legality or command admissibility beyond local runtime constraints.
- q-sim does not own canonical track identity downstream; it publishes detections and state, not stable radar tracks.

## 2. Truth publications

### Telemetry

Published by `_maybe_publish_telemetry()` to `qiki.telemetry`.

Payload classes/fields:

- `source="q_sim_service"`
- `timestamp`, `ts_unix_ms`
- `position {x,y,z}`
- `velocity`, `speed_m_s`, `velocity_xyz_m_s`
- `heading`, `attitude`
- `battery`
- `hull`, `power`, `docking`, `sensor_plane`, `orbit`, `thermal`, `propulsion`
- `comms`
- `radiation_usvh`, `temp_external_c`, `temp_core_c`
- optional `hardware_profile_hash`
- extra `sim_state`

The transponder/signature truth inside telemetry is under `comms.xpdr`:

- `mode`
- `active`
- `allowed`
- `id`

It also affects top-level comms link projections:

- `link`, `latency_ms`, `packet_loss_pct`, `rssi_dbm`, `snr_db`, `tx_power_w`, `data_rate_kbps`, `antenna_status`, `plane_profile`

### Radar

Published by `RadarNatsPublisher.publish_frame()`.

q-sim emits one union frame and two band-specific derivatives:

- `qiki.radar.v1.frames`: full frame, both detections preserved.
- `qiki.radar.v1.frames.lr`: LR-only publish; LR detection has `transponder_id=None`, `id_present=False`.
- `qiki.radar.v1.tracks.sr`: SR-only detection publish, but payload is still a frame-like object with `detections=[...]`, not a canonical `RadarTrackModel`.

Per-frame payload truth:

- `frame_id`
- `sensor_id`
- `timestamp` and `ts_ingest`
- `detections[]`

Per-detection truth:

- `range_m`, `bearing_deg`, `elev_deg`, `vr_mps`, `snr_db`, `rcs_dbsm`
- `transponder_on`
- `transponder_mode`
- `transponder_id`
- `range_band`
- `id_present`

Important constraint:

- `generate_radar_frame()` always creates two detections for the synthetic contact:
  - LR detection: no transponder identity
  - SR detection: carries transponder state/id when active

### Events

Published by `_maybe_publish_events()` and `_maybe_publish_thermal_trip_edges()`.

Current event payloads:

- `qiki.events.v1.sensor.thermal`
  - `schema_version`, `category=sensor`, `source=thermal`, `subject=core`, `temp`, `ts_epoch`, `unit=C`
- `qiki.events.v1.power.bus`
  - `schema_version`, `category=power`, `source=bus`, `subject=main`, `current`, `bus_v`, `ts_epoch`, `unit=A`
- `qiki.events.v1.power.pdu`
  - `schema_version`, `category=power`, `source=pdu`, `subject=main`, `overcurrent`, `pdu_limit_w`, `power_out_w`, `bus_a`, `bus_v`, `ts_epoch`
- `qiki.events.v1.sensor.thermal.trip`
  - `schema_version`, `category=sensor`, `kind=thermal_trip|thermal_clear`, `source=thermal`, `subject=core`, `tripped`, `temp`, `trip_c`, `hys_c`, `ts_epoch`, `unit=C`

### Control responses

Control consumer subscribes to `qiki.commands.control`; after local application it publishes ACK/error envelope to `qiki.responses.control` with:

- `version`
- `kind`
- `success`, `ok`
- `requestId`, `request_id`
- `timestamp`
- `payload.command_name`
- `payload.status`
- optional `error`, `error_detail`

## 3. Truth identity fields

### What q-sim itself publishes as identity

For the simulated contact, q-sim publishes these identity-relevant fields:

- `transponder_id`
- `transponder_mode`
- `transponder_on`
- `id_present`

It does not publish a durable canonical radar `track_id`.

Ephemeral identifiers only:

- `frame_id` is per-frame.
- `sensor_id` is regenerated per radar frame.

Implication:

- q-sim stable identity by itself exists only in the SR transponder/signature fields, not as a track uuid.
- LR truth has no identity-bearing label at all.

### Does q-sim publish stable track identity by itself

No.

Evidence:

- `generate_radar_frame()` creates `sensor_id=uuid4()` every frame.
- `RadarFrameModel` default `frame_id=uuid4()` also changes every frame.
- No method in q-sim constructs or persists a stable `track_id`.

### What q-core receives through its ingest path

Primary q-core ingest path is gRPC `GetSensorData`, not bridge NATS tracks.

What q-core gets:

- `SensorData.radar_frame` when q-sim sensor cycle produces radar.
- Not `SensorData.radar_track`.

Therefore q-core primary radar truth from q-sim is frame/detection truth, not stable downstream bridge track truth.

### Where q-core identity diverges from q-sim truth

`q_core_agent` local `WorldModel.ingest_sensor_data()` does:

- if `sensor_data.radar_track` exists, store that track directly
- else if only `radar_frame` exists, synthesize tracks per detection

Local synthesis rule:

- `track_key = detection.transponder_id or f"{sensor_id}:{index}"`
- `track_id = uuid5(NAMESPACE_URL, f"qiki-radar:{sensor_id}:{track_key}")`

Consequences:

- If SR detection has a transponder id, q-core track identity is derived from transponder id plus current frame sensor id.
- If no transponder id, q-core falls back to `sensor_id:index`.
- Because q-sim `sensor_id` changes every frame, q-core fallback identity is not stable across frames.
- If transponder id changes because of `SPOOF`, q-core can shift identity even if the physical contact is the same.

## 4. SPOOF-related state changes

`sim.xpdr.mode` with `mode=SPOOF` changes q-sim outward truth like this:

- `transponder_mode` becomes `SPOOF`.
- `_is_transponder_active()` remains `True`.
- `_resolve_transponder_id()` switches from normal `transponder_id` to a session-stable `_spoof_transponder_id` with prefix `SPOOF-`.
- Telemetry `comms.xpdr.id` becomes `SPOOF-*`.
- Radar SR detection `transponder_id` becomes `SPOOF-*`.
- Radar SR detection `transponder_on` stays `True`.
- Telemetry `comms.data_rate_kbps` changes to `96.0` for `SPOOF` instead of `192.0` for `ON`.

What does not change:

- q-sim does not create a new physical contact object.
- q-sim does not emit any stable canonical track id before or after spoof.
- LR detection remains identity-free.

Session stability proof:

- `test_xpdr_spoof_id_is_stable_per_session()` proves q-sim keeps one spoof id within the session in [`src/qiki/services/q_sim_service/tests/test_comms_plane.py`](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/tests/test_comms_plane.py:48).

## 5. Downstream consumers

### q-sim -> bridge

Bridge consumer:

- `faststream_bridge.handle_radar_frame()` subscribes to `qiki.radar.v1.frames` and validates raw `RadarFrameModel`.

Bridge receives from q-sim:

- union radar frame truth, not telemetry, not control ACK, not q-core world snapshot.

Bridge then derives:

- internal `_TrackState.track_id = uuid4()`
- updated `RadarTrackModel`
- publishes to `qiki.radar.v1.tracks`

Critical detail:

- bridge continuity can preserve the same bridge `track_id` across transponder/signature mutation if association holds.
- this is already evidenced in [`TASK_OUT/bridge_track_continuity_diagnostic.md`](/home/sonra44/QIKI_DTMP/TASK_OUT/bridge_track_continuity_diagnostic.md).

### q-sim -> q-core

q-core ingest path:

- `GrpcDataProvider.get_sensor_data()` calls q-sim gRPC `GetSensorData`.
- q-core ingests `SensorData.radar_frame` directly.

Therefore q-core does not primarily receive bridge `stable radar_track`.
It primarily receives a radar-frame-like representation from q-sim and can derive its own tracks locally.

This is the strongest identity-discontinuity seam upstream.

### q-sim -> ORION

Direct q-sim truth into ORION:

- telemetry via `qiki.telemetry`
- sim events via `qiki.events.v1.>`
- control ACK via `qiki.responses.control`

Indirect radar truth into ORION:

- ORION track cache is fed by bridge `qiki.radar.v1.tracks`, not by q-sim gRPC and not by raw q-sim frames for the canonical comparison path.

### Which downstream fields are critical for `signature_changed`

At ORION comparison time the critical fields are:

- previous objective `track_id`
- previous objective `track_label`
- live current `track_id`
- live current label resolved as `transponder_id or id or callsign`

`signature_changed` is emitted only if:

- previous `track_id == comparison track_id`
- both labels are non-empty
- previous label != comparison label

So the blocker-sensitive fields are not q-sim event fields directly; they are downstream `track_id` continuity plus label mutation visibility.

## 6. Where downstream identity can diverge from q-sim truth

### Divergence point 1: q-sim raw truth to bridge track truth

q-sim publishes detections with optional transponder identity but no stable `track_id`.
Bridge creates its own `track_id` and can mutate `transponder_id` in place on the same bridge track.

Result:

- bridge identity is derived identity
- label continuity may be preserved even when label changes

### Divergence point 2: q-sim raw truth to q-core local track truth

q-core ingests raw frame truth and synthesizes `track_id` from per-frame `sensor_id` plus detection-level identity material.

Result:

- if no transponder id, q-core identity is unstable because frame sensor id is unstable
- if transponder id mutates on spoof, q-core may shift to a different derived identity even though q-sim physical truth stayed on the same object

This aligns with the current strongest hypothesis: upstream q-core identity discontinuity is a more credible blocker than ORION-local comparison logic.

### Divergence point 3: bridge/q-core vs ORION operator projection

ORION does not compare raw q-sim truth. It compares:

- contour-stored identity
- bridge track cache label
- optional q-core-procedure fallback snapshot

So ORION can honestly return `reconfirmed` even when q-sim already changed outward signature, if downstream identity seam drifted first.

Existing evidence:

- [`TASK_OUT/qcore_vs_orion_truth_comparison.md`](/home/sonra44/QIKI_DTMP/TASK_OUT/qcore_vs_orion_truth_comparison.md) already shows a resumed contour where q-core drifted to another runtime track identity before ORION comparison.

## 7. Minimal next task candidates

### Narrow next tasks

1. q-sim raw truth proof for one resumed contour.
   Capture one synchronized window of raw q-sim SR detection payload before and after `sim.xpdr.mode=SPOOF`, including `frame_id`, `sensor_id`, `transponder_mode`, `transponder_id`, `range_band`, `id_present`.

2. q-core ingest proof.
   Log one synchronized window of q-core `latest_sensor_data.sensor_id`, incoming `radar_frame.detections`, and resulting `world_snapshot.radar_tracks[*].track_id/transponder_id` for the same contour.

3. bridge continuity proof on the same window.
   Capture `bridge_track_spawn`, `bridge_track_update`, `bridge_track_identity_mutation`, `bridge_track_published` for the same physical contact and same wall-clock interval.

4. ORION comparison proof on the same window.
   Capture `_latest_radar_tracks[track_id]` plus `Resume live snapshot` and `Resume comparison` for the same `objective_id`.

### Existing q-sim smoke/tests/harness

Unit tests directly covering q-sim truth path:

- `src/qiki/services/q_sim_service/tests/test_radar_generation.py`
- `src/qiki/services/q_sim_service/tests/test_radar_publisher_payload.py`
- `src/qiki/services/q_sim_service/tests/test_radar_publisher_headers.py`
- `src/qiki/services/q_sim_service/tests/test_sim_events_publishing.py`
- `src/qiki/services/q_sim_service/tests/test_comms_plane.py`
- `src/qiki/services/q_sim_service/tests/test_control_responses.py`
- `src/qiki/services/q_sim_service/tests/test_qsim_service.py`
- `src/qiki/services/q_sim_service/tests/test_rcs_control_commands.py`
- `src/qiki/services/q_sim_service/tests/test_rcs_propulsion.py`
- `src/qiki/services/q_sim_service/tests/test_power_plane.py`
- `src/qiki/services/q_sim_service/tests/test_thermal_plane.py`
- `src/qiki/services/q_sim_service/tests/test_docking_plane.py`

Integration tests/harness touching q-sim outbound truth:

- `tests/integration/test_radar_lr_sr_fusion_sim_truth.py`
- `tests/integration/test_radar_3d_sim_truth_nonzero_z.py`
- `tests/integration/test_xpdr_gating_flow.py`
- `tests/integration/test_control_ack_envelope.py`
- `tests/integration/test_thermal_core_spike_event.py`
- `tests/integration/test_thermal_core_trip_event.py`
- `tests/integration/test_power_pdu_overcurrent_event.py`
- `scripts/run_integration_tests_docker.sh`
- `scripts/start_sim.sh`
- `scripts/smoke_virtual_hardware.sh`

Operator-adjacent smokes that exercise q-sim as live source:

- `tools/orion_v_qiki_comms_combat_constraint_smoke.py`
- `tools/orion_v_qiki_hostile_power_gate_smoke.py`
- `tools/orion_v_qiki_combat_system_consequence_smoke.py`
- `tools/orion_v_qiki_thermal_followup_constraint_smoke.py`
