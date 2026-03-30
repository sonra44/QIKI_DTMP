# bridge_track_continuity_diagnostic

## 1. Current bridge identity model

`faststream_bridge` canonical track identity is the bridge-local UUID stored in `RadarTrackStore._tracks`.

- Bridge `track_id` is created only in [`src/qiki/services/faststream_bridge/radar_track_store.py:314`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:314) via `uuid4()`.
- The identity owner inside the bridge is `_TrackState.track_id` in [`src/qiki/services/faststream_bridge/radar_track_store.py:45`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:45).
- `app.py` publishes the selected `RadarTrackModel` from `frame_to_track(frame)` and does not rewrite `track_id` before `qiki.radar.v1.tracks` publish in [`src/qiki/services/faststream_bridge/app.py:475`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/app.py:475).
- ORION live comparison for `signature_changed` is keyed by the same `track_id`; the live label comes from `transponder_id`/`id`/`callsign` on that same record in [`src/qiki/services/operator_console/orion_v/app.py:1673`](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py:1673) and [`src/qiki/services/operator_console/orion_v/app.py:1711`](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py:1711).

Conclusion: inside the bridge, identity key is not `transponder_id` and not label. Identity key is the bridge-owned UUID that survives only if association matches an existing `_TrackState`.

## 2. Track spawn/update rules

Reuse path:

- `process_frame()` runs `detections -> _associate() -> _update_associated_tracks()` in [`src/qiki/services/faststream_bridge/radar_track_store.py:92`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:92).
- `_find_best_match()` reuses an existing track when predicted Cartesian distance is within `max_association_distance_m` and radial velocity delta is within `max_radial_velocity_delta` in [`src/qiki/services/faststream_bridge/radar_track_store.py:167`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:167).
- `_find_handoff_match()` is a special LR-only reuse path. It can reuse an existing identity-bearing track when bearing/elevation/radial gates match, even if normal Cartesian association failed, in [`src/qiki/services/faststream_bridge/radar_track_store.py:195`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:195).
- On reuse, SR data mutates `transponder_on`, `transponder_mode`, `transponder_id`, `id_present` in place on the same `_TrackState` in [`src/qiki/services/faststream_bridge/radar_track_store.py:254`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:254).

Spawn path:

- If `_associate()` returns `state is None`, `_spawn_new_tracks()` creates a fresh UUID and new `_TrackState` in [`src/qiki/services/faststream_bridge/radar_track_store.py:303`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:303).
- The bridge does not use `transponder_id` as a hard identity join key for SR-to-SR mutation. A changed transponder/signature does not itself force a new track.

## 3. Where same-contact continuity can break

Same-contact continuity can break only when association fails before the in-place SR mutation is applied.

Primary break gates:

- Cartesian association miss: predicted position vs detection position exceeds `12.0 m` default threshold in [`src/qiki/services/faststream_bridge/radar_track_store.py:177`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:177).
- Radial velocity mismatch exceeds `15.0 m/s` in [`src/qiki/services/faststream_bridge/radar_track_store.py:185`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:185).
- LR handoff miss: LR follow-up cannot reuse an identity-bearing track if bearing/elevation/radial gates fail in [`src/qiki/services/faststream_bridge/radar_track_store.py:203`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:203).

Non-break facts:

- A pure SR label mutation on a matched contact is applied in place and keeps the same bridge UUID.
- ORION `signature_changed` will only fail if the live bridge output arrives under a different `track_id` or the label never changes on the reused track.

## 4. Added diagnostics

Added minimal trace points only; no subject changes, no intent-path changes, no contour semantic changes.

- `bridge_track_spawn` in [`src/qiki/services/faststream_bridge/radar_track_store.py:344`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:344)
- `bridge_track_update` in [`src/qiki/services/faststream_bridge/radar_track_store.py:265`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:265)
- `bridge_track_identity_mutation` in [`src/qiki/services/faststream_bridge/radar_track_store.py:283`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py:283)
- `bridge_track_publish_attempt` in [`src/qiki/services/faststream_bridge/app.py:477`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/app.py:477)
- `bridge_track_published` in [`src/qiki/services/faststream_bridge/app.py:498`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/app.py:498)

