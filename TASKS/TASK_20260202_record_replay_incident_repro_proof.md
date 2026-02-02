# TASK (2026-02-02): Record/Replay — deterministic incident trigger reproduction (P0)

## Goal

Prove that an **incident-triggering event** can be recorded from a real Phase1 run and replayed deterministically,
without introducing any new v2/v3 contracts or parallel subjects.

We use the existing event subject:

- `qiki.events.v1.power.pdu` (`SIM_POWER_PDU`)

This event drives the existing incident rule `POWER_PDU_OVERCURRENT` (see `config/incident_rules.yaml`).

## Why this slice matters

- It makes incidents reproducible: capture once → replay later → get the same trigger inputs.
- It enables deterministic debugging and regression testing.
- It stays within the "no-mocks" + "no v2" constraints: only record/replay on existing subjects.

## Proof mechanism (automated)

Integration test:

- `tests/integration/test_record_replay_incident_repro.py`

What it does:

1) Records `qiki.events.v1.power.pdu` into a JSONL file using `qiki.shared.record_replay.record_jsonl`.
2) Verifies the capture contains at least one `overcurrent=1` payload (otherwise skips if the fixture is not active).
3) Replays the JSONL into a prefix `replay.*` using `qiki.shared.record_replay.replay_jsonl`.
4) Subscribes to `replay.qiki.events.v1.power.pdu` and asserts the trigger (`overcurrent=1`) is reproduced.

## How to run the proof

1) Start Phase1 with the deterministic PDU-overcurrent fixture (this will cause lots of N/A in UI; it is expected):

```bash
cd QIKI_DTMP
BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_power_pdu_overcurrent.json \
  docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build
```

2) Run the integration test in Docker:

```bash
cd QIKI_DTMP
./scripts/run_integration_tests_docker.sh tests/integration/test_record_replay_incident_repro.py
```

Expected:

- Test passes if the fixture is active.
- Test skips (with a clear reason) if the fixture is not active.

3) Return to the normal "playable" stack (no fixture bot_config):

```bash
cd QIKI_DTMP
env -u BOT_CONFIG_PATH -u QIKI_BOT_CONFIG_PATH \
  docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build
```

## Notes / constraints

- No new canon subjects are introduced: replay uses a prefix only for isolation in tests.
- This slice proves event-level determinism; ORION incident-level reproduction is the next step (subscribe ORION/IncidentEngine to replay prefix or run replay with sim stopped).

