from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata


def test_docking_plane_telemetry_and_control_commands() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    # By default (bot_config.json), docking_plane is enabled and dock starts connected.
    payload0 = qsim._build_telemetry_payload(qsim.world_model.get_state())
    docking = payload0.get("docking")
    assert isinstance(docking, dict)
    assert docking.get("enabled") is True
    assert docking.get("state") in {"docked", "undocked"}
    assert docking.get("port") in {"A", "B"}
    assert docking.get("connected") in {True, False}

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    release = CommandMessage(command_name="sim.dock.release", parameters={}, metadata=meta)
    assert qsim.apply_control_command(release) is True
    docking2 = qsim._build_telemetry_payload(qsim.world_model.get_state()).get("docking") or {}
    assert docking2.get("state") == "undocked"
    assert docking2.get("connected") is False

    engage = CommandMessage(command_name="sim.dock.engage", parameters={"port": "B"}, metadata=meta)
    assert qsim.apply_control_command(engage) is True
    docking3 = qsim._build_telemetry_payload(qsim.world_model.get_state()).get("docking") or {}
    assert docking3.get("state") == "docked"
    assert docking3.get("connected") is True
    assert docking3.get("port") == "B"

    invalid = CommandMessage(command_name="sim.dock.engage", parameters={"port": "Z"}, metadata=meta)
    assert qsim.apply_control_command(invalid) is False
