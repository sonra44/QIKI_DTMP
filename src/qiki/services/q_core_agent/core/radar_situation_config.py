"""Shared configuration for radar situation lifecycle and operator controls."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RadarSituationRuntimeConfig:
    confirm_frames: int
    cooldown_s: float
    lost_contact_window_s: float
    auto_resolve_after_lost_s: float
    ack_snooze_s: float

    @classmethod
    def from_env(cls) -> "RadarSituationRuntimeConfig":
        return cls(
            confirm_frames=max(1, _env_int("SITUATION_CONFIRM_FRAMES", 3)),
            cooldown_s=max(0.0, _env_float("SITUATION_COOLDOWN_S", 5.0)),
            lost_contact_window_s=max(0.0, _env_float("LOST_CONTACT_WINDOW_S", 2.0)),
            auto_resolve_after_lost_s=max(0.0, _env_float("SITUATION_AUTO_RESOLVE_AFTER_LOST_S", 2.0)),
            ack_snooze_s=max(0.0, _env_float("SITUATION_ACK_S", 10.0)),
        )


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

