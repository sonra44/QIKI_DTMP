from __future__ import annotations

"""Layer-06 Objective Scene runtime for q-sim.

The objective scene owns lower-truth objects, zones and fields.  Radar and
proximity sensors observe this scene; they do not create the scene truth.
"""

import math
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from qiki.shared.models.radar import RadarDetectionModel, RangeBand, TransponderModeEnum
from qiki.shared.radar_coords import xyz_to_polar
from qiki.shared.objective_world import (
    ObjectiveWorldField,
    ObjectiveWorldState,
    ObjectiveWorldZone,
    WorldObjectState,
    vector3_mapping,
    vector3_norm,
    vector3_sub,
)
from qiki.shared.world_snapshot import WorldSnapshotRef


DEFAULT_SCENE_ID = "SCENE-TERTA-LOCAL"


def _finite_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(default)
    try:
        parsed = float(value)
    except Exception:
        return float(default)
    return parsed if math.isfinite(parsed) else float(default)


@dataclass(slots=True)
class ObjectiveScene:
    """Mutable q-sim scene owner for Layer 06.

    This object is deliberately small.  It gives QIKI_DTMP an objective-world
    baseline without turning q-sim into the future independent world-engine.
    """

    scene_id: str = DEFAULT_SCENE_ID
    sr_threshold_m: float = 5000.0
    objects: tuple[WorldObjectState, ...] = field(default_factory=tuple)
    zones: tuple[ObjectiveWorldZone, ...] = field(default_factory=tuple)
    fields: tuple[ObjectiveWorldField, ...] = field(default_factory=tuple)
    sim_time_s: float = 0.0

    @classmethod
    def default(cls, *, sr_threshold_m: float = 5000.0) -> "ObjectiveScene":
        threshold = max(1.0, _finite_float(sr_threshold_m, 5000.0))
        sr_y = threshold * 0.5
        lr_y = threshold * 1.5
        objects = (
            WorldObjectState(
                world_object_id="OBJ-STATION-01",
                object_type="STATION",
                position_xyz_m={"x": 0.0, "y": sr_y, "z": 0.0},
                velocity_xyz_m_s={"x": 0.0, "y": 0.0, "z": 0.0},
                radius_m=75.0,
                collision_radius_m=120.0,
                radar_cross_section_dbsm=12.0,
                transponder_mode="ON",
                true_transponder_id="STATION-TERTA-A-TRUE",
                visible_transponder_id="STATION-TERTA-A",
                thermal_signature={"kind": "station_bus", "relative_heat": 0.25},
                optical_signature={"albedo": 0.42},
                comms_signature={"beacon": True},
                observable_profile={"radar_visible": True, "range_class": "sr", "transponder_visible": True},
                hidden_truth={"scenario_role": "dock_candidate", "allegiance": "unknown"},
                metadata={"label": "baseline station object"},
                evidence=("layer=06.objective_world", "default_object=station"),
            ),
            WorldObjectState(
                world_object_id="OBJ-DEBRIS-01",
                object_type="DEBRIS",
                position_xyz_m={"x": threshold * 0.2, "y": lr_y, "z": 80.0},
                velocity_xyz_m_s={"x": -0.2, "y": 0.0, "z": 0.0},
                radius_m=2.0,
                collision_radius_m=8.0,
                radar_cross_section_dbsm=1.0,
                transponder_mode="OFF",
                true_transponder_id=None,
                visible_transponder_id=None,
                thermal_signature={"kind": "cold_debris", "relative_heat": 0.02},
                optical_signature={"albedo": 0.12},
                observable_profile={"radar_visible": True, "range_class": "lr", "transponder_visible": False},
                hidden_truth={"scenario_role": "navigation_hazard"},
                metadata={"label": "baseline debris object"},
                evidence=("layer=06.objective_world", "default_object=debris"),
            ),
            WorldObjectState(
                world_object_id="OBJ-UNKNOWN-01",
                object_type="UNKNOWN",
                position_xyz_m={"x": -threshold * 0.7, "y": threshold * 2.2, "z": -40.0},
                velocity_xyz_m_s={"x": 0.0, "y": 0.0, "z": 0.0},
                radius_m=15.0,
                collision_radius_m=35.0,
                radar_cross_section_dbsm=4.0,
                transponder_mode="SILENT",
                true_transponder_id="HIDDEN-UNKNOWN-01",
                visible_transponder_id=None,
                thermal_signature={"kind": "masked", "relative_heat": 0.0},
                observable_profile={"radar_visible": False, "reason": "masked_baseline"},
                hidden_truth={"scenario_role": "unknown_contact", "allegiance": "withheld"},
                metadata={"label": "baseline hidden unknown"},
                evidence=("layer=06.objective_world", "default_object=unknown_hidden"),
            ),
        )
        zones = (
            ObjectiveWorldZone(
                zone_id="ZONE-QIKI-LOCAL-SR",
                zone_type="sensor_range_hint",
                center_xyz_m={"x": 0.0, "y": 0.0, "z": 0.0},
                radius_m=threshold,
                metadata={"range_band": "SR"},
            ),
        )
        fields = (
            ObjectiveWorldField(
                field_id="FIELD-RADIATION-BACKGROUND",
                field_type="radiation_background",
                value={"usvh": 0.0},
                metadata={"unit": "uSv/h"},
            ),
        )
        return cls(scene_id=DEFAULT_SCENE_ID, sr_threshold_m=threshold, objects=objects, zones=zones, fields=fields)

    def step(self, delta_time_s: float) -> None:
        dt = max(0.0, _finite_float(delta_time_s, 0.0))
        if dt <= 0.0:
            return
        self.sim_time_s += dt
        self.objects = tuple(obj.advance(dt) for obj in self.objects)

    def _objects_for_threshold(
        self,
        *,
        sr_threshold_m: float | None,
        transponder_mode: str | None,
        visible_transponder_id: str | None,
    ) -> tuple[WorldObjectState, ...]:
        threshold = max(1.0, _finite_float(sr_threshold_m, self.sr_threshold_m))
        if abs(threshold - self.sr_threshold_m) < 1e-9 and transponder_mode is None and visible_transponder_id is None:
            return self.objects
        sr_y = threshold * 0.5
        lr_y = threshold * 1.5
        out: list[WorldObjectState] = []
        for obj in self.objects:
            if obj.world_object_id == "OBJ-STATION-01":
                out.append(
                    replace(
                        obj,
                        position_xyz_m={"x": 0.0, "y": sr_y, "z": 0.0},
                        transponder_mode=str(transponder_mode or obj.transponder_mode or "ON"),
                        visible_transponder_id=visible_transponder_id if visible_transponder_id is not None else obj.visible_transponder_id,
                    )
                )
            elif obj.world_object_id == "OBJ-DEBRIS-01":
                out.append(replace(obj, position_xyz_m={"x": threshold * 0.2, "y": lr_y, "z": 80.0}))
            elif obj.world_object_id == "OBJ-UNKNOWN-01":
                out.append(replace(obj, position_xyz_m={"x": -threshold * 0.7, "y": threshold * 2.2, "z": -40.0}))
            else:
                out.append(obj)
        return tuple(out)

    def build_state(
        self,
        *,
        world_ref: WorldSnapshotRef,
        observer_position_xyz_m: Mapping[str, Any],
        observer_velocity_xyz_m_s: Mapping[str, Any] | list[float] | None = None,
        sr_threshold_m: float | None = None,
        transponder_mode: str | None = None,
        visible_transponder_id: str | None = None,
    ) -> ObjectiveWorldState:
        objects = self._objects_for_threshold(
            sr_threshold_m=sr_threshold_m,
            transponder_mode=transponder_mode,
            visible_transponder_id=visible_transponder_id,
        )
        state = ObjectiveWorldState(
            scene_id=self.scene_id,
            objects=objects,
            zones=self.zones,
            fields=self.fields,
            world_tick_id=world_ref.world_tick_id,
            world_snapshot_id=world_ref.world_snapshot_id,
            source_world_snapshot_id=world_ref.world_snapshot_id,
            sim_time_s=world_ref.sim_time_s,
            source_path="q_sim_service.core.objective_scene.ObjectiveScene.build_state",
            evidence=(
                "layer=06.objective_world",
                "owner=q_sim_service.WorldModel",
                f"world_snapshot_id={world_ref.world_snapshot_id}",
                "world_object_id_is_not_radar_track_id",
            ),
        )
        proximity = nearest_object_summary(state, observer_position_xyz_m=observer_position_xyz_m)
        return replace(state, metadata={"proximity": proximity})


