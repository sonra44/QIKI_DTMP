"""Deterministic operator-training scenarios for radar pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .radar_ingestion import Observation


@dataclass(frozen=True)
class TrainingExpectedAction:
    action_type: str
    description: str
    trigger_checkpoint: str
    deadline_s: float = 4.0
    required: bool = True


@dataclass(frozen=True)
class TrainingFrame:
    ts: float
    observations: tuple[Observation, ...]
    truth_state: str = "OK"
    reason: str = "OK"
    is_fallback: bool = False
    hint: str = ""
    checkpoint: str | None = None


@dataclass(frozen=True)
class TrainingScenario:
    name: str
    title: str
    objective: str
    duration_s: float
    seed: int
    frames: tuple[TrainingFrame, ...]
    expected_actions: tuple[TrainingExpectedAction, ...]
    expected_outcome: str


def available_training_scenarios() -> tuple[str, ...]:
    return (
        "cpa_warning",
        "sensor_dropout",
        "fusion_conflict",
        "policy_degradation",
    )


def build_training_scenario(name: str, *, seed: int = 7, dt_s: float = 0.2) -> TrainingScenario:
    scenario = str(name or "").strip().lower()
    if scenario not in set(available_training_scenarios()):
        raise ValueError(f"unknown training scenario: {name!r}")
    if scenario == "cpa_warning":
        return _cpa_warning(seed=seed, dt_s=dt_s)
    if scenario == "sensor_dropout":
        return _sensor_dropout(seed=seed, dt_s=dt_s)
    if scenario == "fusion_conflict":
        return _fusion_conflict(seed=seed, dt_s=dt_s)
    return _policy_degradation(seed=seed, dt_s=dt_s)


def _obs(
    *,
    source_id: str,
    track_id: str,
    ts: float,
    x: float,
    y: float,
    vx: float,
    vy: float,
    quality: float,
    metadata: dict | None = None,
) -> Observation:
    return Observation(
        source_id=source_id,
        t=float(ts),
        track_key=track_id,
        pos_xy=(float(x), float(y)),
        vel_xy=(float(vx), float(vy)),
        quality=max(0.0, min(1.0, float(quality))),
        metadata=dict(metadata or {}),
    )


def _cpa_warning(*, seed: int, dt_s: float) -> TrainingScenario:
    frames: list[TrainingFrame] = []
    ts = 0.0
    for idx in range(35):
        frames.append(
            TrainingFrame(
                ts=ts,
                observations=(
                    _obs(
                        source_id="radar-a",
                        track_id="cpa-target",
                        ts=ts,
                        x=180.0 - (idx * 2.2),
                        y=0.0,
                        vx=-11.0,
                        vy=0.0,
                        quality=0.92,
                    ),
                ),
                hint="Track is closing fast; inspect and acknowledge alert.",
                checkpoint="CPA_ALERT" if idx == 8 else None,
            )
        )
        ts += max(0.05, dt_s)
    return TrainingScenario(
        name="cpa_warning",
        title="CPA Warning",
        objective="Detect CPA risk and acknowledge the selected alert.",
        duration_s=float(ts),
        seed=seed,
        frames=tuple(frames),
        expected_actions=(
            TrainingExpectedAction(
                action_type="ALERT_ACK",
                description="Acknowledge the selected CPA alert",
                trigger_checkpoint="CPA_ALERT",
                deadline_s=4.0,
            ),
        ),
        expected_outcome="Operator acknowledges critical CPA alert quickly.",
    )


def _sensor_dropout(*, seed: int, dt_s: float) -> TrainingScenario:
    frames: list[TrainingFrame] = []
    ts = 0.0
    for idx in range(30):
        if 11 <= idx <= 16:
            frames.append(
                TrainingFrame(
                    ts=ts,
                    observations=(),
                    truth_state="NO_DATA",
                    reason="NO_DATA",
                    hint="Sensor feed dropped. Verify NO_DATA state in inspector.",
                    checkpoint="NO_DATA_START" if idx == 11 else None,
                )
            )
        else:
            frames.append(
                TrainingFrame(
                    ts=ts,
                    observations=(
                        _obs(
                            source_id="radar-a",
                            track_id="drop-track",
                            ts=ts,
                            x=90.0 - (idx * 1.2),
                            y=7.0,
                            vx=-3.5,
                            vy=0.0,
                            quality=0.88,
                        ),
                    ),
                )
            )
        ts += max(0.05, dt_s)
    return TrainingScenario(
        name="sensor_dropout",
        title="Sensor Dropout",
        objective="Recognize NO_DATA immediately and open inspector.",
        duration_s=float(ts),
        seed=seed,
        frames=tuple(frames),
        expected_actions=(
            TrainingExpectedAction(
                action_type="TOGGLE_INSPECTOR",
                description="Open inspector to confirm NO_DATA reason",
                trigger_checkpoint="NO_DATA_START",
                deadline_s=4.0,
            ),
        ),
        expected_outcome="Operator confirms NO_DATA state instead of trusting stale picture.",
    )


def _fusion_conflict(*, seed: int, dt_s: float) -> TrainingScenario:
    rng = random.Random(int(seed))
    frames: list[TrainingFrame] = []
    ts = 0.0
    for idx in range(35):
        drift = 4.0 + (rng.random() * 2.0)
        jitter = (rng.random() - 0.5) * 0.5
        frames.append(
            TrainingFrame(
                ts=ts,
                observations=(
                    _obs(
                        source_id="radar-a",
                        track_id="fusion-a",
                        ts=ts,
                        x=140.0 - (idx * 0.9),
                        y=25.0,
                        vx=-4.5,
                        vy=0.0,
                        quality=0.9,
                    ),
                    _obs(
                        source_id="radar-b",
                        track_id="fusion-b",
                        ts=ts,
                        x=140.0 - (idx * 0.9) + drift + jitter,
                        y=25.0 + jitter,
                        vx=-4.5,
                        vy=0.0,
                        quality=0.8,
                    ),
                ),
                hint="Fusion conflict likely; focus selected target and inspect trust.",
                checkpoint="FUSION_CONFLICT" if idx == 10 else None,
            )
        )
        ts += max(0.05, dt_s)
    return TrainingScenario(
        name="fusion_conflict",
        title="Fusion Conflict",
        objective="Focus selected target and inspect conflict/trust signals.",
        duration_s=float(ts),
        seed=seed,
        frames=tuple(frames),
        expected_actions=(
            TrainingExpectedAction(
                action_type="ALERT_FOCUS",
                description="Focus selected alert target",
                trigger_checkpoint="FUSION_CONFLICT",
                deadline_s=5.0,
            ),
        ),
        expected_outcome="Operator focuses contested target and checks trust before decision.",
    )


def _policy_degradation(*, seed: int, dt_s: float) -> TrainingScenario:
    rng = random.Random(int(seed))
    frames: list[TrainingFrame] = []
    ts = 0.0
    target_count = 120
    for idx in range(22):
        observations: list[Observation] = []
        for target_idx in range(target_count):
            angle = (target_idx * 0.21) + (idx * 0.03)
            radius = 240.0 + ((target_idx % 11) * 9.0)
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            observations.append(
                _obs(
                    source_id="radar-a",
                    track_id=f"crowd-{target_idx}",
                    ts=ts,
                    x=x,
                    y=y,
                    vx=-math.sin(angle) * 2.0,
                    vy=math.cos(angle) * 2.0,
                    quality=0.72 + ((target_idx % 5) * 0.04) - (rng.random() * 0.01),
                )
            )
        frames.append(
            TrainingFrame(
                ts=ts,
                observations=tuple(observations),
                hint="Load spike: switch policy profile or accept degradation.",
                checkpoint="POLICY_DEGRADE" if idx == 6 else None,
            )
        )
        ts += max(0.05, dt_s)
    return TrainingScenario(
        name="policy_degradation",
        title="Policy Degradation",
        objective="React to LOD degradation by switching policy profile.",
        duration_s=float(ts),
        seed=seed,
        frames=tuple(frames),
        expected_actions=(
            TrainingExpectedAction(
                action_type="POLICY_PROFILE_SWITCH",
                description="Switch policy profile during overload",
                trigger_checkpoint="POLICY_DEGRADE",
                deadline_s=6.0,
            ),
        ),
        expected_outcome="Operator adapts profile under load while preserving readability.",
    )
