from __future__ import annotations

import time

from qiki.services.q_core_agent.core.terminal_radar_renderer import render_terminal_screen


def _event(
    *,
    subsystem: str,
    event_type: str,
    payload: dict,
    reason: str,
    truth_state: str = "OK",
) -> dict:
    return {
        "event_id": f"evt-{subsystem}-{event_type}-{int(time.time() * 1000)}",
        "ts": time.time(),
        "subsystem": subsystem,
        "event_type": event_type,
        "payload": payload,
        "tick_id": None,
        "truth_state": truth_state,
        "reason": reason,
    }


def test_terminal_renderer_renders_screen_from_events_without_exception() -> None:
    events = [
        _event(
            subsystem="FSM",
            event_type="FSM_TRANSITION",
            payload={
                "from_state": "SHIP_IDLE",
                "to_state": "DOCKING_APPROACH",
                "trigger_event": "TARGET_IN_RANGE",
                "status": "COMPLETED",
                "context": {"docking_confirm_hits": "1", "safe_mode_reason": ""},
            },
            reason="TARGET_IN_RANGE",
        ),
        _event(
            subsystem="ACTUATORS",
            event_type="ACTUATION_RECEIPT",
            payload={
                "action": "fire_rcs_thruster:port",
                "status": "executed",
                "command_id": "cmd-1",
                "correlation_id": "cmd-1",
                "is_fallback": False,
                "timestamp": time.time(),
                "reason": "FORCED_EXECUTED",
            },
            reason="FORCED_EXECUTED",
        ),
        _event(
            subsystem="SENSORS",
            event_type="SENSOR_TRUST_VERDICT",
            payload={
                "sensor_kind": "station_track",
                "ok": True,
                "reason": "OK",
                "age_s": 0.1,
                "quality": 0.95,
                "data_present": True,
                "data": {"range_m": 9.0, "vr_mps": 0.1},
                "is_fallback": False,
            },
            reason="OK",
            truth_state="OK",
        ),
    ]

    screen = render_terminal_screen(events)

    assert "RADAR 3D + HUD" in screen
    assert "FSM: DOCKING_APPROACH" in screen
    assert "LAST ACTUATION: fire_rcs_thruster:port status=EXECUTED" in screen
    assert "TRUTH: OK reason=OK" in screen


def test_terminal_renderer_no_data_shows_no_data_and_hides_target_marker() -> None:
    events = [
        _event(
            subsystem="SENSORS",
            event_type="SENSOR_TRUST_VERDICT",
            payload={
                "sensor_kind": "station_track",
                "ok": False,
                "reason": "NO_DATA",
                "age_s": None,
                "quality": None,
                "data_present": False,
                "data": None,
                "is_fallback": False,
            },
            reason="NO_DATA",
            truth_state="NO_DATA",
        )
    ]

    screen = render_terminal_screen(events)

    assert "NO DATA: NO_DATA" in screen
    assert "TRUTH: NO_DATA reason=NO_DATA" in screen
    assert "@>" not in screen
    assert "O>" not in screen
    assert "o>" not in screen


def test_terminal_renderer_safe_mode_shows_reason_and_exit_counter() -> None:
    events = [
        _event(
            subsystem="SAFE_MODE",
            event_type="SAFE_MODE",
            payload={
                "action": "hold",
                "reason": "SENSORS_STALE",
                "exit_hits": "1",
                "confirmation_count": 3,
            },
            reason="SENSORS_STALE",
            truth_state="NO_DATA",
        ),
        _event(
            subsystem="FSM",
            event_type="FSM_TRANSITION",
            payload={
                "from_state": "DOCKING_APPROACH",
                "to_state": "SAFE_MODE",
                "trigger_event": "SAFE_MODE_HOLD_SENSORS_STALE",
                "status": "COMPLETED",
                "context": {"safe_mode_reason": "SENSORS_STALE", "docking_confirm_hits": "0"},
            },
            reason="SAFE_MODE_HOLD_SENSORS_STALE",
        ),
    ]

    screen = render_terminal_screen(events)

    assert "FSM: SAFE_MODE" in screen
    assert "SAFE: ON reason=SENSORS_STALE exit=1/3" in screen


def test_terminal_renderer_shows_training_overlay() -> None:
    events = [
        _event(
            subsystem="TRAINING",
            event_type="TRAINING_STATUS",
            payload={
                "scenario": "cpa_warning",
                "title": "CPA Warning",
                "objective": "Detect CPA risk and acknowledge alert",
                "status": "IN_PROGRESS",
                "duration_s": 12.0,
                "elapsed_s": 3.0,
            },
            reason="IN_PROGRESS",
            truth_state="OK",
        ),
        _event(
            subsystem="TRAINING",
            event_type="TRAINING_RESULT",
            payload={
                "scenario": "cpa_warning",
                "score": 88,
                "verdict": "PASS",
                "metrics": {"reaction_time_s": 1.2},
            },
            reason="PASS",
            truth_state="OK",
        ),
    ]
    screen = render_terminal_screen(events)
    assert "TRAINING: cpa_warning status=PASS" in screen
    assert "TRAINING TIMER:" in screen
    assert "score=88" in screen
