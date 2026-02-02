# TASK (2026-02-02): ORION incident-level replay proof (P0)

## Goal

Prove that ORION’s IncidentStore/IncidentEngine can be driven deterministically via record/replay:

- Record a real sim-truth incident trigger event stream (Phase1 fixture)
- Stop live sources
- Replay the exact recorded events back into canonical subjects
- Observe ORION opening the incident via an auditable event (no TUI scraping)

## Constraints

- No new `v2` subjects or parallel contracts.
- No mocks: incident trigger comes from `q_sim_service` fixture (simulation truth).
- Deterministic and automatable in Docker.

## Implementation (what changed)

ORION now emits a best-effort audit message when an incident is opened:

- Subject: `qiki.events.v1.operator.actions` (already canonical)
- Payload (schema_version=1):
  - `category="audit"`
  - `kind="incident_open"`
  - `source="orion"`
  - `subject="incident"`
  - `ts_epoch`
  - `incident_key`, `incident_id`, `rule_id`, `severity`

Also, ORION uses `payload.ts_epoch` when present as the event time (falls back to `time.time()`).
This makes replay deterministic without having to sleep in real time for min-duration rules.

## Proof procedure (scripted)

Run:

```bash
cd QIKI_DTMP
bash scripts/prove_orion_incident_replay.sh
```

What the script does:

1) Starts Phase1 with `BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_temp_core_trip.json`.
2) Captures the last thermal TRIP edge event from JetStream (`qiki.events.v1.sensor.thermal.trip`) and writes a single-line JSONL file in `qiki-dev` container.
3) Stops `q-sim-service` so there are no live events.
4) Restarts `operator-console` to reset incidents.
5) Replays the JSONL to canonical subjects and waits for ORION to emit `kind=incident_open` with `rule_id=TEMP_CORE_TRIP`.
6) Restores the default (playable) stack automatically.

Expected output includes a JSON payload printed by the script:

- `kind: "incident_open"`
- `rule_id: "TEMP_CORE_TRIP"`

## Notes

- The fixture stack may show many `N/A` in UI; that is expected for proof runs.
- The production/default stack remains `src/qiki/services/q_core_agent/config/bot_config.json` (no fixtures).
