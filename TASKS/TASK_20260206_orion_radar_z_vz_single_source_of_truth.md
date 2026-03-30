# TASK: ORION radar Z/Vz formatting single source of truth (legend vs overlay)

Date: 2026-02-06

## Goal
Prevent drift between:
- overlay labels rendered by `unicode_ppi.py` and
- the radar legend line in `main_orion.py`

Both surfaces must use the same rules for:
- presence detection (no-mocks) and
- token formatting/clamping for `Z±N` and `Vz±N`.

## Implementation
- `src/qiki/services/operator_console/radar/unicode_ppi.py`
  - Add module helpers:
    - `radar_z_m_if_present(payload)` and `radar_vz_mps_if_present(payload)` (no-mocks presence)
    - `format_z_token(z_m)` and `format_vz_token(vz_mps)` (shared formatting)
  - Ensure overlay labels use these helpers.
  - Harden `position` parsing so missing `position.z` does not discard `x/y`.
- `src/qiki/services/operator_console/main_orion.py`
  - Legend imports and reuses the same helpers to render `3D: Z ... Vz ...`.

## Tests / Evidence
- Unit test: `tests/unit/test_orion_radar_commands.py`
  - `test_radar_legend_shows_selection_and_labels_lod` asserts:
    - legend contains `Z+50` and `Vz+1` for selected track
    - overlay output also contains `Z+50` and `Vz+1` (consistency proof)

## DoD
- Legend and overlay use the same helper functions for Z/Vz.
- No-mocks preserved: missing keys do not become invented zeros.
- `bash scripts/quality_gate_docker.sh` is green.

