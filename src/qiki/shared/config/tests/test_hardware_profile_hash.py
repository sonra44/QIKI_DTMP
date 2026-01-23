from __future__ import annotations

import re

from qiki.shared.config.hardware_profile_hash import compute_hardware_profile_hash


def test_compute_hardware_profile_hash_is_deterministic() -> None:
    bot_config = {
        "hardware_profile": {"power_plane": {"bus_v_nominal": 28.0}, "comms_plane": {"enabled": True}},
        "hardware_manifest": {"mcqpu": {"id": "mcqpu", "type": "mcqpu"}},
    }

    h1 = compute_hardware_profile_hash(bot_config)
    h2 = compute_hardware_profile_hash(bot_config)
    assert h1 == h2
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", h1)


def test_compute_hardware_profile_hash_changes_on_profile_change() -> None:
    base = {
        "hardware_profile": {"power_plane": {"bus_v_nominal": 28.0}},
        "hardware_manifest": {"mcqpu": {"id": "mcqpu", "type": "mcqpu"}},
    }
    changed = {
        "hardware_profile": {"power_plane": {"bus_v_nominal": 29.0}},
        "hardware_manifest": {"mcqpu": {"id": "mcqpu", "type": "mcqpu"}},
    }

    assert compute_hardware_profile_hash(base) != compute_hardware_profile_hash(changed)

