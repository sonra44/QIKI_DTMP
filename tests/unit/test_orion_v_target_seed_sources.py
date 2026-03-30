from __future__ import annotations

import pytest

from tools.orion_v_target_seed_sources import pick_initial_target_designator


def test_pick_initial_target_designator_prefers_orion_public_truth_over_qcore_fallback() -> None:
    designator, track, source = pick_initial_target_designator(
        orion_tracks=[
            {
                "track_id": "bridge-track-77",
                "transponder_id": "ALLY-4D1ED5",
                "status": "TRACKED",
            }
        ],
        qcore_fallback=lambda: pytest.fail("q_core fallback must not run when ORION public truth is available"),
    )

    assert designator == "ALLY-4D1ED5"
    assert track["track_id"] == "bridge-track-77"
    assert source == "orion_live_radar_cache"


def test_pick_initial_target_designator_filters_spoof_in_public_truth_before_fallback() -> None:
    designator, track, source = pick_initial_target_designator(
        orion_tracks=[
            {
                "track_id": "bridge-track-spoof",
                "transponder_id": "SPOOF-42",
                "status": "TRACKED",
            },
            {
                "track_id": "bridge-track-77",
                "transponder_id": "ALLY-4D1ED5",
                "status": "TRACKED",
            },
        ],
        require_non_spoof=True,
        qcore_fallback=lambda: pytest.fail("q_core fallback must not run when ORION has a non-spoof public target"),
    )

    assert designator == "ALLY-4D1ED5"
    assert track["track_id"] == "bridge-track-77"
    assert source == "orion_live_radar_cache"
