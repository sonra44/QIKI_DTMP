"""Stage 3 / IF-THERMAL-TELEM-001 — ORION operator surface of thermal node telemetry.

Canon §13.7: ORION must show which node is heating, which commands are blocked, what
cooldown is needed, and which reason_code is active — per thermal node. Conservative:
unknown/missing states stay unknown/missing (Canon != Implemented); ORION never invents
a temperature or a nominal state where the source is absent.
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import thermal_telemetry_from_thermal_state
from qiki.services.operator_console.orion_v.thermal_evidence import thermal_to_evidence


def _missing_node():
    return thermal_telemetry_from_thermal_state(None)[0]


def test_hot_node_is_surfaced() -> None:
    hot = dataclasses.replace(
        _missing_node(),
        thermal_node_id="rcs_cluster",
        thermal_state="hot",
        temp_current=70.0,
        blocked_commands=("radar",),
        cooldown_state="needed",
        reason_codes=("THERMAL_NODE_HOT",),
        trust_status="trusted",
    )
    ev = thermal_to_evidence((hot,))
    assert "rcs_cluster" in ev.hot_nodes
    node = ev.nodes[0]
    assert node.is_hot is True
    assert node.state_label == "hot"
    assert node.blocked_commands == ("radar",)
    assert "THERMAL_NODE_HOT" in node.reason_codes


def test_unknown_node_stays_unknown() -> None:
    ev = thermal_to_evidence((_missing_node(),))
    node = ev.nodes[0]
    assert node.state_label == "unknown"
    assert node.is_hot is False
    assert node.trust_status == "missing"


def test_nodes_surfaced_separately() -> None:
    core = dataclasses.replace(_missing_node(), thermal_node_id="core", thermal_state="nominal")
    rcs = dataclasses.replace(_missing_node(), thermal_node_id="rcs", thermal_state="critical")
    ev = thermal_to_evidence((core, rcs))
    assert len(ev.nodes) == 2
    assert "rcs" in ev.hot_nodes
    assert "core" not in ev.hot_nodes


def test_operator_text_and_readonly() -> None:
    hot = dataclasses.replace(_missing_node(), thermal_node_id="comms", thermal_state="critical")
    ev = thermal_to_evidence((hot,))
    assert ev.read_only is True
    assert "comms" in ev.operator_text


def test_mixed_nominal_unknown_not_summarized_as_nominal() -> None:
    # CODEX_BLOCKER: an unknown node must not be masked by a nominal one.
    core = dataclasses.replace(_missing_node(), thermal_node_id="core", thermal_state="nominal")
    ev = thermal_to_evidence((core, _missing_node()))
    assert "all nodes nominal" not in ev.operator_text


def test_warm_node_not_summarized_as_nominal() -> None:
    warm = dataclasses.replace(_missing_node(), thermal_node_id="pdu", thermal_state="warm")
    ev = thermal_to_evidence((warm,))
    assert "all nodes nominal" not in ev.operator_text
    assert "pdu" in ev.operator_text or "warm" in ev.operator_text


def test_cooldown_node_not_summarized_as_nominal() -> None:
    cooldown = dataclasses.replace(_missing_node(), thermal_node_id="rcs", thermal_state="cooldown")
    ev = thermal_to_evidence((cooldown,))
    assert "all nodes nominal" not in ev.operator_text
    assert "rcs" in ev.operator_text or "cooldown" in ev.operator_text
