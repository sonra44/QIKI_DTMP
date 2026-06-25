"""Console-side adapters: real q-sim telemetry snapshot -> read-only evidence records.

Route (a): the live NATS snapshot is mapped here into the inputs of the *_evidence
projections (e.g. nbl_evidence.nbl_to_evidence), WITHOUT extending the existing ORION V
collector.build_* path (the current hardware_view_model) and WITHOUT modifying q_sim.
NOTE: collector.build_* is ORION V's LIVE path — NOT legacy; route (a) just does not grow it. We surface only what the snapshot
truthfully carries; everything the runtime does not publish is left missing / target-only
and is never fabricated (ADR-0014; §17.10 NBL rules-only / target-only).
"""
from __future__ import annotations

import math

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class NblRecordView:
    """Duck-typed stand-in for q_sim ``NblPacketRecord``, carrying only the fields the
    ORION projection (``nbl_to_evidence``) reads. Kept console-local so the operator
    console does not import q_sim internals."""

    packet_id: str | None
    status: str
    criticality: str | None
    payload_class: str | None
    delivery_confidence: str
    reason_codes: tuple[str, ...]
    SoC_cap_cost: float | None
    power_cost: float | None


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None  # drop nan/inf for clean UI


def _power(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    power = snapshot.get("power") if isinstance(snapshot, Mapping) else None
    return power if isinstance(power, Mapping) else {}


def snapshot_to_nbl_record(snapshot: Mapping[str, Any]) -> NblRecordView:
    """Build a read-only NBL record from the live q-sim telemetry snapshot.

    The live snapshot publishes NBL only as power-budget facts (``power.nbl_active``,
    ``nbl_allowed``, ``nbl_power_w``, ``nbl_budget_w``); it does NOT publish an NBL packet
    projection (id / criticality / payload_class / delivery). We therefore report the
    packet layer honestly as not-implemented / target-only, surface the real NBL power
    cost, and add NBL_PDU_DENIED when the power gate denies NBL (mirrors the canon
    q_sim ``nbl_packet_from_runtime_state`` mapping). Nothing is faked: no packet_sent,
    no invented criticality/payload/delivery.
    """
    power = _power(snapshot)

    # Power cost: prefer the allowed budget, fall back to the actual draw (canon order).
    power_cost = _num(power.get("nbl_budget_w"))
    if power_cost is None:
        power_cost = _num(power.get("nbl_power_w"))

    # §17.10: NBL is rules-only / target-only ALWAYS. The feed carries no packet
    # projection (NBL_NOT_IMPLEMENTED), and the canon q_sim mapper always appends
    # NBL_RULES_ONLY — keep both as the honest baseline so a packet is never honored.
    reason_codes = ["NBL_NOT_IMPLEMENTED", "NBL_RULES_ONLY"]
    if power.get("nbl_allowed") is False:
        reason_codes.append("NBL_PDU_DENIED")  # canon: power gate denies NBL

    return NblRecordView(
        packet_id=None,                    # no packet store in the feed -> "missing"
        status="not_implemented",          # §17.10 rules-only / target-only; never faked
        criticality=None,                  # not published -> "missing"
        payload_class=None,                # not published -> "missing"
        delivery_confidence="unknown",     # no real delivery path
        reason_codes=tuple(reason_codes),
        SoC_cap_cost=None,                 # not published -> "missing"
        power_cost=power_cost,             # real NBL power cost when present
    )
