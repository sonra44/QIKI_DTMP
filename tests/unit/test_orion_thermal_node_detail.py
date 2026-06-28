"""§13.7 per-node thermal evidence detail visible on F1 (_thermal_node_detail_lines)."""

from __future__ import annotations

from qiki.services.operator_console.orion_v.screens.cockpit import OrionVCockpitScreen

_detail = OrionVCockpitScreen._thermal_node_detail_lines  # no self attrs


def test_per_node_detail_shows_each_node_state_reason_blocked() -> None:
    tel = {"thermal": {"nodes": [
        {"id": "core", "temp_c": 25.0, "warn_c": 80.0, "trip_c": 90.0},
        {"id": "pdu", "temp_c": 95.0, "tripped": True},
    ]}}
    lines = _detail(None, tel)
    text = "\n".join(lines)
    assert "Узлы/Nodes (§13.7)" in lines[0]
    assert "core: 25°C | nominal" in text
    # §13.7 requires cooldown shown per node — honest "missing" when none active
    assert "core: 25°C | nominal | cooldown: missing" in text
    # critical node shows §13.7 reason codes + blocked commands
    assert "pdu: 95°C | critical" in text
    assert "PDU_THERMAL_BLOCK" in text
    assert "блок/blocked: radar,transponder,nbl" in text


def test_per_node_detail_shows_active_cooldown() -> None:
    # §13.7: "what cooldown is needed" — an active cooldown_state must be surfaced.
    tel = {"thermal": {"nodes": [
        {"id": "pdu", "temp_c": 95.0, "tripped": True, "cooldown_state": "active"},
    ]}}
    text = "\n".join(_detail(None, tel))
    assert "cooldown: active" in text


def test_no_thermal_yields_no_node_block() -> None:
    assert _detail(None, {}) == []
    assert _detail(None, {"thermal": {"nodes": []}}) == []
