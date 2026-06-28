"""Console comms telemetry — thin re-export of the shared §16 contract.

DEFERRED-A (console side): the former BOUNDED-TEMP verbatim mirror is gone; the record +
pure mapper now live in `qiki.shared.models.comms`, imported by BOTH q_sim (producer) and
this console (read-only projection). The equivalence test
(tests/unit/test_orion_comms_adapter_equivalence.py) keeps proving the shared mapper stays
1-to-1 with q_sim's runtime. Back-compat names (CommsRecord / comms_channels_from_snapshot)
keep existing console call sites unaffected.
"""

from __future__ import annotations

from qiki.shared.models.comms import (
    COMMS_DEGRADED,
    COMMS_NOT_IMPLEMENTED,
    COMMS_POWER_BLOCK,
    COMMS_THERMAL_BLOCK,
    COMMS_UNAUTHORIZED,
    COMMS_UNAVAILABLE,
    EMCON_BLOCK,
    CommsChannelRecord,
    _comms_bandwidth_class,
    _comms_delivery_state,
    _comms_delivery_state_from_reason_codes,
    _comms_power_blocked,
    _comms_reason_codes,
    _comms_thermal_blocked,
    _comms_trust_status,
    _string_tuple,
    comms_channels_from_comms_state,
)

# Back-compat console aliases.
CommsRecord = CommsChannelRecord
comms_channels_from_snapshot = comms_channels_from_comms_state

__all__ = [
    "COMMS_DEGRADED",
    "COMMS_NOT_IMPLEMENTED",
    "COMMS_POWER_BLOCK",
    "COMMS_THERMAL_BLOCK",
    "COMMS_UNAUTHORIZED",
    "COMMS_UNAVAILABLE",
    "EMCON_BLOCK",
    "CommsChannelRecord",
    "CommsRecord",
    "_comms_bandwidth_class",
    "_comms_delivery_state",
    "_comms_delivery_state_from_reason_codes",
    "_comms_power_blocked",
    "_comms_reason_codes",
    "_comms_thermal_blocked",
    "_comms_trust_status",
    "_string_tuple",
    "comms_channels_from_comms_state",
    "comms_channels_from_snapshot",
]
