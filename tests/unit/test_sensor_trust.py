from __future__ import annotations

from dataclasses import replace


from qiki.services.q_sim_service.core.objective_scene import build_default_objective_world_state
from qiki.services.q_sim_service.core.sensor_frame import build_truthful_sensor_frame
from qiki.shared.sensor_runtime import SensorFrameSnapshot, SensorReadingSnapshot, SensorSourceKind, SensorStatus
from qiki.shared.sensor_trust import (
    SensorTrustSnapshot,
    SensorTrustState,
    build_sensor_trust_snapshot,
    sensor_trust_from_telemetry,
)
from qiki.shared.world_snapshot import WorldSnapshotRef, WorldSnapshotSource


class _FakeWorldWithObjectiveScene:
    def __init__(self, objective_world: dict):
        self._objective_world = objective_world

    def sim_time_epoch_ts(self) -> float:
        return 1000.0

    def get_state(self) -> dict:
        return {
            "world_tick_id": self._objective_world["world_tick_id"],
            "world_snapshot_id": self._objective_world["world_snapshot_id"],
            "source_world_snapshot_id": self._objective_world["source_world_snapshot_id"],
            "sim_time_s": self._objective_world["sim_time_s"],
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "velocity_xyz_m_s": {"x": 0.0, "y": 0.0, "z": 0.0},
            "objective_world": self._objective_world,
            "sensor_plane": {
                "enabled": True,
                "imu": {"enabled": True, "status": "ok", "reason": "unit_test", "roll_rate_rps": 0.01},
                "radiation": {"enabled": True, "status": "ok", "background_usvh": 22.0, "dose_total_usv": 4.0},
                "proximity": {"enabled": True, "contacts": 0, "min_range_m": None},
                "solar": {"enabled": True, "illumination_pct": 61.0},
                "star_tracker": {"enabled": True, "status": "ok", "locked": True},
                "magnetometer": {"enabled": True, "status": "ok", "field_ut": 42.0},
            },
            "attitude": {"roll_rad": 0.0, "pitch_rad": 0.0, "yaw_rad": 0.0},
            "thermal": {"core_c": 44.0},
            "power": {"soc_pct": 78.0, "bus_v": 28.0},
            "comms": {"online": True},
            "xpdr": {"enabled": True, "mode": "ON"},
            "actuation": {"rcs": {"enabled": True, "active": False, "power_w": 0.0}},
            "propulsion": {"rcs": {"enabled": True, "active": False, "power_w": 0.0}},
            "docking": {"enabled": True, "state": "idle", "connected": False},
        }


def _scene_ref() -> WorldSnapshotRef:
    return WorldSnapshotRef(
        world_tick_index=9,
        world_snapshot_index=12,
        sim_time_s=5.5,
        source=WorldSnapshotSource.OBJECTIVE_WORLD,
    )


def _trusted_frame() -> SensorFrameSnapshot:
    scene = build_default_objective_world_state({}, world_ref=_scene_ref(), sr_threshold_m=100.0)
    return build_truthful_sensor_frame(_FakeWorldWithObjectiveScene(scene.to_mapping()), now_ts=1000.0)


def test_sensor_trust_snapshot_is_derived_from_sensor_frame_with_lineage() -> None:
    frame = _trusted_frame()
    snapshot = build_sensor_trust_snapshot(sensor_frame=frame, now_ts=1000.0)
    mapped = snapshot.to_mapping()
    parsed = SensorTrustSnapshot.from_mapping(mapped)

    assert snapshot.state is SensorTrustState.TRUSTED
    assert snapshot.world_snapshot_id == frame.world_snapshot_id
    assert snapshot.source_world_snapshot_id == frame.source_world_snapshot_id
    assert snapshot.observation_frame_id == frame.sensor_observation["observation_frame_id"]
    assert "sensor_proximity" in snapshot.input_sensor_ids
    assert snapshot.input_observation_ids
    assert snapshot.constrains_mainfsm is False
    assert parsed.state is SensorTrustState.TRUSTED
    assert parsed.world_snapshot_id == snapshot.world_snapshot_id


