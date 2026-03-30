## Service Registry

| Service | Runtime role | Main entrypoint | Compose participation | Inputs | Outputs | Supported path | Alternate path | Legacy / archive indicators |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `q_sim_service` | Simulation truth owner: world tick, gRPC sim API, control ACK emitter, radar/telemetry/events publisher | `python -m qiki.services.q_sim_service.grpc_server` | `docker-compose.phase1.yml`; also present in `docker-compose.yml`, `docker-compose.minimal.yml` | Subjects: `qiki.commands.control`.<br>Endpoints: gRPC `:50051` (`HealthCheck`, `GetSensorData`, `SendActuatorCommand`, `GetRadarFrame`).<br>APIs: NATS, JetStream, gRPC. | Subjects: `qiki.responses.control`, `qiki.radar.v1.frames.lr`, `qiki.radar.v1.tracks.sr`, `qiki.radar.v1.frames`, `qiki.telemetry`, `qiki.events.v1.sensor.thermal`, `qiki.events.v1.sensor.thermal.trip`, `qiki.events.v1.power.bus`, `qiki.events.v1.power.pdu`.<br>Endpoints: gRPC `:50051`.<br>APIs: gRPC server, NATS publishers. | `docker-compose.phase1.yml` baseline contour. | Same service also appears in root/minimal mixed stacks. | No explicit archive marker found. Root/minimal participation is not current primary contour. |
| `q_core_agent/main.py` | Main agent tick runtime (`qiki-dev`): consumes sim truth via gRPC + BIOS HTTP, evaluates state/proposals, can send actuator commands via gRPC | `python -m qiki.services.q_core_agent.main --grpc` | `docker-compose.phase1.yml`; also present in `docker-compose.yml`, `docker-compose.minimal.yml` | Subjects: none in canonical path.<br>Endpoints: BIOS HTTP base `BIOS_URL` -> `/bios/status`; gRPC target `q-sim-service:50051`.<br>APIs: `GrpcDataProvider`, BIOS HTTP client, gRPC client. | Subjects: none on canonical NATS path proven here.<br>Endpoints: outbound gRPC `SendActuatorCommand` to `q-sim-service:50051`.<br>APIs: gRPC client; local logging/event store. | Phase1 `qiki-dev` service in supported contour. | Root/minimal mixed runtimes; local `--mock` CLI mode. | Dual-role family with separate `q-core-intents` deployment. `--mock` path is non-canonical for runtime contour. |
| `q_core_agent/qiki_orion_intents_service.py` | Dedicated QIKI intent listener and response generator; enriches replies with world snapshot from sim/bios context | `python -m qiki.services.q_core_agent.qiki_orion_intents_service` | `docker-compose.phase1.yml`; also isolated overlay in `docker-compose.qcore-intents.yml` | Subjects: `qiki.intents`, `qiki.secrets.v1.openai_api_key`, `qiki.events.v1.operator.objectives`, `qiki.events.v1.operator.actions`.<br>Endpoints: outbound BIOS HTTP default `http://q-bios-service:8080/bios/status`; outbound gRPC to `q-sim-service:50051` via `GrpcDataProvider`.<br>APIs: NATS, BIOS HTTP, gRPC. | Subjects: `qiki.responses.qiki`, `qiki.events.v1.operator.objectives`, `qiki.events.v1.audit`.<br>Endpoints: none exposed.<br>APIs: NATS publishers. | Supported owner of `qiki.intents -> qiki.responses.qiki` in `docker-compose.phase1.yml`. | Same runtime can be enabled via `docker-compose.qcore-intents.yml`; code-level overlap remains with bridge intent handler. | Not archive, but operationally distinct from `q_core_agent/main.py`; this is the active side of the dual-role ambiguity. |
| `faststream_bridge` | Radar pipeline bridge: consumes radar frames, emits canonical `qiki.radar.v1.tracks`; also retains latent QIKI-intent/proposal-execution route | `faststream run qiki.services.faststream_bridge.app:app` | `docker-compose.phase1.yml`, `docker-compose.yml`, `docker-compose.minimal.yml` | Subjects: `qiki.radar.v1.frames`; alternate latent input `qiki.intents` via `_QIKI_INTENTS_SUBJECT`.<br>Endpoints: none exposed.<br>APIs: FastStream + NATS/JetStream. | Subjects: `qiki.radar.v1.tracks`; alternate/conditional outputs `qiki.responses.qiki`, `qiki.commands.control`, `qiki.events.v1.audit`, `qiki.events.v1.system_mode`, `qiki.events.v1.radar.guard`.<br>Endpoints: none.<br>APIs: FastStream publishers. | Supported only as radar/system bridge in Phase1, with `QIKI_INTENTS_SUBJECT=qiki.intents.faststream_disabled`. | Code still contains live handler for `qiki.intents -> qiki.responses.qiki`; proposal ACCEPT flow can publish `qiki.commands.control`. | No explicit archive marker, but intent path is alternate/non-canonical and must not be read as current owner path. |
| `operator_console / ORION V` | Canonical operator ingress/UI surface; consumes telemetry/tracks/events/replies, emits control commands and QIKI intents | `python main_orion_v.py` / `python -m qiki.services.operator_console.main_orion_v` | Supported overlay: `docker-compose.operator.yml` on top of `docker-compose.phase1.yml`; transitional `docker-compose.operator_orionv.yml`; mixed root `docker-compose.yml`; legacy override `docker-compose.operator_legacy.yml` | Subjects: `qiki.telemetry`, `qiki.radar.v1.tracks`, `qiki.events.v1.>`, `qiki.responses.control`, `qiki.responses.qiki`.<br>Endpoints: interactive TTY/tmux surface.<br>APIs: NATS/JetStream client; gRPC channel to `q-sim-service:50051` for connectivity/health-level use only. | Subjects: `qiki.commands.control`, `qiki.intents`, `qiki.events.v1.operator.actions`, `qiki.events.v1.operator.procedures`, `qiki.events.v1.operator.incidents`, `qiki.events.v1.operator.combat`, `qiki.events.v1.operator.objectives`.<br>Endpoints: none exposed.<br>APIs: NATS publisher. | `docker-compose.phase1.yml` + `docker-compose.operator.yml` + `./scripts/run_orion_v_live.sh`. | Root mixed compose; transitional `docker-compose.operator_orionv.yml`; legacy override/profile. | `src/qiki/services/operator_console/main.py` is explicitly marked `LEGACY / ARCHIVE ENTRYPOINT`; `docker-compose.operator_legacy.yml` exists for isolated legacy console. |
| `q_bios_service` | BIOS/health sidecar: computes hardware/POST status from bot config + q-sim health, exposes BIOS HTTP, publishes BIOS status events | `python -m qiki.services.q_bios_service.main` | `docker-compose.phase1.yml` | Subjects: none consumed on NATS path.<br>Endpoints: HTTP `:8080` -> `/healthz`, `/bios/status`, `/bios/component/<id>`, `/bios/reload`.<br>APIs: outbound gRPC health check to `q-sim-service:50051`. | Subjects: `qiki.events.v1.bios_status`.<br>Endpoints: HTTP `:8080`.<br>APIs: HTTP server, NATS publisher. | Phase1 sidecar in supported contour. | No separate compose overlay found. | No explicit archive marker found. |
| `registrar` | Black-box audit recorder: consumes radar/events streams, writes local log, republishes audit records to canonical audit subject | `python -m qiki.services.registrar.main` via container default | `docker-compose.phase1.yml`, `docker-compose.yml`, `docker-compose.minimal.yml` | Subjects: `qiki.radar.v1.frames`, `qiki.events.v1.>`.<br>Endpoints: local log file `/var/log/qiki/registrar.log`.<br>APIs: FastStream + NATS/JetStream. | Subjects: `qiki.events.v1.audit`.<br>Endpoints: local file output only.<br>APIs: FastStream publisher. | Phase1 audit service. | Root/minimal mixed stacks. | No explicit archive marker found. |
| `qiki_chat` | Standalone legacy/non-canonical chat ingress using request-reply on a separate subject | `python -m qiki.services.qiki_chat.main` | No compose participation found in current compose files | Subjects: `qiki.chat.v1`.<br>Endpoints: none exposed.<br>APIs: plain NATS request-reply. | Subjects: none fixed; replies via `msg.respond(...)` reply subject rather than canonical `qiki.responses.qiki`.<br>Endpoints: none.<br>APIs: NATS responder. | Not part of supported canonical contour. | Can be run standalone as an alternate ingress path. | Non-canonical ingress by design for current contour; absent from supported compose stack. |
| `shell_os` | Support overlay TUI for host/runtime inspection; reads local system/docker/NATS reachability, not operator canon | `python main.py` | `docker-compose.shell_os.yml` overlay on top of Phase1 external network | Subjects: none subscribed.<br>Endpoints: interactive TTY; best-effort TCP reachability checks to `NATS_URL`; host `docker ps` via subprocess.<br>APIs: local OS/process/socket probes. | Subjects: none published.<br>Endpoints: none exposed.<br>APIs: no canonical runtime bus output. | Not part of supported operator contour. Support-only overlay. | Optional overlay on top of Phase1 network. | Support overlay only; must not be read as canonical operator ingress. |

