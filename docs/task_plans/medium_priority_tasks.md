# Medium Priority Tasks (P3)

> HISTORICAL/REFERENCE ONLY (NOT CANON) / ИСТОРИЯ/СПРАВКА (НЕ КАНОН)  
> Канон приоритетов (что сейчас важно) живёт только в `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.  
> Этот файл не является «Now/Next/Backlog» и не должен использоваться как источник текущих приоритетов.  
> Marked: 2026-01-22

## P3-001: Radar Track Store Core
- **Description**: Implement a stateful radar track store with Alpha‑Beta filtering, detection association, and track lifecycle management, replacing the existing stateless `frame_to_track` stub.
- **Tasks**:
  - Develop a `TrackStore` class that maintains active tracks and updates them using Alpha‑Beta filters based on polar coordinates (range, bearing, doppler).
  - Implement detection‑to‑track association, create new tracks, update existing tracks, and retire tracks based on hit/miss counters and track status (`NEW`, `TRACKED`, `LOST`).
  - Extend the `RadarTrackModel` to include position/velocity vectors, covariance, track status, quality metrics, transponder mode and ID.
  - Export track metrics (active tracks, frame latency, redeliveries) via Prometheus.
  - Update unit and integration tests (`test_radar_track_store.py`, `test_radar_handlers.py`) accordingly.
- **Estimated Time**: 1 week.

## P3-002: Radar Guard Rules Integration
- **Description**: Integrate radar guard rules into the finite state machine (FSM) and world model, enabling automated safety responses.
- **Tasks**:
  - Implement a parser for `guard_rules.yaml` defining events such as `UNKNOWN_CONTACT_CLOSE`, `FOE_TRANSPONDER_OFF_APPROACH`, and `SPOOFING_DETECTED` with distance thresholds.
  - Inject guard rules into the radar processing pipeline; generate events (`RADAR_ALERT_*`) and update the world model when thresholds are violated.
  - Link FSM events produced by the guard rules to the RuleEngine to trigger transitions (e.g., IDLE → ACTIVE or ERROR_STATE).
  - Export guard‑related metrics from the world model for monitoring.
  - **Guard Integration Polish**: separate configuration into its own package, add schema/validation for guard YAML, automate containerized pytest without symlink, and reduce long‑line violations (E501).
- **Estimated Time**: 3–5 days.

## P3-003: Radar Visualization UI
- **Description**: Design and implement a visualization tool for radar data and tracks to support operators and developers.
- **Tasks**:
  - Develop a UI (web or desktop) that displays radar frames and tracks in real time; include filtering, zoom, and overlay of guard‑rule boundaries.
  - Integrate metrics (latency, active tracks) and allow toggling display of transponder modes and quality indicators.
  - Provide controls for pausing/resuming playback and stepping through recorded sessions.
  - Optionally use Python libraries like Dash, Plotly or a desktop framework.
- **Estimated Time**: 1‑2 weeks.

## P3-004: JetStream Metrics Extension
- **Description**: Extend observability of the NATS/JetStream pipeline.
- **Tasks**:
  - Add Prometheus/OpenTelemetry metrics to track message latency, backlog, ack rates, and dropped/redelivered messages for both frame and track subjects.
  - Expose these metrics via an HTTP endpoint or integrate with the existing monitoring stack.
  - Update dashboards to visualize radar pipeline health.
- **Estimated Time**: 3–5 days.

## P3-005: gRPC Migration Completion
- **Description**: Finish migrating all services to use gRPC and remove legacy communication layers.
- **Tasks**:
  - Ensure all APIs are defined in protobuf and have corresponding service implementations.
  - Remove obsolete REST or custom message handlers.
  - Update clients and tests to use the gRPC API exclusively.
  - Document new API endpoints and update AsyncAPI specifications accordingly.
- **Estimated Time**: 1 week.
