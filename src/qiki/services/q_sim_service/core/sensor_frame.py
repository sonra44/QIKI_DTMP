from __future__ import annotations

import time
from typing import Any, Mapping

from qiki.shared.sensor_observation import (
    SensorObservationFrame,
    SensorObservationSnapshot,
    SensorObservationStatus,
    build_sensor_observation_frame_from_objective_world,
)
from qiki.shared.sensor_runtime import (
    SensorFrameSnapshot,
    SensorReadingSnapshot,
    SensorSourceKind,
    SensorStatus,
    normalize_sensor_status,
)
from qiki.shared.world_snapshot import WorldSnapshotSource, world_snapshot_ref_from_state


def build_truthful_sensor_frame(world_model: Any, *, now_ts: float | None = None) -> SensorFrameSnapshot:
    """Build a truthful, no-distortion sensor frame from WorldModel state.

    This is the baseline before any future "sensors lie" work.  It packages
    what WorldModel already knows into live readings with explicit source paths,
    timestamps, confidence and status.  It does not invent false telemetry.
    """

    now = float(now_ts if now_ts is not None else _world_now(world_model))
    state = world_model.get_state() if hasattr(world_model, "get_state") else {}
    state = state if isinstance(state, Mapping) else {}
    sensor_plane = _mapping(_get(state, "sensor_plane"))
    objective_world = _mapping(state.get("objective_world"))
    observation_frame = None
    if objective_world:
        observation_frame = build_sensor_observation_frame_from_objective_world(
            objective_world,
            observer_position_xyz_m=_mapping(state.get("position")),
            observer_velocity_xyz_m_s=_mapping(state.get("velocity_xyz_m_s")),
            generated_at_epoch_s=now,
        )
    readings: list[SensorReadingSnapshot] = []

    readings.append(_imu_reading(state, sensor_plane, now))
    readings.append(_radiation_reading(state, sensor_plane, now))
    readings.append(_proximity_reading(state, sensor_plane, now, observation_frame=observation_frame))
    readings.append(_solar_reading(state, sensor_plane, now))
    readings.append(_star_tracker_reading(state, sensor_plane, now))
    readings.append(_magnetometer_reading(state, sensor_plane, now))
    readings.append(_thermal_reading(state, now))
    readings.append(_power_reading(state, now))
    readings.append(_comms_reading(state, now))
    readings.append(_rcs_reading(state, now))
    readings.append(_docking_reading(state, now))

    world_ref = world_snapshot_ref_from_state(state, source=WorldSnapshotSource.SENSOR_RUNTIME)
    sensor_observation = {}
    metadata = {}
    if observation_frame is not None:
        sensor_observation = observation_frame.to_mapping()
        proximity_observation = observation_frame.by_sensor_id("sensor_proximity")
        if proximity_observation is not None:
            # Compatibility alias for consumers that read the proximity observation directly.
            sensor_observation["proximity"] = proximity_observation.to_mapping()
        metadata = {
            "sensor_observation_frame_id": observation_frame.observation_frame_id,
            "observation_boundary": "ObjectiveWorldState->SensorObservationFrame->SensorReadingSnapshot",
        }
    return SensorFrameSnapshot(
        tuple(readings),
        now,
        "q_sim_service.WorldModel.sensor_frame",
        world_tick_id=world_ref.world_tick_id,
        world_snapshot_id=world_ref.world_snapshot_id,
        source_world_snapshot_id=world_ref.world_snapshot_id,
        sim_time_s=world_ref.sim_time_s,
        sensor_observation=sensor_observation,
        metadata=metadata,
    )


