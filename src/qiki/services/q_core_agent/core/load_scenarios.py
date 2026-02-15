"""Deterministic load scenarios for end-to-end radar stress harness."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .radar_ingestion import Observation


@dataclass(frozen=True)
class ScenarioFrame:
    ts: float
    observations: tuple[Observation, ...]
    truth_state: str = "OK"
    reason: str = "OK"
    is_fallback: bool = False


@dataclass(frozen=True)
class ScenarioConfig:
    seed: int = 7
    duration_s: float = 10.0
    target_count: int = 1
    dt_s: float = 0.1


def available_scenarios() -> tuple[str, ...]:
    return (
        "single_target_stable",
        "multi_target_300",
        "fusion_conflict",
        "sensor_dropout",
        "oscillation_threshold",
        "high_write_sqlite",
        "replay_long_trace",
    )


def build_scenario(name: str, config: ScenarioConfig) -> list[ScenarioFrame]:
    scenario = str(name or "").strip().lower()
    if scenario not in set(available_scenarios()):
        raise ValueError(f"unknown scenario: {name}")
    if scenario == "single_target_stable":
        return _single_target_stable(config)
    if scenario == "multi_target_300":
        return _multi_target(config)
    if scenario == "fusion_conflict":
        return _fusion_conflict(config)
    if scenario == "sensor_dropout":
        return _sensor_dropout(config)
    if scenario == "oscillation_threshold":
        return _oscillation_threshold(config)
    if scenario == "high_write_sqlite":
        return _high_write_sqlite(config)
    return _replay_long_trace(config)


def _steps(config: ScenarioConfig) -> int:
    safe_dt = max(0.01, float(config.dt_s))
    safe_duration = max(0.1, float(config.duration_s))
    return max(1, int(round(safe_duration / safe_dt)))


def _track_obs(
    *,
    source_id: str,
    track_id: str,
    ts: float,
    x: float,
    y: float,
    vx: float,
    vy: float,
    quality: float,
) -> Observation:
    return Observation(
        source_id=source_id,
        t=float(ts),
        track_key=track_id,
        pos_xy=(float(x), float(y)),
        vel_xy=(float(vx), float(vy)),
        quality=max(0.0, min(1.0, float(quality))),
        metadata={"target_id": track_id},
    )


def _single_target_stable(config: ScenarioConfig) -> list[ScenarioFrame]:
    frames: list[ScenarioFrame] = []
    dt = max(0.01, float(config.dt_s))
    for idx in range(_steps(config)):
        ts = idx * dt
        obs = _track_obs(
            source_id="radar-a",
            track_id="stable-1",
            ts=ts,
            x=120.0 - (idx * 0.25),
            y=15.0,
            vx=-2.5,
            vy=0.0,
            quality=0.92,
        )
        frames.append(ScenarioFrame(ts=ts, observations=(obs,)))
    return frames


def _multi_target(config: ScenarioConfig) -> list[ScenarioFrame]:
    frames: list[ScenarioFrame] = []
    dt = max(0.01, float(config.dt_s))
    target_count = max(1, int(config.target_count))
    seed = int(config.seed)
    for idx in range(_steps(config)):
        ts = idx * dt
        observations: list[Observation] = []
        for target_idx in range(target_count):
            phase = ((target_idx * 17) + seed) * 0.013
            angle = phase + (idx * 0.02)
            radius = 300.0 + ((target_idx % 9) * 12.0)
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            vx = -math.sin(angle) * 2.0
            vy = math.cos(angle) * 2.0
            quality = 0.7 + ((target_idx % 5) * 0.05)
            observations.append(
                _track_obs(
                    source_id="radar-a",
                    track_id=f"mt-{target_idx}",
                    ts=ts,
                    x=x,
                    y=y,
                    vx=vx,
                    vy=vy,
                    quality=min(0.99, quality),
                )
            )
        frames.append(ScenarioFrame(ts=ts, observations=tuple(observations)))
    return frames


def _fusion_conflict(config: ScenarioConfig) -> list[ScenarioFrame]:
    frames: list[ScenarioFrame] = []
    dt = max(0.01, float(config.dt_s))
    rng = random.Random(int(config.seed))
    for idx in range(_steps(config)):
        ts = idx * dt
        x = 180.0 - (idx * 0.8)
        y = 40.0
        drift = 1.0 if idx % 7 else 90.0
        jitter = (rng.random() - 0.5) * 0.6
        obs = (
            _track_obs(
                source_id="radar-a",
                track_id="fusion-x",
                ts=ts,
                x=x,
                y=y,
                vx=-8.0,
                vy=0.0,
                quality=0.88,
            ),
            _track_obs(
                source_id="radar-b",
                track_id="fusion-y",
                ts=ts,
                x=x + drift + jitter,
                y=y + jitter,
                vx=-8.0,
                vy=0.0,
                quality=0.82,
            ),
        )
        frames.append(ScenarioFrame(ts=ts, observations=obs))
    return frames


def _sensor_dropout(config: ScenarioConfig) -> list[ScenarioFrame]:
    frames: list[ScenarioFrame] = []
    dt = max(0.01, float(config.dt_s))
    for idx in range(_steps(config)):
        ts = idx * dt
        if idx % 9 in {5, 6}:
            frames.append(ScenarioFrame(ts=ts, observations=(), truth_state="NO_DATA", reason="NO_DATA"))
            continue
        obs = _track_obs(
            source_id="radar-a",
            track_id="drop-1",
            ts=ts,
            x=90.0 - (idx * 0.3),
            y=5.0,
            vx=-3.0,
            vy=0.0,
            quality=0.85,
        )
        frames.append(ScenarioFrame(ts=ts, observations=(obs,)))
    return frames


def _oscillation_threshold(config: ScenarioConfig) -> list[ScenarioFrame]:
    frames: list[ScenarioFrame] = []
    dt = max(0.01, float(config.dt_s))
    rng = random.Random(int(config.seed))
    for idx in range(_steps(config)):
        ts = idx * dt
        distance = 155.0 + ((-1) ** idx) * (2.0 + (rng.random() * 2.0))
        vy = 0.6 if idx % 2 == 0 else -0.6
        obs = _track_obs(
            source_id="radar-a",
            track_id="osc-1",
            ts=ts,
            x=distance,
            y=0.0,
            vx=-4.8,
            vy=vy,
            quality=0.9,
        )
        frames.append(ScenarioFrame(ts=ts, observations=(obs,)))
    return frames


def _high_write_sqlite(config: ScenarioConfig) -> list[ScenarioFrame]:
    cfg = ScenarioConfig(
        seed=config.seed,
        duration_s=config.duration_s,
        target_count=max(120, int(config.target_count)),
        dt_s=min(0.05, max(0.02, float(config.dt_s))),
    )
    frames = _multi_target(cfg)
    expanded: list[ScenarioFrame] = []
    for frame in frames:
        dual: list[Observation] = list(frame.observations)
        for obs in frame.observations:
            dual.append(
                _track_obs(
                    source_id="radar-b",
                    track_id=f"b-{obs.track_key}",
                    ts=frame.ts,
                    x=obs.pos_xy[0] + 1.0,
                    y=obs.pos_xy[1] - 1.0,
                    vx=obs.vel_xy[0] if obs.vel_xy else 0.0,
                    vy=obs.vel_xy[1] if obs.vel_xy else 0.0,
                    quality=max(0.0, min(1.0, obs.quality - 0.02)),
                )
            )
        expanded.append(ScenarioFrame(ts=frame.ts, observations=tuple(dual)))
    return expanded


def _replay_long_trace(config: ScenarioConfig) -> list[ScenarioFrame]:
    cfg = ScenarioConfig(
        seed=config.seed,
        duration_s=max(float(config.duration_s), 45.0),
        target_count=max(12, min(64, int(config.target_count))),
        dt_s=max(0.05, float(config.dt_s)),
    )
    return _multi_target(cfg)
