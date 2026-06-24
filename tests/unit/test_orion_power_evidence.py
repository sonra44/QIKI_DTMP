"""Stage 2 / IF-POWER-TELEM-001 — ORION operator surface: battery vs supercap separate.

Canon §12.6 + ADR-0003: ORION must show battery and supercap SEPARATELY; one common
energy bar must not replace power evidence (a charged battery is not peak permission).
Conservative: values surfaced from telemetry where present, else honest "missing".
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import power_telemetry_from_power_state
from qiki.services.operator_console.orion_v.power_evidence import power_to_evidence


def _rec(power):
    return power_telemetry_from_power_state(power)


def test_battery_and_supercap_surfaced_separately() -> None:
    ev = power_to_evidence(_rec({"soc_pct": 80.0, "supercap_soc_pct": 20.0}))
    assert ev.battery_soc_label == "80%"
    assert ev.supercap_soc_label == "20%"
    assert ev.battery_soc_label != ev.supercap_soc_label


def test_no_combined_energy_bar() -> None:
    # ADR-0003: no single conflated energy value that stands in for power evidence.
    ev = power_to_evidence(_rec({"soc_pct": 80.0, "supercap_soc_pct": 20.0}))
    assert not hasattr(ev, "energy_pct")
    assert not hasattr(ev, "soc_pct")
    assert not hasattr(ev, "energy_soc_label")


def test_missing_soc_is_honest() -> None:
    ev = power_to_evidence(_rec({}))
    assert ev.battery_soc_label == "missing"
    assert ev.supercap_soc_label == "missing"


def test_temp_state_missing_is_honest() -> None:
    ev = power_to_evidence(_rec({"soc_pct": 80.0}))
    assert ev.battery_temp_label == "missing"
    assert ev.supercap_temp_label == "missing"


def test_untrusted_power_is_flagged() -> None:
    # Audit #3: SoC must not be presented as clean fact when telemetry is untrusted/missing.
    ev = power_to_evidence(_rec({}))
    assert ev.is_trusted is False
    assert "untrusted" in ev.operator_text.lower()


def test_trusted_power_not_flagged() -> None:
    rec = dataclasses.replace(
        _rec({"soc_pct": 80.0, "supercap_soc_pct": 20.0}),
        trust_status="trusted",
        reason_codes=(),
        freshness="fresh",
    )
    ev = power_to_evidence(rec)
    assert ev.is_trusted is True
    assert "untrusted" not in ev.operator_text.lower()


def test_unknown_or_expired_freshness_not_trusted() -> None:
    # Codex cross-check BLOCKER: only fresh telemetry is trusted; unknown/expired must demote.
    for fr in ("unknown", "expired", ""):
        rec = dataclasses.replace(
            _rec({"soc_pct": 80.0, "supercap_soc_pct": 20.0}),
            trust_status="trusted",
            reason_codes=(),
            freshness=fr,
        )
        ev = power_to_evidence(rec)
        assert ev.is_trusted is False, f"freshness={fr!r} must not be trusted"


def test_operator_text_names_both_sources() -> None:
    ev = power_to_evidence(_rec({"soc_pct": 80.0, "supercap_soc_pct": 20.0}))
    text = ev.operator_text.lower()
    assert "battery" in text and "supercap" in text
    assert ev.read_only is True
