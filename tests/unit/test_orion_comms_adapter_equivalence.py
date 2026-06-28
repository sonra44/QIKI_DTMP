"""Equivalence guard for the shared §16 comms mapper (post DEFERRED-A).

The former console BOUNDED-TEMP mirror is gone: both the console alias
(orion_v.comms_telemetry_adapter.comms_channels_from_snapshot) and the q_sim
re-export (world_model.comms_channels_from_comms_state) now resolve to the one
qiki.shared.models.comms mapper. This asserts they stay field-by-field equal —
a drift means a re-export was rewired wrong or the shared contract changed.
"""

# ruff: noqa: E501  (parametrized comms snapshots are intentionally one-line per case)

from __future__ import annotations

import dataclasses

import pytest

from qiki.services.operator_console.orion_v.comms_telemetry_adapter import (
    comms_channels_from_snapshot,
)
from qiki.services.q_sim_service.core.world_model import (
    comms_channels_from_comms_state,
)

# Each case: (comms, power, thermal). available=True is required to reach the main
# delivery logic (absent/None available -> "unknown" -> not_implemented branch).
CASES = [
    (None, None, None),  # not a dict -> missing record
    ("bad", None, None),  # not a dict -> missing record
    ({"enabled": False}, None, None),  # disabled -> not_implemented
    ({"enabled": True}, None, None),  # available absent -> unknown -> not_implemented
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": True}, "data_rate_kbps": 100}, None, None),  # online medium
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": True}, "data_rate_kbps": 300}, None, None),  # online high bw
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": True}, "data_rate_kbps": 30}, None, None),  # online low bw
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": True}, "EMCON_state": "EMCON_block"}, None, None),  # EMCON_block
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": True}}, None, {"nodes": [{"id": "comms", "tripped": True}]}),  # thermal_block
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": True}}, {"shed_loads": ["transponder"]}, None),  # power_block (shed)
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": False}}, None, None),  # power_block (xpdr not allowed)
    ({"enabled": True, "available": True, "link": "degraded", "xpdr": {"allowed": True}}, None, None),  # channel_degraded
    ({"enabled": True, "available": True, "link": "", "xpdr": {"allowed": True}}, None, None),  # link missing -> not_implemented
    ({"enabled": True, "available": False, "link": "online", "xpdr": {"allowed": True}}, None, None),  # available False -> not_implemented
    ({"enabled": True, "reason_codes": ["COMMS_DEGRADED"]}, None, None),  # source reason -> channel_degraded
    ({"enabled": True, "reason_codes": ["EMCON_BLOCK"]}, None, None),  # source reason -> EMCON_block
    ({"enabled": True, "reason_codes": ["COMMS_UNAUTHORIZED"]}, None, None),  # source reason -> authorization_missing
    (  # full fields mirror through
        {
            "enabled": True,
            "available": True,
            "link": "online",
            "xpdr": {"allowed": True, "mode": "active"},
            "EMCON_state": "clear",
            "latency_ms": 50.0,
            "tx_power_w": 5.0,
            "data_rate_kbps": 128.0,
            "plane_profile": "normal",
        },
        None,
        None,
    ),
    ({"enabled": True, "available": True, "link": "online", "emcon_state": "EMCON_block", "xpdr": {"allowed": True}}, None, None),  # lowercase emcon alias not matched -> online
    ({"enabled": True, "available": True, "link_state": "online", "xpdr": {"allowed": True}}, None, None),  # link_state alias
    # _string_tuple edge cases (runtime shadows: empty strings kept, set is not a Sequence)
    ({"enabled": True, "reason_codes": ""}, None, None),  # empty-string reason_codes
    ({"enabled": True, "reason_codes": ["COMMS_DEGRADED", ""]}, None, None),  # empty item kept, channel_degraded
    ({"enabled": True, "reason_codes": ["", "EMCON_BLOCK"]}, None, None),  # empty item + real reason
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": True}}, {"shed_loads": ["", "transponder"]}, None),  # shed empty item -> power_block
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": True}}, {"shed_loads": "transponder"}, None),  # shed_loads as bare string
    ({"enabled": True, "available": True, "link": "online", "xpdr": {"allowed": True}}, {"shed_loads": {"transponder"}}, None),  # shed_loads as set (not a Sequence)
]


@pytest.mark.parametrize("comms,power,thermal", CASES)
def test_console_comms_adapter_is_1to1_with_qsim_mapper(comms, power, thermal) -> None:
    ts = 123.0
    console = comms_channels_from_snapshot(comms, power=power, thermal=thermal, timestamp=ts, freshness="fresh")
    qsim = comms_channels_from_comms_state(comms, power=power, thermal=thermal, timestamp=ts, freshness="fresh")
    assert len(console) == len(qsim)
    for c, q in zip(console, qsim):
        assert dataclasses.asdict(c) == dataclasses.asdict(q)
