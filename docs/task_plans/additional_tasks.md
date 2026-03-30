# Additional Tasks for QIKI_DTMP

> HISTORICAL/REFERENCE ONLY (NOT CANON) / ИСТОРИЯ/СПРАВКА (НЕ КАНОН)  
> Канон приоритетов (что сейчас важно) живёт только в `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.  
> Этот файл не является «Now/Next/Backlog» и не должен использоваться как источник текущих приоритетов.  
> Marked: 2026-01-22

## Observability & Metrics

- Instrumentation of JetStream, gRPC, and sensors; integrate Prometheus and OpenTelemetry to collect latency, throughput, error rates, CPU/memory usage.
- Provide dashboards and alerting (Grafana) to monitor pipeline health, track counts, guard events.
- Export metrics from WorldModel and GuardTable, including counts of tracks, guard events by type, and track quality metrics.

## AsyncAPI & CI Automation

- Automate generation of AsyncAPI and protobuf docs; integrate with CI pipelines to produce versioned artifacts.
- Validate API spec changes using linting tools (e.g., buf) and update `docs/asyncapi/radar_v1.yaml` accordingly.
- Publish generated docs to documentation sites and ensure cross-references with README and TASK_LIST.

## Load and Stress Testing

- Develop load tests that simulate high-rate radar frames and track updates to test JetStream, FastStream, and TrackStore; measure system throughput and latency under stress.
- Create stress scenarios for gRPC and NATS JetStream; evaluate resource consumption and system stability.
- Provide guidelines for scaling parameters (e.g., consumer memory, JetStream retention) based on test results.

## Guard Integration Polish

- Extract guard configuration into a standalone package and implement YAML schema/validation for guard rules.
- Export guard-related metrics from WorldModel (number of active guard events, severity distribution).
- Connect `fsm_event` from guard events to the RuleEngine for unified event processing.
- Automate container PyTest runs without requiring symlinks; adjust configuration to avoid E501 (long line) errors.

## Thruster & Energy Enhancements

- Refine thrust allocator by incorporating energy management: account for state-of-charge thresholds (`T_boost`, `T_hold`) and capacitor charging/discharging cycles.
- Implement PWM/PWPF modulation modules described in bot_gdd.md, ensuring respect for duty cycles, thermal limits, and peak-shaving.
- Develop SoC-aware control logic that limits continuous burn durations and triggers cooldown as defined in the GDD.
- Add power-plane controllers (MPPT, power path, load shedding) and integrate with Q -Core Agent telemetry.

## Multi-Sensor Perception & R.L.S.M Integration

- Extend TrackStore to support fused tracks from radar, lidar, spectrometer, and magnetometer; update models to include classification attributes and risk levels.
- Implement data association across sensors and state estimation (Kalman/Extended Kalman filters) as described in the GDD.
- Build a unified perception plane pipeline producing occupancy grids, track lists, and environmental maps; provide API to query fused perceptions.
- Design risk evaluation logic (TCAS-like) to trigger brake overrides or evasive maneuvers based on time-to-collision thresholds.

## Docking & Communications Enhancements

- Implement full docking connector API: states (retracted/locked/open/bridging), commands (open/close/dock/undock), and telemetry (current, voltage, temperature, role).
- Support bridge mode for power and data across cascaded docking; implement safety limits (anti-backflow, current/temperature thresholds).
- Develop NBL (Neutrino Burst Link) communication module with channel manager, QoS classes, E2E encryption, and budget-based scheduling.
- Integrate comms analytics: intrusion detection and anomaly alerts based on metadata patterns.

## Hardware Abstraction & Safety Systems

- Create hardware abstraction layer (Power Plane, Propulsion Plane, Sensor Plane, Safety Plane) to interface Q -Core Agent with low-level controllers.
- Implement FDIR (Fault Detection, Isolation and Recovery) with Safe mode, brake override logic, and sun-tracking idle mode to maximise energy recovery.
- Expose hardware plane telemetry (SoC_cap, ΣF, thermal readings, radiation) to the agent; implement regulators for energy budgets and thermal limitations.
- Define test scenarios to verify safe-mode transitions and failover across planes.

## Testing and CI Improvements

- Expand unit and integration tests to cover perception fusion algorithms, docking connectors, and energy controllers.
- Add continuous integration steps for load testing, AsyncAPI generation, documentation build and deployment, and multi-sensor simulation scenarios.
- Ensure test coverage remains above defined thresholds and automates regression detection across modules.
