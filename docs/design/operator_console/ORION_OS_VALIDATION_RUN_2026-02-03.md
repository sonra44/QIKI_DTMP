# ORION OS — Validation Run (2026-02-03)

Scope: clarify `N/A` vs `Disabled` and radar inspector readability, without introducing mocks or v2 contracts.

## Evidence (simulation-truth)

- Telemetry source: `qiki.telemetry` (producer: `q_sim_service`), validated by `tools/telemetry_smoke.py --audit-dictionary`.
- Radar tracks source: `qiki.radar.v1.tracks` (producer: `faststream-bridge`).

## Checks

1) Sensors screen:
   - When telemetry reports a sensor as explicitly disabled (e.g. `sensor_plane.star_tracker.enabled=false` and `status=na`), UI must show `Disabled/Отключено` (not `N/A/—`).
   - Automated proof: `tests/unit/test_orion_sensors_disabled_status.py`.

2) Radar inspector:
   - UI must render enums as operator-readable codes for `Object type`, `IFF`, `Transponder mode`.
   - Automated proof: `tests/unit/test_orion_radar_enum_labels.py`.

## Notes

- This run is screenshot-free (terminal UI). Proof is via unit tests + live-stack subjects.