## Subject Ownership Registry

| Subject | Supported owner / publisher | Supported consumer / owner side | Alternate / latent publisher or path | Notes |
| --- | --- | --- | --- | --- |
| `qiki.intents` | `operator_console / ORION V` publishes operator intents | `q_core_agent/qiki_orion_intents_service.py` is supported owner/consumer in Phase1 | `faststream_bridge` still contains a live subscriber for `_QIKI_INTENTS_SUBJECT`, but Phase1 disables it with `qiki.intents.faststream_disabled` | Ownership is contour-driven, not fully collapsed at code level. |
| `qiki.responses.qiki` | `q_core_agent/qiki_orion_intents_service.py` | `operator_console / ORION V` subscribes | `faststream_bridge` retains latent publisher path via `@broker.publisher(_QIKI_RESPONSES_SUBJECT)` | Supported publisher is `q-core-intents`; bridge path is alternate only. |
| `qiki.commands.control` | `operator_console / ORION V` direct command path | `q_sim_service` subscribes and applies control commands | `faststream_bridge` can also publish on accepted proposal execution; legacy `main_orion.py` can publish outside canon | Current supported ingress is ORION V; bridge publish is valid but alternate/conditional. |
| `qiki.responses.control` | `q_sim_service` | `operator_console / ORION V` subscribes | No active code publisher found in `faststream_bridge`; old docs claiming bridge ownership are drift | This ownership is code-backed and materially different from some older docs. |
| `qiki.radar.v1.frames` | `q_sim_service` publishes union radar frames | `faststream_bridge` and `registrar` subscribe; older operator realtime client can also subscribe | LR/SR side subjects also exist: `qiki.radar.v1.frames.lr`, `qiki.radar.v1.tracks.sr` | Canonical union-frame publisher is `q_sim_service`. |
| `qiki.radar.v1.tracks` | `faststream_bridge` | `operator_console / ORION V` subscribes; other services may consume | `q_sim_service` publishes only `qiki.radar.v1.tracks.sr`, not canonical union `qiki.radar.v1.tracks` | Canonical union-track publisher is bridge. |
| `qiki.events.v1.audit` | `registrar` is the canonical audit aggregator/publisher | `operator_console / ORION V` consumes audit feed through wildcard events stream | `q_core_agent/qiki_orion_intents_service.py` directly publishes hidden observation audit events; `faststream_bridge` directly publishes proposal-accept audit events | This subject already has multi-publisher reality. Registrar is canonical black-box owner, but not the exclusive emitter. |

