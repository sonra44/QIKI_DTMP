from __future__ import annotations

import math
from datetime import timezone
from typing import Any, Dict

from qiki.shared.models.core import SensorData, SensorTypeEnum


def update_sensor_snapshot(snapshot: Dict[str, Any] | None, sensor_data: SensorData) -> Dict[str, Any]:
    """Merge a raw sensor payload into a bot-facing reasoning snapshot.

    The current narrow contract is IMU-first:
    - keep the last known non-radar sensor truth needed for QIKI reasoning
    - do not mix radar track state into this structure
    - preserve prior values when the current payload is unrelated
    """

    base: Dict[str, Any] = dict(snapshot or {})
    sensor_plane = dict(base.get("sensor_plane") or {}) if isinstance(base.get("sensor_plane"), dict) else {}
    base["sensor_plane"] = sensor_plane

    if sensor_data.sensor_type != SensorTypeEnum.IMU:
        return base

    vector = sensor_data.vector_data or []
    roll_deg = _safe_float(vector[0]) if len(vector) > 0 else None
    pitch_deg = _safe_float(vector[1]) if len(vector) > 1 else None
    yaw_deg = _safe_float(vector[2]) if len(vector) > 2 else None
    sensor_ts = sensor_data.timestamp.astimezone(timezone.utc)
    sensor_ts_iso = sensor_ts.isoformat().replace("+00:00", "Z")
    sensor_ts_epoch = sensor_ts.timestamp()

    sensor_plane["imu"] = {
        "enabled": True,
        "status": "ok",
        "reason": "grpc_imu_vector",
        "ok": True,
        "roll_rate_rps": None,
        "pitch_rate_rps": None,
        "yaw_rate_rps": None,
        "source_sensor_id": str(sensor_data.sensor_id),
    }
    sensor_plane["last_seen_ts"] = sensor_ts_iso
    base["attitude"] = {
        "roll_rad": _deg_to_rad(roll_deg),
        "pitch_rad": _deg_to_rad(pitch_deg),
        "yaw_rad": _deg_to_rad(yaw_deg),
    }
    base["timestamp"] = sensor_ts_iso
    base["ts_epoch"] = sensor_ts_epoch
    base["ts_unix_ms"] = int(sensor_ts_epoch * 1000)
    base["sensor_snapshot_source"] = "raw_sensor_data"

    return base


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _deg_to_rad(value: float | None) -> float | None:
    if value is None:
        return None
    return math.radians(value)
