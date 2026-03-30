"""Guard table evaluation for radar tracks and FSM integration."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable, List, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

from qiki.shared.models.radar import (
    FriendFoeEnum,
    RadarTrackModel,
    RadarTrackStatusEnum,
    TransponderModeEnum,
)


DEFAULT_RESOURCE_PACKAGE = "qiki.resources.radar"
DEFAULT_RESOURCE_NAME = "guard_rules.yaml"

_SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


class GuardEvaluationResult(BaseModel):
    """Concrete result of a guard rule applied to a radar track."""

    rule_id: str
    severity: str
    fsm_event: str
    message: str
    track_id: str
    range_m: float
    quality: float
    iff: FriendFoeEnum
    transponder_on: bool
    transponder_mode: TransponderModeEnum

    @property
    def severity_weight(self) -> int:
        return _SEVERITY_ORDER.get(self.severity, 0)


class GuardRule(BaseModel):
    """Single guard rule describing conditions and resulting FSM trigger."""

    rule_id: str = Field(alias="id")
    title: Optional[str] = None
    description: str
    action_required: Optional[str] = None
    severity: str = Field(pattern="^(info|warning|critical)$")
    fsm_event: str
    iff: Optional[FriendFoeEnum] = None
    require_transponder_on: Optional[bool] = None
    allowed_transponder_modes: Optional[List[TransponderModeEnum]] = None
    min_range_m: float = 0.0
    max_range_m: Optional[float] = None
    min_quality: float = 0.0
    max_radial_velocity_mps: Optional[float] = None
    # Anti-flap / trust controls (P0): optional and backward-compatible.
    # - min_duration_s: condition must hold continuously for this long before the first edge alert.
    # - cooldown_s: suppress re-entry alerts for this long after the last published edge.
    # - hysteresis_m: expand range bounds while ACTIVE to prevent boundary flapping.
    min_duration_s: float = 0.0
    cooldown_s: float = 0.0
    hysteresis_m: float = 0.0

    @model_validator(mode="after")
    def _validate_ranges(self) -> "GuardRule":
        if self.max_range_m is not None and self.max_range_m <= self.min_range_m:
            raise ValueError("max_range_m must be greater than min_range_m")
        if not 0.0 <= self.min_quality <= 1.0:
            raise ValueError("min_quality must be in [0,1]")
        if self.min_duration_s < 0.0:
            raise ValueError("min_duration_s must be >= 0")
        if self.cooldown_s < 0.0:
            raise ValueError("cooldown_s must be >= 0")
        if self.hysteresis_m < 0.0:
            raise ValueError("hysteresis_m must be >= 0")
        return self

    def matches(self, track: RadarTrackModel, *, active: bool = False, hysteresis_m: Optional[float] = None) -> bool:
        # P0 trust: guard rules operate on stabilized tracks only.
        # NEW/UNSPECIFIED tracks are too noisy and cause operator-facing flapping.
        if track.status not in {
            RadarTrackStatusEnum.TRACKED,
            RadarTrackStatusEnum.COASTING,
        }:
            return False

        if self.iff is not None and track.iff != self.iff:
            return False

        if self.require_transponder_on is True and not track.transponder_on:
            return False
        if self.require_transponder_on is False and track.transponder_on:
            return False

        if self.allowed_transponder_modes and track.transponder_mode not in self.allowed_transponder_modes:
            return False

        h = float(self.hysteresis_m if hysteresis_m is None else hysteresis_m)
        if active and h:
            min_range = float(self.min_range_m) - h
            max_range = (float(self.max_range_m) + h) if self.max_range_m is not None else None
        else:
            min_range = float(self.min_range_m)
            max_range = float(self.max_range_m) if self.max_range_m is not None else None

        if track.range_m < min_range:
            return False
        if max_range is not None and track.range_m > max_range:
            return False

        if track.quality < self.min_quality:
            return False

        if self.max_radial_velocity_mps is not None and abs(track.vr_mps) > self.max_radial_velocity_mps:
            return False

        return True

    def build_result(self, track: RadarTrackModel) -> GuardEvaluationResult:
        return GuardEvaluationResult(
            rule_id=self.rule_id,
            severity=self.severity,
            fsm_event=self.fsm_event,
            message=self.description,
            track_id=str(track.track_id),
            range_m=track.range_m,
            quality=track.quality,
            iff=track.iff,
            transponder_on=track.transponder_on,
            transponder_mode=track.transponder_mode,
        )

    def evaluate(self, track: RadarTrackModel) -> Optional[GuardEvaluationResult]:
        if not self.matches(track, active=False, hysteresis_m=0.0):
            return None
        return self.build_result(track)


class GuardTable(BaseModel):
    """Collection of guard rules loaded from configuration."""

    schema_version: int
    rules: List[GuardRule] = Field(default_factory=list)

    def evaluate_track(self, track: RadarTrackModel) -> List[GuardEvaluationResult]:
        return [result for rule in self.rules if (result := rule.evaluate(track))]

    def evaluate_tracks(self, tracks: Iterable[RadarTrackModel]) -> List[GuardEvaluationResult]:
        results: List[GuardEvaluationResult] = []
        for track in tracks:
            results.extend(self.evaluate_track(track))
        return results


@dataclass
class GuardTableLoader:
    """Loads guard table configuration from YAML files."""

    path: Optional[Path] = None
    resource_package: str = DEFAULT_RESOURCE_PACKAGE
    resource_name: str = DEFAULT_RESOURCE_NAME

    def _load_from_path(self, path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"Guard table configuration not found: {path}")

        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def _load_from_resource(self) -> dict:
        guard_resource = resources.files(self.resource_package).joinpath(self.resource_name)
        if not guard_resource.is_file():  # type: ignore[attr-defined]
            raise FileNotFoundError(f"Guard table resource not found: {self.resource_package}:{self.resource_name}")

        with guard_resource.open("r", encoding="utf-8") as handle:  # type: ignore[attr-defined]
            return yaml.safe_load(handle)

    def load(self) -> GuardTable:
        raw: dict
        if self.path is not None:
            raw = self._load_from_path(self.path)
        else:
            raw = self._load_from_resource()

        return GuardTable.model_validate(raw)


def load_guard_table(path: Optional[Path] = None) -> GuardTable:
    """Convenience wrapper for loading guard table from default path."""

    loader = GuardTableLoader(path=path)
    return loader.load()
