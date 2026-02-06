# TASK: ORION radar 3D labels show vertical rate (Vz) when present

Date: 2026-02-06

## Goal
Add a small next 3D semantic slice: in `side/front/iso` radar views, show a compact vertical-rate cue `Vz±N` near the altitude label, but only when `velocity.z` is explicitly present (no-mocks).

## Constraints
- Docker-first.
- No-mocks: do not invent `Vz=0` when z-velocity is missing.
- Keep `top` view label semantics unchanged (track-id).

## Implementation
- Renderer: `src/qiki/services/operator_console/radar/unicode_ppi.py`
  - Add `_velocity_z_mps()` that returns z-velocity only when the key is explicitly present.
  - Extend `_label_text()` to append `Vz±N` in 3D views when present.

## Tests / Evidence
- Unit test:
  - `tests/unit/test_orion_radar_commands.py`
    - `test_unicode_ppi_3d_view_labels_show_altitude` asserts both `Z+50` and `Vz+1` appear in side view.
    - `test_unicode_ppi_3d_view_labels_do_not_invent_vz` asserts no `Vz` appears when `velocity.z` is missing.

## DoD
- `Vz±N` appears in `side/front/iso` only when `velocity.z` exists.
- No behavior regression for `top` view labels.
- `bash scripts/quality_gate_docker.sh` is green.

