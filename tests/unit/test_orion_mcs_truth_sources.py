"""MCS truth-sources (#30 / ADR-0016 slice-4 prep): WORLD run-state + SENS trust.

WORLD: canon MISSION_CONTROL_STRIP codes RUN/PAUSE/STOP/REPLAY/WAIT — honest
mapping, RUN only for an explicitly RUNNING world, no-data → WAIT.
SENS: derived.sensor_trust_state comes from the ported SENSORTRUST-0001 shared
contract; with no SensorFrameSnapshot it must honestly degrade, never claim
trusted out of thin air.
"""

from __future__ import annotations

from qiki.services.operator_console.orion_v.operator_state import (
    build_operator_shell_state,
)


def _state(telemetry: dict, **kwargs) -> object:
    return build_operator_shell_state(hardware_model=None, telemetry=telemetry, **kwargs)


def test_world_run_state_running() -> None:
    st = _state({"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}})
    assert st.always_on.world_run_state == "RUN"


def test_world_run_state_paused() -> None:
    st = _state({"sim_state": {"fsm_state": "RUNNING", "paused": True}})
    assert st.always_on.world_run_state == "PAUSE"


def test_world_run_state_stopped() -> None:
    st = _state({"sim_state": {"fsm_state": "STOPPED"}})
    assert st.always_on.world_run_state == "STOP"


def test_world_run_state_no_data_is_wait_never_nodata_prose() -> None:
    st = _state({})
    assert st.always_on.world_run_state == "WAIT"  # canon: never «Нет данных»


def test_world_run_state_replay() -> None:
    st = _state({"sim_state": {"fsm_state": "RUNNING"}}, replay_mode=True)
    assert st.always_on.world_run_state == "REPLAY"


def test_world_run_state_boot_state_is_wait_not_run() -> None:
    # honesty: an INIT/boot world is not "ticking" — must not overclaim RUN
    st = _state({"sim_state": {"fsm_state": "INIT"}})
    assert st.always_on.world_run_state == "WAIT"


def test_sensor_trust_degrades_honestly_without_frames() -> None:
    st = _state({})
    d = st.derived
    assert d.sensor_trust_state == "degraded"  # no SensorFrameSnapshot → legacy fallback
    assert d.sensor_trust_state != "trusted"
    assert d.sensor_trust_confidence is not None
    assert d.sensor_trust_summary
