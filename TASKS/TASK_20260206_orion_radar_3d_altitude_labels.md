**ID:** TASK_20260206_orion_radar_3d_altitude_labels  
**Status:** done  
**Owner:** codex  
**Date created:** 2026-02-06  

## Goal

Add a first true 3D-specific overlay behavior in ORION radar labels:

- `top` keeps legacy ID labels.
- `side/front/iso` show compact altitude labels `Z±N` from simulation-truth `z`.

This ensures 3D views communicate depth explicitly without mocks.

## Changes

- `src/qiki/services/operator_console/radar/unicode_ppi.py`
  - Added `_label_text()` helper.
  - In `top` view labels remain track IDs.
  - In `side/front/iso` labels now prefer altitude `Z±N` derived from computed `z_m`.
  - Fallback to ID labels only when altitude is unavailable.

- `tests/unit/test_orion_radar_commands.py`
  - Added `test_unicode_ppi_3d_view_labels_show_altitude`.
  - Asserts side-view labels contain `Z+50` and do not show the track ID when 3D altitude is present.

## Proof

Command:

```bash
bash scripts/quality_gate_docker.sh
```

Result:
- Ruff: OK
- Pytest: OK
- Gate: OK

