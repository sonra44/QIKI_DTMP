"""BOUNDED-TEMP console-side mirror of the q_sim IF-COMMS-001 channel mapper.

Why this exists (read before editing):
- The canonical comms channel record + mapper live in
  `q_sim_service/core/world_model.py` (heavy q_sim/protobuf deps). ORION
  (operator_console) is a read-only evidence station and MUST NOT import q_sim
  runtime (canon: hard q_sim<->ORION layer separation).
- The proper fix is to extract the pure contract+mapper into `qiki/shared`
  (tracked as DEFERRED-A, same as thermal). Until then this module is a VERBATIM
  mirror of the q_sim comms mapper, guarded by an equivalence test
  (tests/unit/test_orion_comms_adapter_equivalence.py) that asserts this mirror
  stays 1-to-1 with `world_model.comms_channels_from_comms_state`.
- `_comms_thermal_blocked` reuses the already-mirrored `_thermal_state_from_node`
  from thermal_telemetry_adapter (one console mirror of that function, no dup).
- Keep every function below semantically identical to q_sim. Any drift is a bug
  the equivalence test must catch.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from qiki.services.operator_console.orion_v.thermal_telemetry_adapter import (
    _thermal_state_from_node,
)

# IF-COMMS-001 §16.6 reason codes — mirror of world_model comms constants.
COMMS_UNAVAILABLE = "COMMS_UNAVAILABLE"
COMMS_DEGRADED = "COMMS_DEGRADED"
EMCON_BLOCK = "EMCON_BLOCK"
COMMS_POWER_BLOCK = "COMMS_POWER_BLOCK"
COMMS_THERMAL_BLOCK = "COMMS_THERMAL_BLOCK"
COMMS_UNAUTHORIZED = "COMMS_UNAUTHORIZED"
COMMS_NOT_IMPLEMENTED = "COMMS_NOT_IMPLEMENTED"


@dataclass(frozen=True, slots=True)
class CommsRecord:
    """Mirror of world_model.CommsChannelRecord (IF-COMMS-001)."""

    channel_id: str
    channel_class: str
    direction: str
    bandwidth_class: str
    latency: float | None
    power_cost_W: float | None
    thermal_node: str | None
    signature_class: str
    EMCON_state: str
    delivery_state: str
    timestamp: float | None
    freshness: str
    trust_status: str
    reason_codes: tuple[str, ...]


def _num_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_tuple(value: Any) -> tuple[str, ...]:
    # Mirror of the RUNTIME world_model._string_tuple (the line-~1500 definition that
    # SHADOWS an earlier same-named one). Keeps empty strings, treats only abc.Sequence
    # as a sequence (str handled above; set/dict fall through to the str() fallback).
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    return (str(value),)


def _comms_bandwidth_class(data_rate_kbps: float | None) -> str:
    if data_rate_kbps is None or data_rate_kbps <= 0.0:
        return "none"
    if data_rate_kbps < 64.0:
        return "low"
    if data_rate_kbps < 256.0:
        return "medium"
    return "high"


def _comms_thermal_blocked(thermal: dict[str, Any] | None) -> bool:
    if not isinstance(thermal, dict):
        return False
    nodes = thermal.get("nodes")
    if not isinstance(nodes, list):
        return False
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or "").lower()
        if ("comms" in node_id or "comm" in node_id or "transponder" in node_id) and _thermal_state_from_node(raw) in {
            "hot",
            "critical",
        }:
            return True
    return False


def _comms_power_blocked(power: dict[str, Any] | None) -> bool:
    if not isinstance(power, dict):
        return False
    return "transponder" in _string_tuple(power.get("shed_loads"))


def _comms_delivery_state(
    *,
    comms_enabled: bool,
    xpdr_allowed: bool,
    link: str,
    emcon_state: str,
    power_blocked: bool,
    thermal_blocked: bool,
) -> str:
    if not comms_enabled:
        return "not_implemented"
    if emcon_state == "EMCON_block":
        return "EMCON_block"
    if thermal_blocked:
        return "thermal_block"
    if power_blocked or not xpdr_allowed:
        return "power_block"
    if link == "online":
        return "online"
    if link == "degraded":
        return "channel_degraded"
    return "not_implemented"


def _comms_reason_codes(delivery_state: str) -> tuple[str, ...]:
    if delivery_state == "online":
        return ()
    mapping = {
        "not_implemented": COMMS_NOT_IMPLEMENTED,
        "EMCON_block": EMCON_BLOCK,
        "power_block": COMMS_POWER_BLOCK,
        "thermal_block": COMMS_THERMAL_BLOCK,
        "SAFE_block": COMMS_UNAVAILABLE,
        "channel_degraded": COMMS_DEGRADED,
        "authorization_missing": COMMS_UNAUTHORIZED,
    }
    return (mapping.get(delivery_state, COMMS_UNAVAILABLE),)


def _comms_delivery_state_from_reason_codes(reason_codes: tuple[str, ...]) -> str:
    if EMCON_BLOCK in reason_codes:
        return "EMCON_block"
    if COMMS_THERMAL_BLOCK in reason_codes:
        return "thermal_block"
    if COMMS_POWER_BLOCK in reason_codes:
        return "power_block"
    if COMMS_DEGRADED in reason_codes:
        return "channel_degraded"
    if COMMS_UNAUTHORIZED in reason_codes:
        return "authorization_missing"
    if COMMS_NOT_IMPLEMENTED in reason_codes:
        return "not_implemented"
    return "not_implemented"


def _comms_trust_status(delivery_state: str) -> str:
    if delivery_state == "online":
        return "trusted"
    if delivery_state == "not_implemented":
        return "missing"
    return "degraded"


def comms_channels_from_snapshot(
    comms: dict[str, Any] | None,
    *,
    power: dict[str, Any] | None = None,
    thermal: dict[str, Any] | None = None,
    timestamp: float | None = None,
    freshness: str = "fresh",
) -> tuple[CommsRecord, ...]:
    """Console-side mirror of world_model.comms_channels_from_comms_state.

    Must stay 1-to-1 with q_sim (guarded by the equivalence test).
    """
    if not isinstance(comms, dict):
        return (
            CommsRecord(
                channel_id="missing",
                channel_class="missing",
                direction="missing",
                bandwidth_class="none",
                latency=None,
                power_cost_W=None,
                thermal_node=None,
                signature_class="missing",
                EMCON_state="missing",
                delivery_state="not_implemented",
                timestamp=timestamp,
                freshness="unknown",
                trust_status="missing",
                reason_codes=(COMMS_NOT_IMPLEMENTED,),
            ),
        )

    xpdr = comms.get("xpdr") if isinstance(comms.get("xpdr"), dict) else {}
    comms_enabled = bool(comms.get("enabled", comms.get("plane_enabled", False)))
    xpdr_allowed = bool(xpdr.get("allowed", False))
    link = str(comms.get("link") or comms.get("link_state") or "").strip().lower()
    emcon_state = str(comms.get("EMCON_state") or comms.get("emcon_state") or "missing")
    source_reason_codes = _string_tuple(comms.get("reason_codes"))
    availability = comms.get("available")
    availability_state = str(availability).strip().lower() if availability is not None else "unknown"
    power_blocked = _comms_power_blocked(power)
    thermal_blocked = _comms_thermal_blocked(thermal)
    if source_reason_codes:
        delivery_state = _comms_delivery_state_from_reason_codes(source_reason_codes)
    elif availability is False or availability_state == "unknown":
        delivery_state = _comms_delivery_state_from_reason_codes(source_reason_codes)
    else:
        delivery_state = _comms_delivery_state(
            comms_enabled=comms_enabled,
            xpdr_allowed=xpdr_allowed,
            link=link,
            emcon_state=emcon_state,
            power_blocked=power_blocked,
            thermal_blocked=thermal_blocked,
        )
    data_rate = _num_or_none(comms.get("data_rate_kbps"))
    mode = str(xpdr.get("mode") or comms.get("plane_profile") or "missing").strip().lower() or "missing"
    reason_codes = source_reason_codes if source_reason_codes else _comms_reason_codes(delivery_state)

    return (
        CommsRecord(
            channel_id="transponder" if comms_enabled else "missing",
            channel_class="transponder" if comms_enabled else "missing",
            direction="tx" if comms_enabled else "missing",
            bandwidth_class=_comms_bandwidth_class(data_rate),
            latency=_num_or_none(comms.get("latency_ms")),
            power_cost_W=_num_or_none(comms.get("tx_power_w")),
            thermal_node="comms" if comms_enabled else None,
            signature_class=mode,
            EMCON_state=emcon_state,
            delivery_state=delivery_state,
            timestamp=timestamp,
            freshness=freshness if comms_enabled else "unknown",
            trust_status=_comms_trust_status(delivery_state),
            reason_codes=reason_codes,
        ),
    )
