"""IF-POWER-TELEM-001 (§12.6) read-only ORION power surface.

ADR-0003: battery and supercap are shown SEPARATELY; ORION never collapses them into a
single energy bar (a charged battery is not peak permission). Values are surfaced from the
PowerTelemetryRecord where present; absent numerics / states are shown as honest "missing".
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
    battery_temp_label: str
    supercap_temp_label: str
    bus_label: str
    freshness: str
    trust_status: str
    operator_text: str


def _pct(value: Any) -> str:
    return "missing" if value is None else f"{float(value):.0f}%"


def _state(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "missing"


def _bus(record: Any) -> str:
    volts, amps = record.bus_voltage_V, record.bus_current_A
    if volts is None and amps is None:
        return "missing"
    v_label = "missing" if volts is None else f"{float(volts):.1f}V"
    a_label = "missing" if amps is None else f"{float(amps):.1f}A"
    return f"{v_label} {a_label}"


def power_to_evidence(record: Any) -> PowerEvidence:
    """Read-only ORION projection of a PowerTelemetryRecord — battery and supercap separate."""
    battery_soc = _pct(record.battery_soc_pct)
    supercap_soc = _pct(record.supercap_soc_pct)
    operator_text = (
        f"battery: SoC {battery_soc}; supercap: SoC {supercap_soc} "
        "(shown separately — battery charge is not peak permission)"
    )
    return PowerEvidence(
        claim_type="power_telemetry",
        source_type="telemetry",
        read_only=True,
        battery_soc_label=battery_soc,
        supercap_soc_label=supercap_soc,
        battery_temp_label=_state(record.battery_temp_state),
        supercap_temp_label=_state(record.supercap_temp_state),
        bus_label=_bus(record),
        freshness=str(record.freshness or ""),
        trust_status=str(record.trust_status or ""),
        operator_text=operator_text,
    )
