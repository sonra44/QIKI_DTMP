"""Stage 6 / IF-COMMS-001 — ORION operator surface of comms channels.

Canon §16.7: ORION must show active channel, delivery state, latency, EMCON, thermal/power
blockers, and reason_codes — per channel. "Связь не означает безопасность": a channel is not
just on/off; ORION shows its state and blockers. Conservative: a non-online channel is never
summarized as online; absent channels stay not_implemented.
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import comms_channels_from_comms_state
from qiki.services.operator_console.orion_v.comms_evidence import comms_to_evidence


def _not_implemented():
    return comms_channels_from_comms_state(None)[0]


def _channel(**kw):
    return dataclasses.replace(_not_implemented(), **kw)


def test_online_channel_is_active() -> None:
    ev = comms_to_evidence((_channel(channel_id="main", delivery_state="online", reason_codes=()),))
    assert "main" in ev.active_channels
    assert ev.channels[0].is_active is True
    assert ev.operator_text == "comms: all channels online"


def test_thermal_blocked_channel_flagged() -> None:
    ev = comms_to_evidence(
        (_channel(channel_id="hi_gain", delivery_state="thermal_block", reason_codes=("COMMS_THERMAL_BLOCK",)),)
    )
    channel = ev.channels[0]
    assert channel.is_blocked is True
    assert channel.blocker == "thermal"
    assert "hi_gain" in ev.blocked_channels
    assert "all channels online" not in ev.operator_text


def test_not_implemented_is_not_active() -> None:
    ev = comms_to_evidence((_not_implemented(),))
    assert ev.channels[0].is_active is False
    assert ev.channels[0].delivery_state == "not_implemented"


def test_mixed_not_summarized_as_all_online() -> None:
    online = _channel(channel_id="main", delivery_state="online")
    blocked = _channel(channel_id="relay", delivery_state="power_block")
    ev = comms_to_evidence((online, blocked))
    assert "all channels online" not in ev.operator_text
    assert "relay" in ev.blocked_channels


def test_online_with_blocking_reason_is_demoted() -> None:
    # Audit #2: an online channel carrying a blocking reason_code must not stay active.
    ev = comms_to_evidence((_channel(channel_id="main", delivery_state="online", reason_codes=("EMCON_BLOCK",)),))
    assert ev.channels[0].is_active is False
    assert "all channels online" not in ev.operator_text
    assert ev.channels[0].blocker != "none"


def test_readonly() -> None:
    ev = comms_to_evidence((_not_implemented(),))
    assert ev.read_only is True
