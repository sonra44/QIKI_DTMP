from __future__ import annotations

from qiki.services.q_core_agent.core.runtime_contracts import (
    EVENT_SCHEMA_VERSION,
    build_export_envelope,
    resolve_strict_mode,
    validate_export_envelope,
)


def test_export_envelope_validation_ok() -> None:
    envelope = build_export_envelope(
        ts=1.5,
        subsystem="RADAR",
        event_type="RADAR_RENDER_TICK",
        truth_state="OK",
        reason="OK",
        payload={"v": 1},
        session_id="s-1",
    )
    assert envelope["schema_version"] == EVENT_SCHEMA_VERSION
    assert validate_export_envelope(envelope) == []


def test_export_envelope_validation_fail_on_missing_and_wrong_fields() -> None:
    errors = validate_export_envelope(
        {
            "schema_version": 999,
            "ts": "bad",
            "subsystem": 1,
            "event_type": "X",
            "truth_state": "WRONG",
            "reason": 3,
            "payload": [],
            # session_id missing
        }
    )
    assert errors
    assert any("schema_version" in err for err in errors)
    assert any("session_id" in err for err in errors)
    assert any("truth_state" in err for err in errors)


def test_global_strict_mode_overrides_legacy_flags() -> None:
    env = {
        "QIKI_STRICT_MODE": "1",
        "RADAR_POLICY_STRICT": "0",
        "QIKI_PLUGINS_STRICT": "0",
        "EVENTSTORE_STRICT": "0",
    }
    assert resolve_strict_mode(env, legacy_keys=("RADAR_POLICY_STRICT",), default=False) is True
    assert resolve_strict_mode(env, legacy_keys=("QIKI_PLUGINS_STRICT",), default=False) is True
    assert resolve_strict_mode(env, legacy_keys=("EVENTSTORE_STRICT",), default=False) is True


def test_legacy_strict_alias_works_without_global_flag() -> None:
    env = {"RADAR_POLICY_STRICT": "1"}
    assert resolve_strict_mode(env, legacy_keys=("RADAR_POLICY_STRICT",), default=False) is True
