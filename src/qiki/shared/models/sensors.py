"""IF-SENSOR-TELEM-001 (§15) shared sensor-telemetry contract + mapper.

Single source of truth for the per-sensor record and its pure derivation, imported by
BOTH q_sim (producer) and ORION operator_console (read-only projection). Part of the
producer->transport->ORION evidence path (Slice A): q_sim emits these records in the
telemetry payload, ORION consumes them for the §15 evidence projection (it must NOT
re-derive §15 evidence from raw sensor_plane). No q_sim / protobuf deps. Reuses the
shared thermal state helper for the sensor thermal-state gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qiki.shared.models.thermal import _thermal_state_from_node

# §15.6 sensor reason codes.
SENSOR_MISSING = "SENSOR_MISSING"
SENSOR_STALE = "SENSOR_STALE"
SENSOR_CONFLICTING = "SENSOR_CONFLICTING"
SENSOR_BLIND = "SENSOR_BLIND"
SENSOR_DEGRADED = "SENSOR_DEGRADED"
SENSOR_BLOCKED_BY_MODULE = "SENSOR_BLOCKED_BY_MODULE"
SENSOR_THERMAL_BLOCK = "SENSOR_THERMAL_BLOCK"
SENSOR_AFFECTED_BY_FIELD = "SENSOR_AFFECTED_BY_FIELD"
SENSOR_AFFECTED_BY_MOTION = "SENSOR_AFFECTED_BY_MOTION"


@dataclass(frozen=True, slots=True)
class SensorTelemetryRecord:
    """IF-SENSOR-TELEM-001 target-only projection from q_sim sensor truth."""

    sensor_id: str
    sensor_class: str
    measured_quantity: str
    value: Any
    unit: str
    timestamp: float | None
    freshness: str
    latency: float | None
    accuracy: float | None
    source: str
    trust_status: str
    field_of_view: str | None
    mount_point: str | None
    blocked_by_module: bool | None
    affected_by_motion: bool | None
    affected_by_field: bool | None
    affected_by_emcon: bool | None
    thermal_state: str
    reason_codes: tuple[str, ...]


def _num_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sensor_thermal_state(thermal: dict[str, Any] | None) -> str:
    if not isinstance(thermal, dict):
        return "unknown"
    nodes = thermal.get("nodes")
    if not isinstance(nodes, list):
        return "unknown"
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or "").lower()
        if "sensor" in node_id or node_id == "head":
            return _thermal_state_from_node(raw)
    return "unknown"


def _sensor_reason_codes(
    *,
    enabled: bool,
    value: Any,
    source: str,
    freshness: str,
    status: str | None = None,
    blind: bool = False,
    thermal_state: str = "unknown",
) -> tuple[str, ...]:
    reason_codes: list[str] = []
    if not enabled or value is None or source == "missing":
        reason_codes.append(SENSOR_MISSING)
    if freshness == "stale":
        reason_codes.append(SENSOR_STALE)
    if blind:
        reason_codes.append(SENSOR_BLIND)
    if status in {"warn", "crit"}:
        reason_codes.append(SENSOR_DEGRADED)
    if thermal_state in {"hot", "critical"}:
        reason_codes.append(SENSOR_THERMAL_BLOCK)
    return tuple(dict.fromkeys(reason_codes))


def _sensor_trust_status(reason_codes: tuple[str, ...], *, blind: bool = False) -> str:
    if SENSOR_MISSING in reason_codes:
        return "missing"
    if SENSOR_STALE in reason_codes:
        return "stale"
    if blind or SENSOR_BLIND in reason_codes:
        return "blind"
    if SENSOR_DEGRADED in reason_codes or SENSOR_THERMAL_BLOCK in reason_codes:
        return "degraded"
    return "trusted"


def _sensor_record(
    *,
    sensor_id: str,
    sensor_class: str,
    measured_quantity: str,
    value: Any,
    unit: str,
    enabled: bool,
    status: str | None,
    source: str,
    timestamp: float | None,
    freshness: str,
    thermal_state: str,
    blind: bool = False,
    field_of_view: str | None = None,
    mount_point: str | None = None,
) -> SensorTelemetryRecord:
    source = str(source or "").strip() or "missing"
    if source == "missing":
        value = None
        freshness = "unknown"
    reason_codes = _sensor_reason_codes(
        enabled=enabled,
        value=value,
        source=source,
        freshness=freshness,
        status=status,
        blind=blind,
        thermal_state=thermal_state,
    )
    return SensorTelemetryRecord(
        sensor_id=sensor_id,
        sensor_class=sensor_class,
        measured_quantity=measured_quantity,
        value=value,
        unit=unit,
        timestamp=timestamp,
        freshness=freshness,
        latency=None,
        accuracy=None,
        source=source,
        trust_status=_sensor_trust_status(reason_codes, blind=blind),
        field_of_view=field_of_view,
        mount_point=mount_point,
        blocked_by_module=None,
        affected_by_motion=None,
        affected_by_field=None,
        affected_by_emcon=None,
        thermal_state=thermal_state,
        reason_codes=reason_codes,
    )


def sensor_telemetry_from_sensor_plane(
    sensor_plane: dict[str, Any] | None,
    *,
    thermal: dict[str, Any] | None = None,
    timestamp: float | None = None,
    freshness: str = "fresh",
    source: str = "q_sim_service.world_model.sensor_plane",
) -> tuple[SensorTelemetryRecord, ...]:
    """Map WorldModel sensor plane state into per-sensor IF-SENSOR-TELEM-001 records."""
    if not isinstance(sensor_plane, dict):
        return (
            _sensor_record(
                sensor_id="missing",
                sensor_class="missing",
                measured_quantity="missing",
                value=None,
                unit="missing",
                enabled=False,
                status=None,
                source="missing",
                timestamp=timestamp,
                freshness="unknown",
                thermal_state="unknown",
            ),
        )

    source = str(source or "").strip() or "missing"
    thermal_state = _sensor_thermal_state(thermal)
    records: list[SensorTelemetryRecord] = []

    imu = sensor_plane.get("imu") if isinstance(sensor_plane.get("imu"), dict) else {}
    imu_value = {
        "roll_rate_rps": _num_or_none(imu.get("roll_rate_rps")),
        "pitch_rate_rps": _num_or_none(imu.get("pitch_rate_rps")),
        "yaw_rate_rps": _num_or_none(imu.get("yaw_rate_rps")),
    }
    if any(value is None for value in imu_value.values()):
        imu_value = None
    records.append(
        _sensor_record(
            sensor_id="imu",
            sensor_class="motion",
            measured_quantity="angular_rate",
            value=imu_value,
            unit="rad/s",
            enabled=bool(imu.get("enabled")),
            status=str(imu.get("status") or ""),
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
        )
    )

    radiation = sensor_plane.get("radiation") if isinstance(sensor_plane.get("radiation"), dict) else {}
    records.append(
        _sensor_record(
            sensor_id="radiation",
            sensor_class="radiation",
            measured_quantity="radiation_background",
            value=_num_or_none(radiation.get("background_usvh")),
            unit="uSv/h",
            enabled=bool(radiation.get("enabled")),
            status=str(radiation.get("status") or ""),
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
        )
    )

    proximity = sensor_plane.get("proximity") if isinstance(sensor_plane.get("proximity"), dict) else {}
    proximity_value = {
        "min_range_m": _num_or_none(proximity.get("min_range_m")),
        "contacts": _num_or_none(proximity.get("contacts")),
    }
    if all(value is None for value in proximity_value.values()):
        proximity_value = None
    records.append(
        _sensor_record(
            sensor_id="proximity",
            sensor_class="proximity",
            measured_quantity="proximity_contact",
            value=proximity_value,
            unit="m/count",
            enabled=bool(proximity.get("enabled")),
            status=None,
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
            field_of_view="local",
        )
    )

    solar = sensor_plane.get("solar") if isinstance(sensor_plane.get("solar"), dict) else {}
    records.append(
        _sensor_record(
            sensor_id="solar",
            sensor_class="illumination",
            measured_quantity="illumination",
            value=_num_or_none(solar.get("illumination_pct")),
            unit="percent",
            enabled=bool(solar.get("enabled")),
            status=None,
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
            field_of_view="external",
        )
    )

    star_tracker = sensor_plane.get("star_tracker") if isinstance(sensor_plane.get("star_tracker"), dict) else {}
    locked = star_tracker.get("locked")
    star_value = None if locked is None else {
        "locked": bool(locked),
        "attitude_err_deg": _num_or_none(star_tracker.get("attitude_err_deg")),
    }
    records.append(
        _sensor_record(
            sensor_id="star_tracker",
            sensor_class="attitude",
            measured_quantity="attitude_lock",
            value=star_value,
            unit="bool/deg",
            enabled=bool(star_tracker.get("enabled")),
            status=str(star_tracker.get("status") or ""),
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
            blind=locked is False,
            field_of_view="stellar",
        )
    )

    magnetometer = sensor_plane.get("magnetometer") if isinstance(sensor_plane.get("magnetometer"), dict) else {}
    field = magnetometer.get("field_ut")
    records.append(
        _sensor_record(
            sensor_id="magnetometer",
            sensor_class="field",
            measured_quantity="magnetic_field",
            value=dict(field) if isinstance(field, dict) else None,
            unit="uT",
            enabled=bool(magnetometer.get("enabled")),
            status=None,
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
        )
    )

    return tuple(records)