## Ambiguities / Drifts

- `q_core_agent` has a real dual-role split.
  `main.py` is the Phase1 agent tick runtime (`qiki-dev`), while `qiki_orion_intents_service.py` is a separate deployed intent listener (`q-core-intents`).
  They share code family and context sources, but they are not the same runtime role.

- `faststream_bridge` still contains an alternate intent path.
  Code-level subscriber/publisher for `qiki.intents -> qiki.responses.qiki` still exists.
  The supported contour suppresses it by compose env override, so this is latent/alternate, not canon.

- `qiki_chat` is a non-canonical ingress.
  It listens on `qiki.chat.v1` and answers through request-reply.
  It is absent from supported compose files and does not participate in the canonical `qiki.intents -> qiki.responses.qiki` contour.

- `shell_os` is a support overlay, not an operator runtime owner.
  It reads local runtime state and NATS reachability.
  It does not own canonical subjects and should not be treated as operator ingress.

- `qiki.events.v1.audit` is not single-writer in code.
  Registrar is the canonical audit service, but direct publishers also exist in `q-core-intents` and `faststream_bridge`.
  This is a real multi-publisher subject, not just a docs issue.

- Older docs still drift on control ownership.
  Some architecture text still attributes `qiki.commands.control` consumption and `qiki.responses.control` publishing to bridge.
  Current code shows `q_sim_service` as the actual control consumer/ACK publisher.

## Safe Conclusions vs Unresolved Points

### Safe conclusions

- The supported canonical contour for runtime/tasking is `docker-compose.phase1.yml` plus `docker-compose.operator.yml`, with ORION V launched through `./scripts/run_orion_v_live.sh`.
- `q_core_agent/main.py` and `q_core_agent/qiki_orion_intents_service.py` must be treated as separate deployment roles.
- Supported ownership of `qiki.intents -> qiki.responses.qiki` is:
  `operator_console / ORION V` publishes `qiki.intents`;
  `q-core-intents` consumes `qiki.intents` and publishes `qiki.responses.qiki`.
- Supported ownership of `qiki.commands.control -> qiki.responses.control` is:
  `operator_console / ORION V` publishes control commands;
  `q_sim_service` consumes them and publishes control responses.
- Canonical radar path is:
  `q_sim_service` publishes radar frames;
  `faststream_bridge` publishes canonical union tracks;
  `operator_console / ORION V` consumes tracks.
- `qiki_chat` and `shell_os` remain visible runtime surfaces, but they are not part of the supported canonical ingress/operator path.

### Unresolved points

- `faststream_bridge` still carries live code for the alternate QIKI intent route.
  Compose disables it in the supported contour, but the code path still exists and could be reactivated by env/config change.

- `qiki.events.v1.audit` does not currently have an exclusive single publisher.
  Registrar is the canonical audit owner, but the subject is also written to directly by other services.

- Root/mixed compose files (`docker-compose.yml`, `docker-compose.minimal.yml`) still expose overlapping runtime surfaces.
  They should be treated as non-primary/transitional unless a new canon explicitly promotes them.