def nearest_object_summary(
    scene: ObjectiveWorldState,
    *,
    observer_position_xyz_m: Mapping[str, Any],
) -> dict[str, Any]:
    qiki_pos = vector3_mapping(observer_position_xyz_m)
    nearest_id: str | None = None
    nearest_type: str | None = None
    nearest_range: float | None = None
    contacts = 0
    for obj in scene.objects:
        if obj.status.value != "active":
            continue
        rel = vector3_sub(obj.position_xyz_m, qiki_pos)
        rng = vector3_norm(rel)
        contacts += 1
        if nearest_range is None or rng < nearest_range:
            nearest_range = float(rng)
            nearest_id = obj.world_object_id
            nearest_type = obj.object_type.value
    return {
        "source_path": "ObjectiveWorldState.objects",
        "scene_id": scene.scene_id,
        "nearest_world_object_id": nearest_id,
        "nearest_object_id": nearest_id,
        "nearest_object_type": nearest_type,
        "min_range_m": nearest_range,
        "contacts_count": contacts,
        "contacts": contacts,
        "collision_envelope": bool(nearest_range is not None and nearest_range <= 50.0),
        "world_snapshot_id": scene.world_snapshot_id,
    }



def build_default_objective_world_state(
    world_state: Mapping[str, Any] | None = None,
    *,
    world_ref: WorldSnapshotRef | None = None,
    sr_threshold_m: float = 100.0,
) -> ObjectiveWorldState:
    """Build a deterministic public objective scene for unit tests and probes."""

    ref = world_ref or WorldSnapshotRef(source="objective_world")
    state = world_state if isinstance(world_state, Mapping) else {}
    observer_position = state.get("position") if isinstance(state.get("position"), Mapping) else {"x": 0.0, "y": 0.0, "z": 0.0}
    return ObjectiveScene.default(sr_threshold_m=sr_threshold_m).build_state(
        world_ref=ref,
        observer_position_xyz_m=observer_position,
        sr_threshold_m=sr_threshold_m,
    )


