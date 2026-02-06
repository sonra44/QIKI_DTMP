# TASK: ORION radar legend shows selected-track 3D readout (Z, Vz)

Date: 2026-02-06

## Goal
When a radar track is selected, show an explicit 3D readout in the radar legend:
- `Z` (altitude) as `Z±N` when `position.z` is explicitly present
- `Vz` (vertical rate) as `Vz±N` when `velocity.z` is explicitly present

No-mocks rule: missing keys must not be invented as zeros; show `N/A/—` instead.

## Implementation
- `src/qiki/services/operator_console/main_orion.py`
  - Extend `_render_radar_legend()` to append a 4th line:
    - `3D: Z <value>  Vz <value>`
  - Read values from the selected track payload in `self._tracks_by_id` (selection id from `self._selection_by_app["radar"].key`).
  - Formatting clamps:
    - `Z` clamp `999`, `Vz` clamp `99` (consistent with overlay labels).

## Tests / Evidence
- Unit test: `tests/unit/test_orion_radar_commands.py`
  - `test_radar_legend_shows_selection_and_labels_lod` asserts the legend includes `Z+50` and `Vz+1` when payload includes `position.z` and `velocity.z`.

## DoD
- Legend shows `Z±N` and `Vz±N` for selected track when keys exist.
- Legend shows `N/A/—` for missing keys (no zeros invented).
- `bash scripts/quality_gate_docker.sh` is green.

