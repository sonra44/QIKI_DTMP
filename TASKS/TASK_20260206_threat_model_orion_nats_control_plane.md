# TASK: Threat model (lightweight) - ORION -> NATS control plane

Date: 2026-02-06

## Scope
In-scope: Phase1 operator control plane where ORION publishes to NATS and services consume.

Evidence entrypoints / subjects:
- NATS is started with JetStream and HTTP monitoring port, no auth configured in compose:
  - `docker-compose.phase1.yml` publishes `4222:4222` and `8222:8222`, runs `nats --jetstream --http_port 8222`
  - `Dockerfile.nats` is `FROM nats:2.10-alpine` (no auth config baked in)
- Canonical subject names: `src/qiki/shared/nats_subjects.py`
- ORION publishes control commands: `src/qiki/services/operator_console/main_orion.py` (`COMMANDS_CONTROL`)
- QSim consumes control commands: `src/qiki/services/q_sim_service/grpc_server.py` (`COMMANDS_CONTROL` -> `apply_control_command`)
- QCore agent consumes OpenAI API key updates: `src/qiki/services/q_core_agent/qiki_orion_intents_service.py` (`OPENAI_API_KEY_UPDATE`)
- ORION subscribes to responses/events without authentication:
  - `src/qiki/services/operator_console/clients/nats_client.py` (`RESPONSES_CONTROL`, `QIKI_RESPONSES`, `EVENTS_V1_WILDCARD`, `SYSTEM_TELEMETRY`)

Out-of-scope:
- General OS/container hardening, internet exposure outside the host running docker compose.
- Non-control telemetry (radar frames/tracks) beyond spoofing/DoS relevance.

## Assumptions (explicit, affect priority)
1. Phase1 is a dev/operator environment where host network access might include other machines/users (because NATS ports are bound on `0.0.0.0` by default when using `4222:4222`).
2. NATS has no auth/TLS in this Phase1 compose (no evidence of user/pass/token flags).
3. Any process that can reach NATS can publish to control subjects; no message signing is implemented.

## System model (minimal)
Components:
- ORION operator console (Textual TUI) publishes control commands and operator action events.
- NATS broker (JetStream enabled) routes control/events/telemetry.
- QSim service consumes `qiki.commands.control` and drives simulation state.
- Faststream bridge consumes operator intents and can publish some control commands (proposal accept path).
- QCore agent consumes `qiki.secrets.v1.openai_api_key` and sets `OPENAI_API_KEY` runtime env.

Trust boundaries:
- Operator terminal -> ORION process (trusted operator input, but local code execution risk is out-of-scope here).
- ORION -> NATS (network boundary; currently unauthenticated).
- NATS -> consumers (QSim / QCore agent / bridge) (network boundary; currently unauthenticated).

## Assets (what we protect)
- Simulation integrity (control commands must reflect operator intent, not attacker intent).
- Operator decision integrity (UI must not be spoofed with fake responses/events).
- Availability of NATS and consumers (DoS on control plane degrades operator capability).
- Secrets: OpenAI API key (`OPENAI_API_KEY`) runtime value.

## Attacker capabilities (realistic)
- Can connect to host-exposed NATS port `4222` (same LAN / same host / compromised container).
- Can publish/subscribe arbitrary subjects if NATS has no auth.
- Can flood subjects to degrade service.

Non-capabilities (assumed):
- Cannot bypass code-level validation once inside a consumer, except by sending valid payloads.
- Cannot directly access container filesystem/host unless separately compromised.

## Threats (top 3 abuse paths)

### T1: Unauthorized control command injection (integrity)
Path:
1. Attacker publishes JSON to `qiki.commands.control` (`COMMANDS_CONTROL`).
2. `q_sim_service` subscribes and validates with `CommandMessage.model_validate(...)`, then calls `apply_control_command`.
3. If the command name/params pass allow checks, sim state changes.

Impact: High (operator loses trust, sim integrity compromised; can cause unsafe actions in later phases).
Likelihood: High (if NATS reachable, no auth).
Existing mitigations (evidence):
- Schema validation in consumer: `CommandMessage.model_validate` in `grpc_server.py`.
- Some command-level rejection logic (`_describe_control_command_result`), but accept paths exist.

Smallest hardening step:
- Bind NATS ports to localhost in Phase1 compose (`127.0.0.1:4222:4222`, `127.0.0.1:8222:8222`) to reduce network exposure.
- Add NATS auth token/user for Phase1 and pass credentials via `NATS_URL` for all services (still dev-friendly).

### T2: UI spoofing via fake responses/events (decision integrity)
Path:
1. Attacker publishes fake `qiki.responses.control` or `qiki.responses.qiki` or `qiki.events.v1.*`.
2. ORION subscribes via core NATS (`subscribe_control_responses`, `subscribe_qiki_responses`, `subscribe_events`) and renders incoming payloads.
3. Operator is misled about command success/mode/proposals/events.

Impact: High (operator acts on false state).
Likelihood: High (same root: unauthenticated NATS).
Existing mitigations:
- None cryptographic; only JSON decoding and best-effort UI handling.

Smallest hardening step:
- Same as T1 (reduce exposure + add auth).
- Add minimal provenance check in ORION display: require expected `source` field for control responses/events where present; otherwise render as `UNTRUSTED` (UI-only hardening).

### T3: Secret update injection on `OPENAI_API_KEY_UPDATE` (secret integrity/availability)
Path:
1. Attacker publishes `{"op":"set_key","api_key":"..."}`
2. `qiki_orion_intents_service.py` subscribes to `qiki.secrets.v1.openai_api_key` and sets `os.environ["OPENAI_API_KEY"]`.

Impact: Medium to High (DoS of QIKI replies; billing confusion; potential exfil path if attacker can force status/behavior).
Likelihood: High (unauthenticated NATS; handler accepts any non-empty string).
Existing mitigations:
- Minimal: requires non-empty string; optional reply ack is best-effort.

Smallest hardening step:
- Gate `set_key` behind an env flag (default disabled) in non-dev environments, or require a shared secret/token in the payload (documented, rotated).

## Recommended next work (tight, evidence-first)
1. Implement `127.0.0.1` port binding for NATS in Phase1 compose and prove with `docker compose ... ps` and a connectivity smoke from inside containers.
2. Add a short ORION UI “untrusted message” marker for responses/events without expected provenance keys.
3. Decide on the policy for `OPENAI_API_KEY_UPDATE` (dev-only vs authenticated runtime control) and encode it as a decision (SovMem `DECISIONS`) before implementing.

