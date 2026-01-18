"""RCS control via COMMANDS_CONTROL (no new proto) — no-mocks."""

from __future__ import annotations

from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata


def test_sim_rcs_fire_and_stop_control_commands() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    fire = CommandMessage(
        command_name="sim.rcs.fire",
        parameters={"axis": "port", "pct": 60.0, "duration_s": 2.0},
        metadata=meta,
    )
    assert qsim.apply_control_command(fire) is True

    qsim.step()
    state = qsim.world_model.get_state()
    rcs = (state.get("propulsion") or {}).get("rcs") or {}
    assert rcs.get("enabled") is True
    assert rcs.get("active") in (True, False)  # must exist
    assert float(rcs.get("command_pct", 0.0)) > 0.0
    assert float(rcs.get("time_left_s", 0.0)) <= 2.0 + 1e-6

    stop = CommandMessage(command_name="sim.rcs.stop", parameters={}, metadata=meta)
    assert qsim.apply_control_command(stop) is True

    qsim.step()
    state2 = qsim.world_model.get_state()
    rcs2 = (state2.get("propulsion") or {}).get("rcs") or {}
    assert float(rcs2.get("command_pct", 0.0)) == 0.0

