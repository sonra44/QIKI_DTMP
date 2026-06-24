"""IF-NBL-001 (§17.8) read-only ORION surface of an NBL emergency packet.

Per §17.8 ORION must show criticality, payload class, cost, status, delivery uncertainty,
and reason_codes. §17.10: NBL is rules-only / target-only — a packet is never shown as sent
or delivered without a real source. is_sent is True only for an explicit packet_sent status;
delivery confidence is surfaced verbatim. Read-only; never transmits or gates a packet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_SENT_STATE = "packet_sent"
# Reasons that mean there is no real delivery path -> a sent status cannot be honored.
_NO_DELIVERY_REASONS = ("NBL_RULES_ONLY", "NBL_NOT_IMPLEMENTED")


@dataclass(frozen=True, slots=True)
class NblPacketEvidence:
    packet_id: str
    criticality: str
    payload_class: str
    cost_label: str
    status: str
    delivery_confidence: str
    is_sent: bool
    reason_codes: tuple[str, ...]
    read_only: bool
    operator_text: str


def _text(value: Any, default: str = "missing") -> str:
    text = str(value or "").strip()
    return text if text else default


def _cost(record: Any) -> str:
    soc = record.SoC_cap_cost
    power = record.power_cost
    if soc is None and power is None:
        return "missing"
    soc_label = "missing" if soc is None else str(soc)
    power_label = "missing" if power is None else str(power)
    return f"SoC_cap={soc_label} power={power_label}"


def nbl_to_evidence(record: Any) -> NblPacketEvidence:
    """Read-only ORION projection of one NblPacketRecord (§17.8)."""
    status = _text(record.status, "not_implemented")
    delivery_confidence = _text(record.delivery_confidence, "unknown")
    reason_codes = tuple(record.reason_codes or ())
    # Defensive: a sent status with no-delivery reasons (rules-only / not-implemented) is not
    # a real delivery — ORION must not honor it.
    is_sent = status == _SENT_STATE and not any(r in _NO_DELIVERY_REASONS for r in reason_codes)
    if is_sent:
        operator_text = f"NBL: packet sent; delivery confidence: {delivery_confidence}"
    else:
        operator_text = (
            f"NBL: {status}; delivery: {delivery_confidence} (target-only)"
            + (" — " + ", ".join(reason_codes) if reason_codes else "")
        )
    return NblPacketEvidence(
        packet_id=str(record.packet_id or "missing"),
        criticality=_text(record.criticality),
        payload_class=_text(record.payload_class),
        cost_label=_cost(record),
        status=status,
        delivery_confidence=delivery_confidence,
        is_sent=is_sent,
        reason_codes=reason_codes,
        read_only=True,
        operator_text=operator_text,
    )
