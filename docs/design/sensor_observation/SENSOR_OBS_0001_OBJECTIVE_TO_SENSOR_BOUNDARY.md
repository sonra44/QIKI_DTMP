# SENSOR-OBS-0001 — ObjectiveWorldState to Sensor Observation Boundary

## Purpose

`SENSOR-OBS-0001` introduces an explicit Layer-07 boundary between objective-world truth and runtime sensor readings.

Before this patch, `sensor_runtime.sensor_proximity` could read a proximity summary that was already present in `WorldModel.sensor_plane.proximity`. After `OBJECTIVE-0001`, that was not strict enough: the objective scene existed, but sensor runtime still had no separate object proving that a sensor observed that scene.

The new chain is:

```text
ObjectiveWorldState public mapping
→ SensorObservationFrame
→ SensorObservationSnapshot(sensor_proximity)
→ SensorReadingSnapshot(sensor_proximity)
→ SensorFrameSnapshot.sensor_observation
```

This is still a truthful baseline. It does not add sensor lottery, false readings, noise, hallucination, target inference or hidden-truth leakage.

## Ownership

`ObjectiveWorldState` owns what objectively exists in the scene.

`SensorObservationFrame` owns what a concrete sensor observation derived from that objective scene can report.

`SensorReadingSnapshot` owns the runtime sensor reading exported to the rest of QIKI.

`SensorFrameSnapshot` owns the full sensor-runtime frame and stores the observation frame as provenance metadata.

## Runtime fields

`SensorObservationFrame` carries:

```text
observation_frame_id
objective_scene_id
world_tick_id
world_snapshot_id
source_world_snapshot_id
sim_time_s
observations[]
evidence[]
metadata
```

`SensorObservationSnapshot(sensor_proximity)` carries:

```text
observation_id
sensor_id
sensor_type
observation_kind
status
objective_scene_id
observed_objects[]
nearest_world_object_id
min_range_m
contacts_count
collision_envelope
confidence
world_tick_id
world_snapshot_id
source_world_snapshot_id
sim_time_s
evidence[]
metadata
```

`SensorReadingSnapshot(sensor_proximity)` now includes the observation identity:

```text
source_path = SensorObservationFrame.observations[sensor_proximity]
observation_id
observation_kind
metadata.sensor_observation_id
metadata.sensor_observation_frame_id
metadata.objective_scene_id
metadata.observed_world_object_ids
metadata.observation_boundary
```

## Hidden-truth rule

`SensorObservationFrame` is built from a public projection of `ObjectiveWorldState`.

The following private objective-world fields must not leak through sensor observation or sensor runtime:

```text
hidden_truth
true_transponder_id
```

The boundary may state that private truth was redacted, but it must not copy the private payload.

## Compatibility

If `WorldModel.get_state()` does not include `objective_world`, `sensor_proximity` keeps the legacy `WorldModel.sensor_plane.proximity` path. This preserves older truthful sensor-runtime behavior while allowing the new objective-scene path when Layer 06 is present.

## Non-goals

This patch intentionally does not implement:

```text
sensor lottery
false contacts
noise model
range/angle degradation
occlusion/FOV masks
radar-track fusion
operator target inference
sensor trust decision
```

Those belong to later Layer-07 and Layer-08 work.

## Acceptance

```text
given ObjectiveWorldState with OBJ-STATION-01 and OBJ-DEBRIS-01
when build_truthful_sensor_frame() runs
then SensorFrameSnapshot.sensor_observation exists
and sensor_proximity.source_path == SensorObservationFrame.observations[sensor_proximity]
and sensor_proximity.metadata.sensor_observation_id exists
and observed_world_object_ids contains the observed objective objects
and hidden_truth / true_transponder_id are not exposed
```
