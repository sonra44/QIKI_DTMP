"""IF-COMMS-001 (§16.7) read-only ORION comms-channel surface.

Per §16.7 ORION must show, per channel: active channel, delivery state, latency, EMCON,
thermal/power blockers, reason_codes. "Связь не означает безопасность" — a channel is not
just on/off. Conservative: a non-online channel is never summarized as online; absent
channels stay not_implemented. Read-only; never opens, gates, or re-decides a channel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_ACTIVE_STATE = "online"
# §16.5 blocked delivery states -> the blocker dimension ORION must surface.
_BLOCKER_BY_STATE = {
    "power_block": "power",
    "thermal_block": "thermal",
    "EMCON_block": "EMCON",
    "SAFE_block": "SAFE",
    "channel_degraded": "degraded",
    "authorization_missing": "authorization",
    "not_implemented": "not_implemented",
}


@dataclass(frozen=True, slots=True)
class CommsChannelEvidence:
    channel_id: str
    channel_class: str
    delivery_state: str
    latency_label: str
    emcon_state: str
    is_active: bool
    is_blocked: bool
    blocker: str
    reason_codes: tuple[str, ...]
    trust_status: str


@dataclass(frozen=True, slots=True)
class CommsEvidence:
    claim_type: str  # "comms"
    source_type: str  # "telemetry"
    read_only: bool
    channels: tuple[CommsChannelEvidence, ...]
    active_channels: tuple[str, ...]
    blocked_channels: tuple[str, ...]
    operator_text: str


def _text(value: Any, default: str = "missing") -> str:
    text = str(value or "").strip()
    return text if text else default


def _latency(value: Any) -> str:
    return "missing" if value is None else str(value)


def _channel_evidence(record: Any) -> CommsChannelEvidence:
    delivery = _text(record.delivery_state, "not_implemented")
    is_active = delivery == _ACTIVE_STATE
    blocker = _BLOCKER_BY_STATE.get(delivery, "none" if is_active else "unknown")
    return CommsChannelEvidence(
        channel_id=str(record.channel_id or "missing"),
        channel_class=_text(record.channel_class),
        delivery_state=delivery,
        latency_label=_latency(record.latency),
        emcon_state=_text(record.EMCON_state),
        is_active=is_active,
        is_blocked=not is_active,
        blocker=blocker,
        reason_codes=tuple(record.reason_codes or ()),
        trust_status=_text(record.trust_status),
    )


def comms_to_evidence(records: Any) -> CommsEvidence:
    """Read-only ORION projection of per-channel CommsChannelRecord(s)."""
    channels = tuple(_channel_evidence(record) for record in records)
    active = tuple(c.channel_id for c in channels if c.is_active)
    blocked = tuple(c.channel_id for c in channels if c.is_blocked)
    if not channels:
        operator_text = "comms: no telemetry"
    elif all(c.is_active for c in channels):
        operator_text = "comms: all channels online"
    else:
        operator_text = "comms: attention — " + ", ".join(
            f"{c.channel_id}={c.delivery_state}" for c in channels if not c.is_active
        )
    return CommsEvidence(
        claim_type="comms",
        source_type="telemetry",
        read_only=True,
        channels=channels,
        active_channels=active,
        blocked_channels=blocked,
        operator_text=operator_text,
    )