Replayable proof tests added:

- same-`track_id` label mutation in [`src/qiki/services/faststream_bridge/tests/test_radar_track_store.py:259`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/tests/test_radar_track_store.py:259)
- new-`track_id` spawn when association breaks in [`src/qiki/services/faststream_bridge/tests/test_radar_track_store.py:299`](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/tests/test_radar_track_store.py:299)

## 5. Evidence from live or replayable run

Environment proof:

- `docker compose -f docker-compose.phase1.yml ps qiki-dev`
  - result: `qiki-dev-phase1 ... Up`

Replayable targeted test proof:

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/faststream_bridge/tests/test_radar_track_store.py -k 'preserves_track_id_across_sr_label_mutation or spawns_new_track_when_mutated_contact_breaks_association or keeps_sr_id_when_only_lr_is_visible'`
  - result: `3 passed`

Replayable direct diagnostic run:

- command:
```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
... instantiate RadarTrackStore ...
... feed SR track ALLY-001 ...
... feed nearby SR mutation HOSTILE-777 ...
... feed far SR mutation HOSTILE-888 ...
PY
```

- observed output:
```text
bridge_track_spawn track_id=5030956b-cf95-4831-b72f-e4813b30998d ... transponder_id=ALLY-001 ...
near_mutation {'initial_track_id': '5030956b-cf95-4831-b72f-e4813b30998d', 'mutated_track_id': '5030956b-cf95-4831-b72f-e4813b30998d', 'initial_label': 'ALLY-001', 'mutated_label': 'HOSTILE-777'}
bridge_track_identity_mutation track_id=5030956b-cf95-4831-b72f-e4813b30998d ... transponder_id=ALLY-001->HOSTILE-777 ...
far_break [{'track_id': '5030956b-cf95-4831-b72f-e4813b30998d', 'transponder_id': 'HOSTILE-777', 'status': 'COASTING'}, {'track_id': 'cb69c41d-f991-4c6d-804c-ac8ba4059eb3', 'transponder_id': 'HOSTILE-888', 'status': 'NEW'}]
bridge_track_spawn track_id=cb69c41d-f991-4c6d-804c-ac8ba4059eb3 ... transponder_id=HOSTILE-888 ...
```

Residual note:

- A broader bridge test slice including `test_radar_handlers.py` is currently not all-green in this worktree because those tests assume SR identity without setting `range_band=RR_SR`. That mismatch is outside this diagnostic scope and does not change the continuity conclusion above.

## 6. Does bridge preserve same `track_id` across label mutation?

Yes, when the mutated live contour still matches the existing `_TrackState`.

Evidence-backed answer:

- For nearby SR mutation `ALLY-001 -> HOSTILE-777`, the bridge kept `track_id=5030956b-cf95-4831-b72f-e4813b30998d`.
- The mutation was applied in place on the same `_TrackState`.
- ORION’s `signature_changed` predicate is therefore satisfiable from the bridge side, because ORION compares `same track_id + changed non-empty track_label`.

Therefore `faststream_bridge` cannot be treated as the primary blocker if the live mutation really arrives on the same associated contact. The bridge preserves continuity in that case.

## 7. Minimal next fix task candidates

1. Run one supported live smoke with the new trace lines enabled and capture `bridge_track_spawn/update/identity_mutation/published` for the exact resumed contour contact.
2. If live smoke shows a new bridge UUID after spoof mutation, localize which association gate failed first: distance, radial delta, or LR handoff gate.
3. If live smoke shows same bridge UUID and changed `transponder_id`, exclude `faststream_bridge` as primary blocker and move the blocker hunt downstream to the label-change trigger source or ORION objective snapshot timing.
