"""Stage 4 / IF-PDU-POWER-001 — ORION operator surface of PDU load permission.

Canon §11.8: ORION must show PDU state, requested load, allowed/rejected, blocked peak
commands, SoC_bat, SoC_cap (separately — ADR-0003), thermal blockers, and reason_codes,
per load. Conservative: a missing thermal_clearance is never surfaced as cleared; a
rejected load is never surfaced as allowed; absent values stay missing.
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import pdu_permissions_from_power_state
from qiki.services.operator_console.orion_v.pdu_evidence import pdu_to_evidence


def _base():
    recs = pdu_permissions_from_power_state(
        {"loads_w": {"radar": 10.0}, "soc_pct": 80.0, "supercap_soc_pct": 20.0},
        thermal=None,
    )
    return recs[0]


def test_allowed_load_surfaced() -> None:
    ev = pdu_to_evidence((_base(),))
    load = ev.loads[0]
    assert load.allowance_label == "load_allowed"
    assert load.is_rejected is False


def test_rejected_peak_is_flagged() -> None:
    rec = dataclasses.replace(
        _base(),
        load_id="boost",
        peak_required=True,
        allowance_state="load_rejected",
        reason_codes=("PDU_PEAK_DENIED",),
    )
    ev = pdu_to_evidence((rec,))
    assert "boost" in ev.rejected_loads
    assert "boost" in ev.blocked_peak_loads
    load = ev.loads[0]
    assert load.is_rejected is True
    assert load.is_blocked_peak is True
    assert "PDU_PEAK_DENIED" in load.reason_codes


def test_soc_bat_and_cap_surfaced_separately() -> None:
    # ADR-0003: battery and supercap SoC are distinct, never one conflated value.
    ev = pdu_to_evidence((_base(),))
    load = ev.loads[0]
    assert load.soc_cap_label == "20%"
    assert load.soc_bat_label != load.soc_cap_label


def test_thermal_clearance_missing_is_honest() -> None:
    # thermal=None at the mapper -> ORION must not present clearance as cleared.
    ev = pdu_to_evidence((_base(),))
    assert ev.loads[0].thermal_clearance == "missing"


def test_operator_text_and_readonly() -> None:
    rec = dataclasses.replace(
        _base(),
        load_id="boost",
        peak_required=True,
        allowance_state="load_rejected",
        reason_codes=("PDU_PEAK_DENIED",),
    )
    ev = pdu_to_evidence((rec,))
    assert ev.read_only is True
    assert "boost" in ev.operator_text


def test_allowed_but_thermal_missing_not_all_allowed() -> None:
    # CODEX_BLOCKER / ADR-0003: full-allowed summary requires thermal clearance.
    ev = pdu_to_evidence((_base(),))  # load_allowed but thermal_clearance=missing
    assert "all requested loads allowed" not in ev.operator_text
    assert "thermal_clearance" in ev.operator_text


def test_limited_not_summarized_as_fully_allowed() -> None:
    rec = dataclasses.replace(
        _base(), load_id="scan", allowance_state="load_allowed_limited", thermal_clearance="clear"
    )
    ev = pdu_to_evidence((rec,))
    assert "all requested loads allowed" not in ev.operator_text


def test_fully_cleared_load_is_all_allowed() -> None:
    # Positive path stays reachable: load_allowed AND thermal_clearance == clear.
    rec = dataclasses.replace(_base(), thermal_clearance="clear")
    ev = pdu_to_evidence((rec,))
    assert ev.operator_text == "PDU: all requested loads allowed"