def _imu_reading(state: Mapping[str, Any], sensor_plane: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    imu = _mapping(sensor_plane.get("imu"))
    status = _status_from_plane(imu, enabled=sensor_plane.get("enabled", True))
    confidence = 0.90 if status is SensorStatus.OK else 0.55 if status is SensorStatus.DEGRADED else 0.0
    value = {
        "roll_rate_rps": _num(imu.get("roll_rate_rps")),
        "pitch_rate_rps": _num(imu.get("pitch_rate_rps")),
        "yaw_rate_rps": _num(imu.get("yaw_rate_rps")),
        "attitude": _mapping(state.get("attitude")),
    }
    return SensorReadingSnapshot(
        sensor_id="imu_main",
        sensor_type="imu",
        subsystem="sensor_plane",
        status=status,
        value=value,
        unit="rad/s",
        confidence=confidence,
        quality=confidence,
        timestamp_epoch_s=now,
        source_kind=SensorSourceKind.LIVE,
        source_path="WorldModel.sensor_plane.imu",
        evidence=(str(imu.get("reason") or "world_model_imu"),),
    )


def _radiation_reading(state: Mapping[str, Any], sensor_plane: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    rad = _mapping(sensor_plane.get("radiation"))
    raw_status = str(rad.get("status") or "").lower()
    if raw_status in {"crit", "critical", "fault", "failed"}:
        status = SensorStatus.FAULT
    elif raw_status in {"warn", "warning", "degraded"}:
        status = SensorStatus.WARN
    elif raw_status in {"ok", "healthy", "nominal"}:
        status = SensorStatus.OK
    elif rad.get("enabled") is False:
        status = SensorStatus.OFFLINE
    else:
        status = SensorStatus.UNKNOWN
    value = {
        "background_usvh": _num(rad.get("background_usvh"), _get(state, "radiation_usvh")),
        "dose_total_usv": _num(rad.get("dose_total_usv")),
        "limits": _mapping(rad.get("limits")),
    }
    confidence = 1.0 if status in {SensorStatus.OK, SensorStatus.WARN, SensorStatus.FAULT} else 0.0
    return SensorReadingSnapshot(
        sensor_id="sensor_radiation",
        sensor_type="radiation",
        subsystem="sensor_plane",
        status=status,
        value=value,
        unit="uSv/h",
        confidence=confidence,
        quality=confidence,
        timestamp_epoch_s=now,
        source_kind=SensorSourceKind.LIVE,
        source_path="WorldModel.sensor_plane.radiation",
        evidence=(str(rad.get("reason") or "world_model_radiation"),),
    )


def _proximity_reading(
    state: Mapping[str, Any],
    sensor_plane: Mapping[str, Any],
    now: float,
    *,
    observation_frame: SensorObservationFrame | None = None,
) -> SensorReadingSnapshot:
    prox = _mapping(sensor_plane.get("proximity"))
    enabled = bool(prox.get("enabled", sensor_plane.get("enabled", True)))
    observation = observation_frame.by_sensor_id("sensor_proximity") if observation_frame is not None else None
    if observation is not None:
        return _proximity_reading_from_observation(
            observation,
            observation_frame=observation_frame,
            now=now,
            enabled=enabled,
        )

    contacts = _num(prox.get("contacts"), 0.0)
    min_range = _num(prox.get("min_range_m"))
    status = SensorStatus.OK if enabled else SensorStatus.OFFLINE
    confidence = 0.82 if enabled else 0.0
    if enabled and contacts is None and min_range is None:
        status = SensorStatus.MISSING
        confidence = 0.0
    source_path = str(prox.get("source_path") or "WorldModel.sensor_plane.proximity")
    evidence = ["world_model_proximity"]
    if source_path.startswith("q_sim_service.WorldModel.objective_world") or "ObjectiveWorldState" in source_path:
        evidence.append("source=objective_world")
    return SensorReadingSnapshot(
        sensor_id="sensor_proximity",
        sensor_type="proximity",
        subsystem="sensor_plane",
        status=status,
        value={
            "contacts": contacts,
            "min_range_m": min_range,
            "nearest_world_object_id": prox.get("nearest_world_object_id"),
            "collision_envelope": bool(prox.get("collision_envelope", False)),
        },
        unit="m",
        confidence=confidence,
        quality=confidence,
        timestamp_epoch_s=now if enabled else None,
        source_kind=SensorSourceKind.LIVE if enabled else SensorSourceKind.MISSING,
        source_path=source_path,
        evidence=tuple(evidence),
        metadata={
            "nearest_world_object_id": prox.get("nearest_world_object_id"),
            "world_snapshot_id": prox.get("world_snapshot_id"),
        },
    )


def _proximity_reading_from_observation(
    observation: SensorObservationSnapshot,
    *,
    observation_frame: SensorObservationFrame,
    now: float,
    enabled: bool = True,
) -> SensorReadingSnapshot:
    status = _status_from_observation(observation.status) if enabled else SensorStatus.OFFLINE
    confidence = observation.confidence if enabled else 0.0
    observed_world_object_ids = [item.world_object_id for item in observation.observed_objects]
    return SensorReadingSnapshot(
        sensor_id="sensor_proximity",
        sensor_type="proximity",
        subsystem="sensor_plane",
        status=status,
        value=observation.to_sensor_value(),
        unit="m",
        confidence=confidence,
        quality=confidence,
        timestamp_epoch_s=now if enabled and status is not SensorStatus.MISSING else None,
        source_kind=SensorSourceKind.LIVE if enabled and status is not SensorStatus.MISSING else SensorSourceKind.MISSING,
        source_path="SensorObservationFrame.observations[sensor_proximity]",
        evidence=(
            "world_model_proximity",
            "source=objective_world",
            "source=sensor_observation",
            f"observation_id={observation.observation_id}",
        ),
        metadata={
            "sensor_observation_id": observation.observation_id,
            "sensor_observation_frame_id": observation_frame.observation_frame_id,
            "objective_scene_id": observation.objective_scene_id,
            "world_snapshot_id": observation.world_snapshot_id,
            "source_world_snapshot_id": observation.source_world_snapshot_id,
            "nearest_world_object_id": observation.nearest_world_object_id,
            "observed_world_object_ids": observed_world_object_ids,
            "contacts_count": observation.contacts_count,
            "observation_boundary": "ObjectiveWorldState->SensorObservationFrame->SensorReadingSnapshot",
        },
        world_snapshot_id=observation.world_snapshot_id,
        source_world_snapshot_id=observation.source_world_snapshot_id,
        observation_id=observation.observation_id,
        observation_kind=observation.observation_kind.value,
    )

def _solar_reading(state: Mapping[str, Any], sensor_plane: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    solar = _mapping(sensor_plane.get("solar"))
    enabled = bool(solar.get("enabled", sensor_plane.get("enabled", True)))
    illumination = _num(solar.get("illumination_pct"), _get(state, "power", "solar_illumination_pct"))
    status = SensorStatus.OK if enabled and illumination is not None else SensorStatus.OFFLINE if not enabled else SensorStatus.MISSING
    confidence = 0.78 if status is SensorStatus.OK else 0.0
    return SensorReadingSnapshot(
        sensor_id="sensor_solar",
        sensor_type="solar",
        subsystem="sensor_plane",
        status=status,
        value={"illumination_pct": illumination},
        unit="percent",
        confidence=confidence,
        quality=confidence,
        timestamp_epoch_s=now if status is not SensorStatus.OFFLINE else None,
        source_kind=SensorSourceKind.LIVE if status is not SensorStatus.OFFLINE else SensorSourceKind.MISSING,
        source_path="WorldModel.sensor_plane.solar",
        evidence=("world_model_solar",),
    )


def _star_tracker_reading(state: Mapping[str, Any], sensor_plane: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    tracker = _mapping(sensor_plane.get("star_tracker"))
    status = _status_from_plane(tracker, enabled=sensor_plane.get("enabled", True))
    confidence = 0.86 if status is SensorStatus.OK else 0.45 if status in {SensorStatus.WARN, SensorStatus.DEGRADED} else 0.0
    return SensorReadingSnapshot(
        sensor_id="sensor_star_tracker",
        sensor_type="star_tracker",
        subsystem="sensor_plane",
        status=status,
        value={"locked": tracker.get("locked"), "status": tracker.get("status")},
        confidence=confidence,
        quality=confidence,
        timestamp_epoch_s=now if status is not SensorStatus.OFFLINE else None,
        source_kind=SensorSourceKind.LIVE if status is not SensorStatus.OFFLINE else SensorSourceKind.MISSING,
        source_path="WorldModel.sensor_plane.star_tracker",
        evidence=(str(tracker.get("reason") or "world_model_star_tracker"),),
    )


def _magnetometer_reading(state: Mapping[str, Any], sensor_plane: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    mag = _mapping(sensor_plane.get("magnetometer"))
    status = _status_from_plane(mag, enabled=sensor_plane.get("enabled", True))
    confidence = 0.72 if status is SensorStatus.OK else 0.4 if status in {SensorStatus.WARN, SensorStatus.DEGRADED} else 0.0
    return SensorReadingSnapshot(
        sensor_id="magnetometer",
        sensor_type="magnetometer",
        subsystem="sensor_plane",
        status=status,
        value={"field_ut": _num(mag.get("field_ut")), "status": mag.get("status")},
        unit="uT",
        confidence=confidence,
        quality=confidence,
        timestamp_epoch_s=now if status is not SensorStatus.OFFLINE else None,
        source_kind=SensorSourceKind.LIVE if status is not SensorStatus.OFFLINE else SensorSourceKind.MISSING,
        source_path="WorldModel.sensor_plane.magnetometer",
        evidence=(str(mag.get("reason") or "world_model_magnetometer"),),
    )


def _thermal_reading(state: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    thermal = _mapping(state.get("thermal"))
    core = _num(thermal.get("core_c"), state.get("temp_core_c"))
    status = _status_from_text(thermal.get("status"))
    if status is SensorStatus.UNKNOWN:
        status = SensorStatus.OK if core is not None and core < 75 else SensorStatus.WARN if core is not None and core < 90 else SensorStatus.FAULT if core is not None else SensorStatus.MISSING
    confidence = 0.95 if core is not None else 0.0
    return SensorReadingSnapshot("sensor_thermal", "thermal", "body", status, now if core is not None else None, SensorSourceKind.LIVE if core is not None else SensorSourceKind.MISSING, "WorldModel.thermal", {"core_c": core}, "degC", confidence, confidence, evidence=("world_model_thermal",))


def _power_reading(state: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    power = _mapping(state.get("power"))
    soc = _num(power.get("soc_pct"), power.get("battery_soc_pct"), state.get("battery"))
    bus_v = _num(power.get("bus_v"), power.get("bus_voltage_v"))
    status = SensorStatus.OK if soc is not None or bus_v is not None else SensorStatus.MISSING
    confidence = 0.95 if status is SensorStatus.OK else 0.0
    return SensorReadingSnapshot("sensor_power", "power", "body", status, now if status is SensorStatus.OK else None, SensorSourceKind.LIVE if status is SensorStatus.OK else SensorSourceKind.MISSING, "WorldModel.power", {"soc_pct": soc, "bus_v": bus_v}, "mixed", confidence, confidence, evidence=("world_model_power",))


def _comms_reading(state: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    comms = _mapping(state.get("comms"))
    xpdr = _mapping(state.get("xpdr"))
    online = comms.get("online", comms.get("connected", xpdr.get("enabled")))
    status = SensorStatus.OK if online is True else SensorStatus.OFFLINE if online is False else SensorStatus.UNKNOWN
    confidence = 0.8 if status is SensorStatus.OK else 0.2 if status is SensorStatus.UNKNOWN else 0.0
    return SensorReadingSnapshot("sensor_comms", "comms", "body", status, now if status is not SensorStatus.OFFLINE else None, SensorSourceKind.LIVE if status is not SensorStatus.OFFLINE else SensorSourceKind.MISSING, "WorldModel.comms", {"online": online, "xpdr_mode": xpdr.get("mode")}, "state", confidence, confidence, evidence=("world_model_comms",))


def _rcs_reading(state: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    rcs = _mapping(_get(state, "actuation", "rcs"))
    source_path = "WorldModel.actuation.rcs"
    if not rcs:
        rcs = _mapping(_get(state, "propulsion", "rcs"))
        source_path = "WorldModel.propulsion.rcs"
    enabled = rcs.get("enabled")
    status = SensorStatus.OK if enabled is True else SensorStatus.OFFLINE if enabled is False else SensorStatus.UNKNOWN
    if rcs.get("throttled"):
        status = SensorStatus.WARN
    if rcs.get("effect_status") == "REJECTED":
        status = SensorStatus.FAULT
    confidence = 0.85 if status in {SensorStatus.OK, SensorStatus.WARN} else 0.35 if status is SensorStatus.FAULT else 0.0
    value = {
        "active": rcs.get("active"),
        "desired_axis": rcs.get("desired_axis"),
        "actual_axis": rcs.get("actual_axis", rcs.get("axis")),
        "actual_pct": _num(rcs.get("actual_pct"), rcs.get("command_pct")),
        "burn_id": rcs.get("burn_id"),
        "command_id": rcs.get("command_id"),
        "effect_status": rcs.get("effect_status"),
        "power_w": _num(rcs.get("power_w")),
        "heat_w": _num(rcs.get("heat_w")),
        "net_force_n": rcs.get("net_force_n"),
        "net_torque_nm": rcs.get("net_torque_nm"),
    }
    return SensorReadingSnapshot(
        "sensor_rcs",
        "rcs",
        "body",
        status,
        now if status is not SensorStatus.OFFLINE else None,
        SensorSourceKind.LIVE if status is not SensorStatus.OFFLINE else SensorSourceKind.MISSING,
        source_path,
        value,
        "mixed",
        confidence,
        confidence,
        evidence=("world_model_actuation_rcs",),
    )


def _docking_reading(state: Mapping[str, Any], now: float) -> SensorReadingSnapshot:
    docking = _mapping(state.get("docking"))
    enabled = docking.get("enabled")
    status = SensorStatus.OK if enabled is True else SensorStatus.OFFLINE if enabled is False else SensorStatus.UNKNOWN
    confidence = 0.82 if status is SensorStatus.OK else 0.0
    return SensorReadingSnapshot("sensor_docking", "docking", "body", status, now if status is SensorStatus.OK else None, SensorSourceKind.LIVE if status is SensorStatus.OK else SensorSourceKind.MISSING, "WorldModel.docking", {"state": docking.get("state"), "connected": docking.get("connected"), "port": docking.get("port")}, "state", confidence, confidence, evidence=("world_model_docking",))





def _status_from_observation(status: SensorObservationStatus | str) -> SensorStatus:
    if isinstance(status, SensorObservationStatus):
        obs_status = status
    else:
        text = str(status or "unknown").strip().lower()
        obs_status = next((item for item in SensorObservationStatus if item.value == text), SensorObservationStatus.UNKNOWN)
    if obs_status in {SensorObservationStatus.OBSERVED, SensorObservationStatus.CLEAR}:
        return SensorStatus.OK
    if obs_status is SensorObservationStatus.DEGRADED:
        return SensorStatus.DEGRADED
    if obs_status is SensorObservationStatus.BLOCKED:
        return SensorStatus.WARN
    if obs_status is SensorObservationStatus.MISSING:
        return SensorStatus.MISSING
    return SensorStatus.UNKNOWN

def _status_from_plane(block: Mapping[str, Any], *, enabled: Any = True) -> SensorStatus:
    if block.get("enabled") is False or enabled is False:
        return SensorStatus.OFFLINE
    raw = block.get("status")
    if raw is not None:
        return _status_from_text(raw)
    ok = block.get("ok")
    if ok is True:
        return SensorStatus.OK
    if ok is False:
        return SensorStatus.DEGRADED
    return SensorStatus.UNKNOWN


def _status_from_text(value: Any) -> SensorStatus:
    status = normalize_sensor_status(value)
    if status is SensorStatus.UNKNOWN:
        text = str(value or "").strip().lower()
        if text in {"warn", "warning"}:
            return SensorStatus.WARN
        if text in {"crit", "critical"}:
            return SensorStatus.FAULT
    return status


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _get(mapping: Mapping[str, Any], *path: str) -> Any:
    current: Any = mapping
    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


def _num(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed == parsed and parsed not in (float("inf"), float("-inf")):
            return parsed
    return None


def _world_now(world_model: Any) -> float:
    if hasattr(world_model, "sim_time_epoch_ts"):
        try:
            return float(world_model.sim_time_epoch_ts())
        except Exception:
            pass
    return time.time()
