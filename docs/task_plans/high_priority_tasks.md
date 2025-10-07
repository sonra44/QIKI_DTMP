# High Priority Tasks (P2)

## P2-001: Q-Operator Console MVP
- **Description**: Develop a minimal operator console with three interfaces: a command-line interface (CLI) using Python Click + Rich, a text-based user interface (TUI) using Rich/Textual, and a basic web interface built with FastAPI and simple HTML/CSS.
- **Components**:
  - CLI: commands to view system state, logs, metrics, and manage services.
  - TUI: real-time monitoring dashboard with metrics, log stream, and control actions.
  - Web UI: simple dashboard summarizing system status and offering control operations.
- **Goals**: Provide operators with unified tools for state monitoring, debugging, and control of Q-Core Agent and services.
- **Estimated Time**: 1‑2 weeks.

## P2-002: Event Store Implementation
- **Description**: Implement a persistent event store for the QIKI_DTMP platform using SQLite and an event-sourcing pattern.
- **Details**:
  - Create tables for events with a serializable format (protobuf/JSON).
  - Provide API for writing events, querying by time range, and reconstructing state.
  - Integrate with `AsyncStateStore`; ensure >1,000 events/sec throughput.
  - Support audit trail and recovery of agent state.
- **Estimated Time**: 1 week.

## P2-003: STEP‑A Thrust Allocator
- **Description**: Build the thrust allocation subsystem for a bot equipped with 16 RCS thrusters organized into four clusters (4×4) as described in the design document (`bot_gdd.md`).
- **Tasks**:
  - Implement thrust allocation algorithms (quadratic programming or NNLS) that distribute thrust to satisfy the desired translation/rotation while respecting symmetrical cluster orientation, as outlined in the bot design (ZTT and FTG groups).
  - Support pulsed thrust modulation (PWPF/bang‑bang) for thrusters that cannot throttle continuously.
  - Enforce energy and thermal constraints: maximum power 45 kW, battery/condenser SoC thresholds (`T_boost = 0.6`, `T_hold = 0.3`) and thermal cooldown windows.
  - Include adaptive override modes (`AUTO`/`ADAPTIVE`/`MANUAL_OVERRIDE`) and zero‑torque translation (ZTT) and full thrust group (FTG) sets, as well as torque maps for roll/pitch/yaw.
  - Integrate with the energy system (Power Plane) to respect power budgets and record telemetry.
- **Estimated Time**: 1 week.

## P2-004: STEP‑A Docking & XPDR
- **Description**: Implement the docking finite state machine and transponder subsystem for bot‑to‑bot and bot‑to‑station connections.
- **Tasks**:
  - Create a docking state machine with phases: Align → Soft Dock → Hard Dock → Bridge.
  - Support power/data/full docking profiles with automatic locking and unlocking; ensure cascade docking (bridge mode).
- **Transponder**:
  - Implement transponder modes: ON, OFF, SILENT, SPOOF, with IFF identifiers.
  - Integrate transponder modes into radar track data (`RadarTrackModel`) and the world model.
  - Support spoofing detection scenarios as described in the radar guard rules.
- **Estimated Time**: 1 week.

## P2-005: Docker Production Setup
- **Description**: Prepare the project for production deployment.
- **Tasks**:
  - Create optimized production Dockerfiles with separate stages for build and runtime.
  - Provide environment-specific compose files (dev vs. prod) with secrets management.
  - Add health‑check definitions for all services and integrate Prometheus metrics exporters.
  - Include monitoring and logging stacks (Prometheus, Grafana, Loki) for observability.
- **Estimated Time**: 3–5 days.
