"""IF-SENSOR-TELEM-001 (§15.7) read-only ORION sensor-telemetry surface.

Per §15.7 ORION must show, per sensor: source, freshness, trust, conflict, missing status,
and hypothesis/reconstruction marking. REQ-SENSOR-001 (P0): a value without a source is not
physical truth — it stays "no value" / marked missing or hypothesis. "all trusted" is claimed
only when every sensor is trusted (non-trusted sensors are never masked). Read-only; this
module never fuses, validates, or invents sensor data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# §15.5 trust states grouped by how ORION must flag them.
_MISSING_STATES = ("missing", "blind", "stale")
_HYPOTHESIS_STATES = ("hypothesis", "local_reconstruction")
# Trust states that assert a real reading and therefore REQUIRE a source (REQ-SENSOR-001);
# without one, the value is not physical truth and is demoted to "missing".
_SOURCE_REQUIRED_STATES = ("trusted", "degraded", "conflicting", "blind", "stale")


@dataclass(frozen=True, slots=True)
class SensorEvidence:
    sensor_id: str
    sensor_class: str
    value_label: str
    source: str
    freshness: str
    trust_status: str
    is_trusted: bool
    is_conflicting: bool
    is_missing: bool
    is_hypothesis: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SensorTelemetryEvidence:
    claim_type: str  # "sensor_telemetry"
    source_type: str  # "telemetry"
    read_only: bool
    sensors: tuple[SensorEvidence, ...]
    conflicting_sensors: tuple[str, ...]
    missing_sensors: tuple[str, ...]
    hypothesis_sensors: tuple[str, ...]
    operator_text: str


def _value_label(record: Any) -> str:
    if record.value is None:
        return "no value"
    unit = str(record.unit or "").strip()
    return f"{record.value} {unit}".strip()


def _text(value: Any, default: str = "missing") -> str:
    text = str(value or "").strip()
    return text if text else default


def _sensor_evidence(record: Any) -> SensorEvidence:
    source = _text(record.source, "missing")
    has_source = source not in ("", "missing")
    claimed = _text(record.trust_status, "missing")
    # REQ-SENSOR-001 (P0): a source-required trust claim without a source is not physical
    # truth — demote it to "missing" and drop the value, regardless of the input claim.
    if not has_source and claimed in _SOURCE_REQUIRED_STATES:
        trust = "missing"
        value_label = "no value"
    else:
        trust = claimed
        value_label = _value_label(record)
    return SensorEvidence(
        sensor_id=str(record.sensor_id or "missing"),
        sensor_class=_text(record.sensor_class),
        value_label=value_label,
        source=source,
        freshness=_text(record.freshness),
        trust_status=trust,
        # A trusted claim carrying a blocking reason_code is not fully trusted (demote).
        is_trusted=trust == "trusted" and not record.reason_codes,
        is_conflicting=trust == "conflicting",
        is_missing=trust in _MISSING_STATES,
        is_hypothesis=trust in _HYPOTHESIS_STATES,
        reason_codes=tuple(record.reason_codes or ()),
    )


def sensor_to_evidence(records: Any) -> SensorTelemetryEvidence:
    """Read-only ORION projection of per-sensor SensorTelemetryRecord(s)."""
    sensors = tuple(_sensor_evidence(record) for record in records)
    conflicting = tuple(s.sensor_id for s in sensors if s.is_conflicting)
    missing = tuple(s.sensor_id for s in sensors if s.is_missing)
    hypothesis = tuple(s.sensor_id for s in sensors if s.is_hypothesis)
    if not sensors:
        operator_text = "sensors: no telemetry"
    elif all(s.is_trusted for s in sensors):
        operator_text = "sensors: all trusted"
    else:
        operator_text = "sensors: attention — " + ", ".join(
            f"{s.sensor_id}={s.trust_status}" + (f"({','.join(s.reason_codes)})" if s.reason_codes else "")
            for s in sensors
            if not s.is_trusted
        )
    return SensorTelemetryEvidence(
        claim_type="sensor_telemetry",
        source_type="telemetry",
        read_only=True,
        sensors=sensors,
        conflicting_sensors=conflicting,
        missing_sensors=missing,
        hypothesis_sensors=hypothesis,
        operator_text=operator_text,
    )
