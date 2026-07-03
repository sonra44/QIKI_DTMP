# SENSORTRUST-0001 — Shared Sensor Trust Runtime Contract

## Purpose

Layer 08 is no longer an ORION-local heuristic only. It now has a shared Python runtime contract:

```text
SensorFrameSnapshot
+ SensorObservationFrame boundary
+ freshness / confidence / status
+ optional radar tracks / lower-layer health
→ SensorTrustSnapshot
```

`SensorTrustSnapshot` is a derived decision surface. It does not mutate `WorldModel` truth, does not mark sensors as broken by itself, and does not turn an operator override into runtime truth.

## Owner

```text
src/qiki/shared/sensor_trust.py
```

Primary types:

```text
SensorTrustState
SensorTrustReason
SensorTrustEvidence
SensorTrustDecision
SensorTrustSnapshot
```

Primary evaluator:

```text
build_sensor_trust_snapshot(...)
```

## Runtime chain

```text
ObjectiveWorldState
→ SensorObservationFrame
→ SensorFrameSnapshot
→ SensorTrustSnapshot
→ telemetry.sensor_trust
→ ORION / future MainFSM bridge
```

The evaluator prefers `SensorFrameSnapshot`. If only legacy telemetry exists, it falls back to a legacy-derived degraded/explicit mode.

## States

```text
TRUSTED      fresh live readings, no hard conflicts
DEGRADED     missing/stale/config-only/low-confidence/lower-layer degraded
CONFLICTING  incompatible sensor evidence
LOTTERY      anomaly/radiation environment makes valid readings unreliable
BLIND        external sensing unavailable; body-only telemetry remains
```

## Invariants

```text
explicit trusted must not override computed hard conflict/degradation
CONFIG_ONLY does not become live OK
MISSING does not become trusted
STALE/DEAD does not become fresh
operator override is local UI posture, not runtime truth
hidden ObjectiveWorld truth is not consumed by SensorTrustSnapshot
```

## q-sim telemetry

`QSimService._build_telemetry_payload()` now publishes:

```text
telemetry.sensor_runtime
telemetry.sensor_observation
telemetry.sensor_trust
```

`telemetry.sensor_trust` includes lineage fields:

```text
world_tick_id
world_snapshot_id
source_world_snapshot_id
sim_time_s
sensor_frame_id
observation_frame_id
```

## ORION compatibility

`orion_v.sensor_trust_model.build_sensor_trust_snapshot()` delegates to `qiki.shared.sensor_trust` first. Its older local heuristic remains as defensive fallback only.

## Non-goals

This patch does not implement sensor lottery distortion, sensor spoofing, occlusion/FOV, hardware integrity as a full shared contract, or MainFSM signal bridge. Those are later patches.
