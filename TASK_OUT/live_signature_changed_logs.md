# Live Signature Changed Logs

## Procedure Load

Source: [`TASK_OUT/live_orion_procedure_status.log`](/home/sonra44/QIKI_DTMP/TASK_OUT/live_orion_procedure_status.log)

```text
RESOLVED_PROCEDURES_DIR=/workspace/config/orion_v/procedures
PROCEDURE_COUNT=3
PROCEDURE_NAMES=hostile_rcs_intercept_burst,safe_pause_resume,safe_pause_slow_resume
```

## Direct Probe

Source: [`TASK_OUT/live_signature_changed_direct_probe.log`](/home/sonra44/QIKI_DTMP/TASK_OUT/live_signature_changed_direct_probe.log)

### Initial ORION tracks

```text
ORION_TRACKS_INITIAL=[{"track_id":"38a7770e-1f09-4e4f-b7a4-ac186da43d35","transponder_id":"SPOOF-05C30E","quality":1.0,"range_m":3500.3571246374277,...}]
```

### Initial q-core tracks

```text
QCORE_TRACKS_INITIAL=[
  {"track_id":"e9459b28-5d8a-49be-97fb-d580e1aff04a","transponder_id":null,"visible_signature":null,"quality":0.5,"range_m":8500.357124637427},
  {"track_id":"1625aec3-9267-45fa-95e3-42386bf275fa","transponder_id":"SPOOF-05C30E","visible_signature":"SPOOF-05C30E","quality":1.0,"range_m":3500.3571246374277}
]
```

### Initial telemetry

```text
TELEMETRY_INITIAL={
  "comms": {
    "plane_profile": "ON",
    "xpdr": {"active": true, "allowed": true, "id": "ALLY-0F4107", "mode": "ON"}
  },
  "sim_state": {"fsm_state": "RUNNING", "paused": false, "running": true, "speed": 1.0},
  "xpdr": null
}
```

### After `sim.xpdr.mode=ON`

```text
XPDR_ACK_ON={"ack": true}
TELEMETRY_AFTER_ON={
  "comms": {
    "plane_profile": "ON",
    "xpdr": {"active": true, "allowed": true, "id": "ALLY-0F4107", "mode": "ON"}
  },
  "sim_state": {"fsm_state": "RUNNING", "paused": false, "running": true, "speed": 1.0},
  "xpdr": null
}
ORION_TRACKS_AFTER_ON=[{"track_id":"38a7770e-1f09-4e4f-b7a4-ac186da43d35","transponder_id":"SPOOF-05C30E","quality":1.0,"range_m":3500.3571246374277,...}]
QCORE_TRACKS_AFTER_ON=[]
```

### After `sim.xpdr.mode=SPOOF`

```text
XPDR_ACK_SPOOF={"ack": true}
TELEMETRY_AFTER_SPOOF={
  "comms": {
    "plane_profile": "SPOOF",
    "xpdr": {"active": true, "allowed": true, "id": "SPOOF-05C30E", "mode": "SPOOF"}
  },
  "sim_state": {"fsm_state": "RUNNING", "paused": false, "running": true, "speed": 1.0},
  "xpdr": null
}
ORION_TRACKS_AFTER_SPOOF=[{"track_id":"38a7770e-1f09-4e4f-b7a4-ac186da43d35","transponder_id":"SPOOF-05C30E","quality":1.0,"range_m":3500.3571246374277,...}]
QCORE_TRACKS_AFTER_SPOOF=[
  {"track_id":"e6bc5ce1-e6a7-4dbe-bc23-84ac48212c0d","transponder_id":null,"visible_signature":null,"quality":0.5,"range_m":8500.357124637427},
  {"track_id":"59ca1ed6-ef92-4cc8-af7d-a839d8f2bf0e","transponder_id":"SPOOF-05C30E","visible_signature":"SPOOF-05C30E","quality":1.0,"range_m":3500.3571246374277}
]
```

## Control Slow Run

Source: [`TASK_OUT/live_signature_changed_control_slow.log`](/home/sonra44/QIKI_DTMP/TASK_OUT/live_signature_changed_control_slow.log)

```text
OK: orion_v_qiki_observation_objective_seed_smoke
OBSERVATION_STYLE=slow
ROUTE_ROLE=deviation
OBJECTIVE_ID=observation-db230099-ff8e-4304-be2b-a4584fd70815
OBJECTIVE_TARGET=SPOOF-05C30E
OBJECTIVE_KIND=observation_objective_update
OBJECTIVE_STATUS=confirmed
TRACK_ID=21a31bb0-3cfa-5141-bd80-b9538d258618
TRACK_RANGE_M=3500.3571246374277
TRACK_QUALITY=1.0
OBJECTIVE_PROCEDURE=safe_pause_slow_resume
OBJECTIVE_FOLLOW_UP=review_required
REVIEW_ACTION=review_confirm
POST_REVIEW_CHOICE=hold_for_recheck
RESUME_ACTION=resume_observation
OBJECTIVE_FOLLOW_UP_AFTER_REVIEW=review_completed
OBJECTIVE_FOLLOW_UP_AFTER_CHOICE=hold_for_recheck
OBJECTIVE_FOLLOW_UP_AFTER_RESUME=resume_observation
NEXT_ALLOWED_STEP=safe observation
CONTINUATION_RESULT=reconfirmed
CONTINUED_TARGET=SPOOF-05C30E
CONTINUED_OBJECTIVE_ID=observation-db230099-ff8e-4304-be2b-a4584fd70815
CONTINUED_ROUTE_ROLE=deviation
PRE_REVIEW_QIKI_STATUS=pending
HIDDEN_EVENT_LINE=audit | HIDDEN_EVENT_REVEALED | Deviation route safe_pause_slow_resume раскрыл скрытый observation fact для SPOOF-05C30E.
FINAL_QIKI_STATUS=confirmed
SIM_STATE={'running': True, 'paused': False, 'speed': 1.0, 'fsm_state': 'RUNNING'}
```

## Mutation-Specific Failures

The two raw files below are empty because `tee` captured `stdout`, while the actual failures were emitted to `stderr`:

- [`TASK_OUT/live_signature_changed_smoke.log`](/home/sonra44/QIKI_DTMP/TASK_OUT/live_signature_changed_smoke.log)
- [`TASK_OUT/live_signature_changed_precomparison.log`](/home/sonra44/QIKI_DTMP/TASK_OUT/live_signature_changed_precomparison.log)

The live command outputs that actually occurred were:

### Smoke failure

```text
AssertionError: timeout while waiting for live radar track with public designator in q_core world snapshot
```

### Precomparison probe failure

```text
AssertionError: no ORION live radar track with public designator is available
```

## Short Readout

- Procedures load correctly on canonical contour.
- Control resumed-observation contour is alive and ends with `reconfirmed`.
- Telemetry mutation works: `ALLY-0F4107 -> SPOOF-05C30E`.
- ORION live cache does not surface a non-spoof public designator after `ON`.
- q-core public track view disappears after `ON` and reappears under a different `track_id` after `SPOOF`.
- Therefore the live stack still does not produce a same-contact public-label transition suitable for honest `signature_changed` proof.
