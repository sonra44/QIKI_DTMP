"""Radar backend interfaces and shared scene types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from qiki.services.q_core_agent.core.radar_view_state import RadarViewState

@dataclass(frozen=True)
class RadarPoint:
    x: float
    y: float
    z: float
    vr_mps: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RadarScene:
    ok: bool
    reason: str
    truth_state: str
    is_fallback: bool
    points: list[RadarPoint] = field(default_factory=list)
    trails: dict[str, list[RadarPoint]] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderOutput:
    backend: str
    lines: list[str]
    used_runtime_fallback: bool = False
    plan: Any = None
    stats: Any = None


class RadarBackend(ABC):
    name: str

    @abstractmethod
    def is_supported(self) -> bool:
        """Return True only when backend is confidently supported in current terminal."""

    @abstractmethod
    def render(self, scene: RadarScene, *, view_state: RadarViewState, color: bool, render_plan: Any = None) -> RenderOutput:
        """Render radar pane for provided scene and projection view."""
