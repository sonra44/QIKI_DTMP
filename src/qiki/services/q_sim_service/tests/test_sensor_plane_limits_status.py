from __future__ import annotations

from qiki.services.q_sim_service.core.world_model import WorldModel


def test_radiation_status_na_when_limits_not_configured() -> None:
    bot_config = {"hardware_profile": {"sensor_plane": {"enabled": True, "radiation": {"enabled": True}}}}
    wm = WorldModel(bot_config=bot_config)
    wm.radiation_usvh = 10.0
    sp = wm.get_state().get("sensor_plane") or {}
    rad = (sp.get("radiation") or {}) if isinstance(sp, dict) else {}
    assert rad.get("enabled") is True
    assert rad.get("status") == "na"


def test_radiation_status_warn_and_crit_from_limits() -> None:
    bot_config = {
        "hardware_profile": {
            "sensor_plane": {
                "enabled": True,
                "radiation": {"enabled": True, "limits": {"warn_usvh": 1.0, "crit_usvh": 2.0}},
            }
        }
    }
    wm = WorldModel(bot_config=bot_config)

    wm.radiation_usvh = 0.5
    rad0 = (wm.get_state().get("sensor_plane") or {}).get("radiation") or {}
    assert rad0.get("status") == "ok"

    wm.radiation_usvh = 1.5
    rad1 = (wm.get_state().get("sensor_plane") or {}).get("radiation") or {}
    assert rad1.get("status") == "warn"

    wm.radiation_usvh = 2.5
    rad2 = (wm.get_state().get("sensor_plane") or {}).get("radiation") or {}
    assert rad2.get("status") == "crit"

