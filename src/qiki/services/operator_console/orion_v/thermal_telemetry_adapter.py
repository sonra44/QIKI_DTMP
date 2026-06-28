"""Console thermal telemetry — thin re-export of the shared §13.7 contract.

DEFERRED-A (console side): the former BOUNDED-TEMP verbatim mirror is gone; the record +
pure mapper now live in `qiki.shared.models.thermal`, imported by BOTH q_sim (producer)
and this console (read-only projection). The equivalence test
(tests/unit/test_orion_thermal_adapter_equivalence.py) keeps proving the shared mapper
stays 1-to-1 with q_sim's runtime. Back-compat names (ThermalRecord /
thermal_records_from_snapshot) keep existing console call sites unaffected.
"""

from __future__ import annotations

from qiki.shared.models.thermal import (
    BAYONET_THERMAL_BLOCK,
    COMMS_HOT,
    MODULE_THERMAL_BLOCK,
    PDU_THERMAL_BLOCK,
    RCS_CLUSTER_HOT,
    SENSOR_HEAD_HOT,
    THERMAL_NODE_CRITICAL,
    THERMAL_NODE_HOT,
    THERMAL_TELEM_MISSING,
    ThermalTelemetryRecord,
    _thermal_blocked_commands,
    _thermal_reason_codes,
    _thermal_state_from_node,
    thermal_telemetry_from_thermal_state,
)

# Back-compat console aliases (the console previously named the record/mapper differently).
ThermalRecord = ThermalTelemetryRecord
thermal_records_from_snapshot = thermal_telemetry_from_thermal_state

__all__ = [
    "BAYONET_THERMAL_BLOCK",
    "COMMS_HOT",
    "MODULE_THERMAL_BLOCK",
    "PDU_THERMAL_BLOCK",
    "RCS_CLUSTER_HOT",
    "SENSOR_HEAD_HOT",
    "THERMAL_NODE_CRITICAL",
    "THERMAL_NODE_HOT",
    "THERMAL_TELEM_MISSING",
    "ThermalRecord",
    "ThermalTelemetryRecord",
    "_thermal_blocked_commands",
    "_thermal_reason_codes",
    "_thermal_state_from_node",
    "thermal_records_from_snapshot",
    "thermal_telemetry_from_thermal_state",
]
