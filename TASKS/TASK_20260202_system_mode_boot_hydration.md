# TASK (2026-02-02): ORION header Mode/Режим is not N/A at boot (JetStream hydration)

## Goal

Make ORION show `Mode/Режим` immediately in the default stack, without requiring a manual mode-change intent and without adding any new subjects or v2 contracts.

## Problem (facts)

- ORION header renders `Mode/Режим` from event `qiki.events.v1.system_mode`.
- This event is published on core NATS (non-persistent). If it is emitted before ORION subscribes, ORION can remain at `N/A/—` until the next mode change.

## Fix (no new contracts)

1) **Publisher**: faststream-bridge now publishes the current mode once at boot using existing subject:

- Subject: `qiki.events.v1.system_mode` (`SYSTEM_MODE_EVENT`)
- Stored in JetStream stream `QIKI_EVENTS_V1` because `EVENTS_SUBJECTS=qiki.events.v1.>`

Implementation: `src/qiki/services/faststream_bridge/app.py`
- Publishes on `@app.after_startup` (broker is ready).
- Also adds `ts_epoch` field (backward-compatible v1 expansion).

2) **Consumer**: ORION hydrates mode from JetStream on startup (no mocks):

- Fetch last message from `QIKI_EVENTS_V1` + `qiki.events.v1.system_mode`.
- If payload contains `mode`, updates internal `_qiki_mode` and header.

Implementation:
- `src/qiki/services/operator_console/clients/nats_client.py` adds `fetch_last_event_json(...)`.
- `src/qiki/services/operator_console/main_orion.py` calls `_hydrate_qiki_mode_from_jetstream()` at end of `_init_nats`.

## Proof

- Unit proofs (Docker-first):
  - `tests/unit/test_system_mode_boot_event.py` proves faststream-bridge publishes boot mode event.
  - `tests/unit/test_orion_hydrate_system_mode_from_jetstream.py` proves ORION hydrates `_qiki_mode` from JetStream payload.

- Integration proof (Docker-first, deterministic):
  - `tests/integration/test_system_mode_boot_event_stream.py` publishes an existing QIKI intent (`mode factory`) and asserts the resulting `qiki.events.v1.system_mode` is persisted in JetStream stream `QIKI_EVENTS_V1`.

- Restart proof (canonical checklist):
  - `docs/RESTART_CHECKLIST.md` step **2.1** runs `python tools/system_mode_smoke.py --persisted-only` to verify the persisted edge-event exists after a restart (no mocks).

- Runtime evidence (tmux):
  - After restart, ORION header shows `Mode/Режим FACTORY` (not `N/A/—`).
  - Captured via: `tmux capture-pane -pt %19 -S -20`.