def test_explicit_trusted_does_not_override_missing_critical_sensor() -> None:
    frame = _trusted_frame()
    frame_without_power = SensorFrameSnapshot(
        readings=tuple(reading for reading in frame.readings if reading.sensor_id != "sensor_power"),
        generated_at_epoch_s=frame.generated_at_epoch_s,
        source_path=frame.source_path,
        world_tick_id=frame.world_tick_id,
        world_snapshot_id=frame.world_snapshot_id,
        source_world_snapshot_id=frame.source_world_snapshot_id,
        sim_time_s=frame.sim_time_s,
        sensor_observation=frame.sensor_observation,
        metadata=frame.metadata,
    )

    snapshot = build_sensor_trust_snapshot(
        sensor_frame=frame_without_power,
        telemetry={"sensor_trust": {"state": "trusted", "confidence": 0.95}},
        now_ts=1000.0,
    )

    assert snapshot.state is SensorTrustState.DEGRADED
    assert "sensor_power" in snapshot.missing_critical_sensors
    assert any("ignored" in item for item in snapshot.evidence)


def test_proximity_contact_without_radar_tracks_is_conflicting_when_tracks_are_available_input() -> None:
    frame = _trusted_frame()
    snapshot = build_sensor_trust_snapshot(sensor_frame=frame, radar_tracks=[], now_ts=1000.0)

    assert snapshot.state is SensorTrustState.CONFLICTING
    assert any("proximity sees contact" in item for item in snapshot.conflict_markers)
    assert snapshot.constrains_mainfsm is True


def test_high_radiation_marks_sensor_trust_as_lottery() -> None:
    frame = _trusted_frame()
    changed: list[SensorReadingSnapshot] = []
    for reading in frame.readings:
        if reading.sensor_id == "sensor_radiation":
            changed.append(
                replace(
                    reading,
                    value={"background_usvh": 6000.0, "dose_total_usv": 40.0},
                    status=SensorStatus.WARN,
                    confidence=1.0,
                    source_kind=SensorSourceKind.LIVE,
                )
            )
        else:
            changed.append(reading)
    radiation_frame = SensorFrameSnapshot(
        readings=tuple(changed),
        generated_at_epoch_s=frame.generated_at_epoch_s,
        source_path=frame.source_path,
        world_tick_id=frame.world_tick_id,
        world_snapshot_id=frame.world_snapshot_id,
        source_world_snapshot_id=frame.source_world_snapshot_id,
        sim_time_s=frame.sim_time_s,
        sensor_observation=frame.sensor_observation,
        metadata=frame.metadata,
    )

    snapshot = build_sensor_trust_snapshot(sensor_frame=radiation_frame, now_ts=1000.0)

    assert snapshot.state is SensorTrustState.LOTTERY
    assert snapshot.decision is not None
    assert snapshot.decision.allowed_for_high_risk_action is False
    assert any("radiation=6000" in item for item in snapshot.evidence)


def test_sensor_trust_from_telemetry_reads_sensor_runtime_mapping() -> None:
    frame = _trusted_frame()
    snapshot = sensor_trust_from_telemetry(
        {"sensor_runtime": frame.to_mapping(), "timestamp": "1970-01-01T00:16:40Z"},
        now_ts=1000.0,
    )

    assert snapshot.state is SensorTrustState.TRUSTED
    assert snapshot.world_snapshot_id == frame.world_snapshot_id


def test_orion_sensor_trust_model_delegates_to_shared_contract() -> None:
    from qiki.services.operator_console.orion_v.sensor_trust_model import build_sensor_trust_snapshot as orion_build

    frame = _trusted_frame()
    snapshot = orion_build(telemetry={"sensor_runtime": frame.to_mapping()})

    assert snapshot.state.value == SensorTrustState.TRUSTED.value
    assert snapshot.source_path.startswith("qiki.shared.sensor_trust")