def build_radar_detections_from_objective_world(
    scene: ObjectiveWorldState | Mapping[str, Any],
    *,
    observer_position_xyz_m: Mapping[str, Any],
    observer_velocity_xyz_m_s: Mapping[str, Any] | None = None,
    sr_threshold_m: float = 5000.0,
    transponder_mode_override: TransponderModeEnum | str | int | None = None,
    transponder_id_override: str | None = None,
) -> list[RadarDetectionModel]:
    """Derive radar detections from ObjectiveWorldState without leaking hidden truth.

    This helper is intentionally independent from QSimService so unit tests can
    validate Layer-06 behavior without importing generated protobuf modules.
    QSimService keeps a service-local compatibility wrapper because its SR
    station beacon must still honor q-sim's XPDR runtime settings.
    """

    if isinstance(scene, ObjectiveWorldState):
        scene_id = scene.scene_id
        source_world_snapshot_id = scene.world_snapshot_id
        objects = [obj.to_mapping(include_hidden_truth=False) for obj in scene.objects]
    elif isinstance(scene, Mapping):
        scene_id = str(scene.get("scene_id") or "")
        source_world_snapshot_id = str(scene.get("world_snapshot_id") or "") or None
        raw_objects = scene.get("objects")
        objects = list(raw_objects) if isinstance(raw_objects, list) else []
    else:
        return []

    observer_velocity_xyz_m_s = observer_velocity_xyz_m_s if isinstance(observer_velocity_xyz_m_s, Mapping) else {}
    sr_threshold = max(1.0, _finite_float(sr_threshold_m, 5000.0))
    detections: list[RadarDetectionModel] = []
    for obj in objects:
        if not isinstance(obj, Mapping):
            continue
        profile = obj.get("observable_profile") if isinstance(obj.get("observable_profile"), Mapping) else {}
        if profile.get("radar_visible") is False:
            continue
        if str(obj.get("status") or "active").strip().lower() not in {"active", "dormant"}:
            continue

        obj_pos = obj.get("position_xyz_m") if isinstance(obj.get("position_xyz_m"), Mapping) else {}
        obj_vel = obj.get("velocity_xyz_m_s") if isinstance(obj.get("velocity_xyz_m_s"), Mapping) else {}
        rel = {
            "x": _finite_float(obj_pos.get("x")) - _finite_float(observer_position_xyz_m.get("x")),
            "y": _finite_float(obj_pos.get("y")) - _finite_float(observer_position_xyz_m.get("y")),
            "z": _finite_float(obj_pos.get("z")) - _finite_float(observer_position_xyz_m.get("z")),
        }
        range_m, bearing_deg, elev_deg = xyz_to_polar(x_m=rel["x"], y_m=rel["y"], z_m=rel["z"])
        if range_m <= 0.01:
            continue
        rel_vel = {
            "x": _finite_float(obj_vel.get("x")) - _finite_float(observer_velocity_xyz_m_s.get("x")),
            "y": _finite_float(obj_vel.get("y")) - _finite_float(observer_velocity_xyz_m_s.get("y")),
            "z": _finite_float(obj_vel.get("z")) - _finite_float(observer_velocity_xyz_m_s.get("z")),
        }
        vr_mps = (rel["x"] * rel_vel["x"] + rel["y"] * rel_vel["y"] + rel["z"] * rel_vel["z"]) / max(range_m, 1e-9)
        range_band = RangeBand.RR_SR if range_m <= sr_threshold else RangeBand.RR_LR

        visible_id = obj.get("visible_transponder_id")
        mode = _radar_mode_from_value(transponder_mode_override if transponder_mode_override is not None else obj.get("transponder_mode"))
        transponder_id = str(visible_id or "") or None
        if transponder_id_override and str(obj.get("world_object_id") or "") != "OBJ-STATION-01":
            transponder_id = str(transponder_id_override)
        transponder_on = bool(transponder_id and mode in {TransponderModeEnum.ON, TransponderModeEnum.SPOOF})
        if range_band == RangeBand.RR_LR:
            transponder_on = False
            mode = TransponderModeEnum.OFF
            transponder_id = None
            id_present = None
        else:
            id_present = bool(transponder_id)

        rcs_dbsm = _finite_float(obj.get("radar_cross_section_dbsm"), 0.0)
        snr_db = max(1.0, 34.0 + (rcs_dbsm * 0.2) - 20.0 * math.log10(max(1.0, range_m) / 100.0))
        world_object_id = str(obj.get("world_object_id") or "")
        detections.append(
            RadarDetectionModel(
                range_m=float(range_m),
                bearing_deg=float(bearing_deg),
                elev_deg=float(elev_deg),
                vr_mps=float(vr_mps),
                snr_db=float(snr_db),
                rcs_dbsm=float(rcs_dbsm),
                transponder_on=transponder_on,
                transponder_mode=mode,
                transponder_id=transponder_id,
                range_band=range_band,
                id_present=id_present,
                world_object_id=world_object_id or None,
                objective_scene_id=scene_id or None,
                objective_object_type=str(obj.get("object_type") or "unknown"),
                source_world_snapshot_id=source_world_snapshot_id,
                source_path=f"ObjectiveWorldState.objects[{world_object_id}]" if world_object_id else "ObjectiveWorldState.objects",
                metadata={"objective_world_observation": True, "private_truth_redacted": True},
            )
        )
    detections.sort(key=lambda det: (0 if det.range_band == RangeBand.RR_LR else 1, det.range_m, det.world_object_id or ""))
    return detections


def _radar_mode_from_value(value: TransponderModeEnum | str | int | None) -> TransponderModeEnum:
    if isinstance(value, TransponderModeEnum):
        return value
    if isinstance(value, int):
        try:
            return TransponderModeEnum(value)
        except Exception:
            return TransponderModeEnum.OFF
    text = str(value or "OFF").strip().upper()
    return {
        "ON": TransponderModeEnum.ON,
        "SILENT": TransponderModeEnum.SILENT,
        "SPOOF": TransponderModeEnum.SPOOF,
        "OFF": TransponderModeEnum.OFF,
    }.get(text, TransponderModeEnum.OFF)
