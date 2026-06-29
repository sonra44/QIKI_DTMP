"""IF-POWER-TELEM-001 (§12.6) read-only ORION power surface.

ADR-0003: battery and supercap are shown SEPARATELY; ORION never collapses them into a
single energy bar (a charged battery is not peak permission). Values are surfaced from the
PowerTelemetryRecord where present; absent numerics / states are shown as honest "unknown".
This module does not compute power, validate loads, or invoke the PDU.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PowerEvidence:
    claim_type: str  # "power_telemetry"
    source_type: str  # "telemetry"
    read_only: bool
    battery_soc_label: str
    supercap_soc_label: str
    soc_bat_label: str
    soc_cap_label: str
    battery_temp_label: str
    supercap_temp_label: str
    bus_label: str
    freshness: str
    trust_status: str
    is_trusted: bool
    reason_codes: tuple[str, ...]
    operator_text: str


def _pct(value: Any) -> str:
    return "unknown" if value is None else f"{float(value):.0f}%"


def _state(value: Any) -> str:
    text = str(value or "").strip()
    return text if text and text.lower() != "missing" else "unknown"


def _bus(record: Any) -> str:
    volts, amps = record.bus_voltage_V, record.bus_current_A
    if volts is None and amps is None:
        return "unknown"
    v_label = "unknown" if volts is None else f"{float(volts):.1f}V"
    a_label = "unknown" if amps is None else f"{float(amps):.1f}A"
    return f"{v_label} {a_label}"


def power_to_evidence(record: Any) -> PowerEvidence:
    """Read-only ORION projection of a PowerTelemetryRecord — battery and supercap separate."""
    battery_soc = _pct(record.battery_soc_pct)
    supercap_soc = _pct(record.supercap_soc_pct)
    freshness = str(record.freshness or "")
    trust_status = str(record.trust_status or "")
    reason_codes = tuple(record.reason_codes or ())
    # SoC is clean fact only when trusted, unflagged AND explicitly fresh (allowlist —
    # unknown/expired/stale must not pass as trusted).
    is_trusted = trust_status == "trusted" and not reason_codes and freshness == "fresh"
    base = (
        f"SoC_bat {battery_soc}; SoC_cap {supercap_soc} "
        "(shown separately — battery charge is not peak permission)"
    )
    if is_trusted:
        operator_text = base
    else:
        parts = [f"trust={trust_status or 'unknown'}", f"freshness={freshness or 'unknown'}"]
        if reason_codes:
            parts.append(",".join(reason_codes))
        operator_text = base + " [UNTRUSTED: " + "; ".join(parts) + "]"
    return PowerEvidence(
        claim_type="power_telemetry",
        source_type="telemetry",
        read_only=True,
        battery_soc_label=battery_soc,
        supercap_soc_label=supercap_soc,
        soc_bat_label=battery_soc,
        soc_cap_label=supercap_soc,
        battery_temp_label=_state(record.battery_temp_state),
        supercap_temp_label=_state(record.supercap_temp_state),
        bus_label=_bus(record),
        freshness=freshness,
        trust_status=trust_status,
        is_trusted=is_trusted,
        reason_codes=reason_codes,
        operator_text=operator_text,
    )
