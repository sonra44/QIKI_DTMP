from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence

from qiki.shared.sensor_runtime import (
    SensorFrameSnapshot,
    SensorFreshness,
    SensorReadingSnapshot,
    SensorSourceKind,
    SensorStatus,
)


class SensorTrustState(StrEnum):
    TRUSTED = "trusted"
    DEGRADED = "degraded"
    CONFLICTING = "conflicting"
    LOTTERY = "lottery"
    BLIND = "blind"


class SensorTrustOverride(StrEnum):
    AUTO = "auto"
    TRUSTED = "trusted"
    DEGRADED = "degraded"
    CONFLICTING = "conflicting"
    LOTTERY = "lottery"
    BLIND = "blind"


class SensorTrustReason(StrEnum):
    RUNTIME_READINGS_OK = "runtime_readings_ok"
    EXPLICIT_RUNTIME_STATE = "explicit_runtime_state"
    MISSING_SENSOR_FRAME = "missing_sensor_frame"
    MISSING_CRITICAL_SENSOR = "missing_critical_sensor"
    CONFIG_ONLY_SENSOR = "config_only_sensor"
    STALE_SENSOR = "stale_sensor"
    DEAD_SENSOR = "dead_sensor"
    LOW_CONFIDENCE = "low_confidence"
    BAD_STATUS = "bad_status"
    SENSOR_CONFLICT = "sensor_conflict"
    LOTTERY_ENVIRONMENT = "lottery_environment"
    BLIND_EXTERNAL_CONTOUR = "blind_external_contour"
    LOWER_LAYER_HEALTH = "lower_layer_health"
    OPERATOR_LOCAL_OVERRIDE = "operator_local_override"


_STATE_RU: dict[SensorTrustState, str] = {
    SensorTrustState.TRUSTED: "сенсоры достоверны",
    SensorTrustState.DEGRADED: "сенсоры деградируют",
    SensorTrustState.CONFLICTING: "сенсоры противоречат",
    SensorTrustState.LOTTERY: "телеметрия-лотерея",
    SensorTrustState.BLIND: "слепой режим",
}

_STATE_SEVERITY: dict[SensorTrustState, str] = {
    SensorTrustState.TRUSTED: "normal",
    SensorTrustState.DEGRADED: "warning",
    SensorTrustState.CONFLICTING: "warning",
    SensorTrustState.LOTTERY: "critical",
    SensorTrustState.BLIND: "warning",
}

_STATE_F2_SEVERITY: dict[SensorTrustState, str] = {
    SensorTrustState.TRUSTED: "ok",
    SensorTrustState.DEGRADED: "warn",
    SensorTrustState.CONFLICTING: "warn",
    SensorTrustState.LOTTERY: "crit",
    SensorTrustState.BLIND: "warn",
}

_STATE_NEXT_STEP: dict[SensorTrustState, str] = {
    SensorTrustState.TRUSTED: "можно использовать сенсорную картину, сверяя свежесть данных",
    SensorTrustState.DEGRADED: "открыть F2/F3 и проверить, какие сенсоры потеряли качество",
    SensorTrustState.CONFLICTING: "сравнить evidence в F3; не подтверждать рискованные действия без проверки",
    SensorTrustState.LOTTERY: "считать внешнюю картину недостоверной; перейти к корпусной телеметрии и ручному подтверждению",
    SensorTrustState.BLIND: "не полагаться на внешнее восприятие; использовать body-only телеметрию и короткие шаги",
}

_STATE_RANK: dict[SensorTrustState, int] = {
    SensorTrustState.TRUSTED: 0,
    SensorTrustState.DEGRADED: 1,
    SensorTrustState.BLIND: 2,
    SensorTrustState.CONFLICTING: 3,
    SensorTrustState.LOTTERY: 4,
}

_STATE_CONFIDENCE_FALLBACK: dict[SensorTrustState, float] = {
    SensorTrustState.TRUSTED: 0.84,
    SensorTrustState.DEGRADED: 0.52,
    SensorTrustState.BLIND: 0.40,
    SensorTrustState.CONFLICTING: 0.34,
    SensorTrustState.LOTTERY: 0.18,
}

_EXPLICIT_STATE_ALIASES: dict[str, SensorTrustState] = {
    "trusted": SensorTrustState.TRUSTED,
    "healthy": SensorTrustState.TRUSTED,
    "ok": SensorTrustState.TRUSTED,
    "normal": SensorTrustState.TRUSTED,
    "nominal": SensorTrustState.TRUSTED,
    "degraded": SensorTrustState.DEGRADED,
    "degrade": SensorTrustState.DEGRADED,
    "warn": SensorTrustState.DEGRADED,
    "warning": SensorTrustState.DEGRADED,
    "conflicting": SensorTrustState.CONFLICTING,
    "conflict": SensorTrustState.CONFLICTING,
    "contradiction": SensorTrustState.CONFLICTING,
    "contradictory": SensorTrustState.CONFLICTING,
    "lottery": SensorTrustState.LOTTERY,
    "chaos": SensorTrustState.LOTTERY,
    "uncertain": SensorTrustState.LOTTERY,
    "uncertainty": SensorTrustState.LOTTERY,
    "anomaly": SensorTrustState.LOTTERY,
    "blind": SensorTrustState.BLIND,
    "body_only": SensorTrustState.BLIND,
    "body-only": SensorTrustState.BLIND,
    "body telemetry only": SensorTrustState.BLIND,
    "external_off": SensorTrustState.BLIND,
}

_DEFAULT_REQUIRED_SENSOR_IDS = (
    "imu_main",
    "sensor_radiation",
    "sensor_proximity",
    "sensor_power",
    "sensor_thermal",
)

_EXTERNAL_SENSOR_IDS = {
    "sensor_proximity",
    "radar_360",
    "lidar",
    "star_tracker",
    "magnetometer",
}

_BAD_STATUSES = {
    SensorStatus.FAULT,
    SensorStatus.MISSING,
    SensorStatus.UNKNOWN,
}

_DEGRADED_STATUSES = {
    SensorStatus.WARN,
    SensorStatus.DEGRADED,
}


@dataclass(frozen=True, slots=True)
class SensorTrustEvidence:
    reason: SensorTrustReason | str
    message: str
    sensor_id: str | None = None
    source_path: str = ""
    world_snapshot_id: str | None = None
    observation_id: str | None = None
    severity: str = "info"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", normalize_sensor_trust_reason(self.reason))
        object.__setattr__(self, "message", str(self.message or "").strip())
        object.__setattr__(self, "sensor_id", _str_or_none(self.sensor_id))
        object.__setattr__(self, "source_path", str(self.source_path or ""))
        object.__setattr__(self, "world_snapshot_id", _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "observation_id", _str_or_none(self.observation_id))
        object.__setattr__(self, "severity", str(self.severity or "info"))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_mapping(self) -> dict[str, Any]:
        out = {
            "reason": self.reason.value,
            "message": self.message,
            "severity": self.severity,
            "source_path": self.source_path,
        }
        if self.sensor_id is not None:
            out["sensor_id"] = self.sensor_id
        if self.world_snapshot_id is not None:
            out["world_snapshot_id"] = self.world_snapshot_id
        if self.observation_id is not None:
            out["observation_id"] = self.observation_id
        if self.metadata:
            out["metadata"] = dict(self.metadata)
        return out

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SensorTrustEvidence":
        return cls(
            reason=data.get("reason") or SensorTrustReason.RUNTIME_READINGS_OK,
            message=str(data.get("message") or ""),
            sensor_id=data.get("sensor_id"),
            source_path=str(data.get("source_path") or ""),
            world_snapshot_id=data.get("world_snapshot_id"),
            observation_id=data.get("observation_id"),
            severity=str(data.get("severity") or "info"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class SensorTrustDecision:
    state: SensorTrustState | str
    confidence: float
    reason: SensorTrustReason | str
    allowed_for_navigation: bool
    allowed_for_high_risk_action: bool
    recommended_mainfsm_sensor_trust: str
    recommended_operator_posture: str

    def __post_init__(self) -> None:
        state = normalize_sensor_trust_state(self.state)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "confidence", _clamp01(self.confidence))
        object.__setattr__(self, "reason", normalize_sensor_trust_reason(self.reason))
        object.__setattr__(self, "allowed_for_navigation", bool(self.allowed_for_navigation))
        object.__setattr__(self, "allowed_for_high_risk_action", bool(self.allowed_for_high_risk_action))
        object.__setattr__(self, "recommended_mainfsm_sensor_trust", str(self.recommended_mainfsm_sensor_trust or state.value).upper())
        object.__setattr__(self, "recommended_operator_posture", str(self.recommended_operator_posture or state.value))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "confidence": self.confidence,
            "reason": self.reason.value,
            "allowed_for_navigation": self.allowed_for_navigation,
            "allowed_for_high_risk_action": self.allowed_for_high_risk_action,
            "recommended_mainfsm_sensor_trust": self.recommended_mainfsm_sensor_trust,
            "recommended_operator_posture": self.recommended_operator_posture,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SensorTrustDecision":
        state = normalize_sensor_trust_state(data.get("state"))
        return cls(
            state=state,
            confidence=data.get("confidence") or _STATE_CONFIDENCE_FALLBACK[state],
            reason=data.get("reason") or SensorTrustReason.RUNTIME_READINGS_OK,
            allowed_for_navigation=bool(data.get("allowed_for_navigation", state in {SensorTrustState.TRUSTED, SensorTrustState.DEGRADED})),
            allowed_for_high_risk_action=bool(data.get("allowed_for_high_risk_action", state is SensorTrustState.TRUSTED)),
            recommended_mainfsm_sensor_trust=str(data.get("recommended_mainfsm_sensor_trust") or state.value).upper(),
            recommended_operator_posture=str(data.get("recommended_operator_posture") or state.value),
        )


@dataclass(frozen=True, slots=True)
class SensorTrustSnapshot:
    state: SensorTrustState | str
    confidence: float
    reason: SensorTrustReason | str
    reason_ru: str
    evidence: tuple[str, ...]
    source_path: str = "qiki.shared.sensor_trust"
    world_tick_id: str | None = None
    world_snapshot_id: str | None = None
    source_world_snapshot_id: str | None = None
    sim_time_s: float | None = None
    sensor_frame_id: str | None = None
    observation_frame_id: str | None = None
    input_sensor_ids: tuple[str, ...] = ()
    input_observation_ids: tuple[str, ...] = ()
    freshness_summary: Mapping[str, str] = field(default_factory=dict)
    missing_critical_sensors: tuple[str, ...] = ()
    degraded_sensors: tuple[str, ...] = ()
    conflict_markers: tuple[str, ...] = ()
    lower_layer_health: Mapping[str, Any] = field(default_factory=dict)
    evidence_items: tuple[SensorTrustEvidence, ...] = ()
    decision: SensorTrustDecision | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        state = normalize_sensor_trust_state(self.state)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "confidence", _clamp01(self.confidence))
        object.__setattr__(self, "reason", normalize_sensor_trust_reason(self.reason))
        object.__setattr__(self, "reason_ru", str(self.reason_ru or _reason_ru_for_state(state)))
        object.__setattr__(self, "evidence", tuple(str(item).strip() for item in (self.evidence or ()) if str(item).strip()))
        object.__setattr__(self, "source_path", str(self.source_path or "qiki.shared.sensor_trust"))
        object.__setattr__(self, "world_tick_id", _str_or_none(self.world_tick_id))
        object.__setattr__(self, "world_snapshot_id", _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "source_world_snapshot_id", _str_or_none(self.source_world_snapshot_id) or _str_or_none(self.world_snapshot_id))
        object.__setattr__(self, "sim_time_s", _finite_float_or_none(self.sim_time_s))
        object.__setattr__(self, "sensor_frame_id", _str_or_none(self.sensor_frame_id))
        object.__setattr__(self, "observation_frame_id", _str_or_none(self.observation_frame_id))
        object.__setattr__(self, "input_sensor_ids", tuple(str(item) for item in (self.input_sensor_ids or ()) if str(item).strip()))
        object.__setattr__(self, "input_observation_ids", tuple(str(item) for item in (self.input_observation_ids or ()) if str(item).strip()))
        object.__setattr__(self, "freshness_summary", {str(k): str(v) for k, v in dict(self.freshness_summary or {}).items()})
        object.__setattr__(self, "missing_critical_sensors", tuple(str(item) for item in (self.missing_critical_sensors or ()) if str(item).strip()))
        object.__setattr__(self, "degraded_sensors", tuple(str(item) for item in (self.degraded_sensors or ()) if str(item).strip()))
        object.__setattr__(self, "conflict_markers", tuple(str(item) for item in (self.conflict_markers or ()) if str(item).strip()))
        object.__setattr__(self, "lower_layer_health", dict(self.lower_layer_health or {}))
        object.__setattr__(self, "evidence_items", tuple(self.evidence_items or ()))
        if self.decision is None:
            object.__setattr__(self, "decision", _decision_for_state(state, self.confidence, self.reason))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def label_ru(self) -> str:
        return _STATE_RU[self.state]

    @property
    def severity(self) -> str:
        return _STATE_SEVERITY[self.state]

    @property
    def f2_severity(self) -> str:
        return _STATE_F2_SEVERITY[self.state]

    @property
    def next_step_ru(self) -> str:
        return _STATE_NEXT_STEP[self.state]

    @property
    def truth_badge(self) -> str:
        return f"[DERIVED {self.source_path}; sensor confidence, not runtime truth mutation]"

    @property
    def short_chip(self) -> str:
        return f"{self.state.value} {self.confidence:.2f}"

    @property
    def status_key(self) -> str:
        return self.state.value

    @property
    def operator_effect_ru(self) -> str:
        return self.reason_ru

    @property
    def constrains_mainfsm(self) -> bool:
        return self.state in {SensorTrustState.CONFLICTING, SensorTrustState.LOTTERY, SensorTrustState.BLIND}

    def to_mapping(self) -> dict[str, Any]:
        out = {
            "schema_version": 1,
            "state": self.state.value,
            "confidence": self.confidence,
            "reason": self.reason.value,
            "reason_ru": self.reason_ru,
            "label_ru": self.label_ru,
            "severity": self.severity,
            "f2_severity": self.f2_severity,
            "next_step_ru": self.next_step_ru,
            "source_path": self.source_path,
            "evidence": list(self.evidence),
            "input_sensor_ids": list(self.input_sensor_ids),
            "input_observation_ids": list(self.input_observation_ids),
            "freshness_summary": dict(self.freshness_summary),
            "missing_critical_sensors": list(self.missing_critical_sensors),
            "degraded_sensors": list(self.degraded_sensors),
            "conflict_markers": list(self.conflict_markers),
            "lower_layer_health": dict(self.lower_layer_health),
            "evidence_items": [item.to_mapping() for item in self.evidence_items],
            "decision": self.decision.to_mapping() if self.decision is not None else None,
            "constrains_mainfsm": self.constrains_mainfsm,
            "metadata": dict(self.metadata),
        }
        if self.world_tick_id is not None:
            out["world_tick_id"] = self.world_tick_id
        if self.world_snapshot_id is not None:
            out["world_snapshot_id"] = self.world_snapshot_id
        if self.source_world_snapshot_id is not None:
            out["source_world_snapshot_id"] = self.source_world_snapshot_id
        if self.sim_time_s is not None:
            out["sim_time_s"] = self.sim_time_s
        if self.sensor_frame_id is not None:
            out["sensor_frame_id"] = self.sensor_frame_id
        if self.observation_frame_id is not None:
            out["observation_frame_id"] = self.observation_frame_id
        return out

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SensorTrustSnapshot":
        evidence_items = tuple(
            SensorTrustEvidence.from_mapping(item)
            for item in (data.get("evidence_items") or ())
            if isinstance(item, Mapping)
        )
        decision_data = data.get("decision")
        decision = SensorTrustDecision.from_mapping(decision_data) if isinstance(decision_data, Mapping) else None
        return cls(
            state=data.get("state") or SensorTrustState.DEGRADED,
            confidence=data.get("confidence") or 0.0,
            reason=data.get("reason") or SensorTrustReason.RUNTIME_READINGS_OK,
            reason_ru=str(data.get("reason_ru") or ""),
            evidence=tuple(data.get("evidence") or ()),
            source_path=str(data.get("source_path") or "qiki.shared.sensor_trust"),
            world_tick_id=data.get("world_tick_id"),
            world_snapshot_id=data.get("world_snapshot_id"),
            source_world_snapshot_id=data.get("source_world_snapshot_id") or data.get("world_snapshot_id"),
            sim_time_s=data.get("sim_time_s"),
            sensor_frame_id=data.get("sensor_frame_id"),
            observation_frame_id=data.get("observation_frame_id"),
            input_sensor_ids=tuple(data.get("input_sensor_ids") or ()),
            input_observation_ids=tuple(data.get("input_observation_ids") or ()),
            freshness_summary=dict(data.get("freshness_summary") or {}),
            missing_critical_sensors=tuple(data.get("missing_critical_sensors") or ()),
            degraded_sensors=tuple(data.get("degraded_sensors") or ()),
            conflict_markers=tuple(data.get("conflict_markers") or ()),
            lower_layer_health=dict(data.get("lower_layer_health") or {}),
            evidence_items=evidence_items,
            decision=decision,
            metadata=dict(data.get("metadata") or {}),
        )


def normalize_sensor_trust_state(value: SensorTrustState | str | None, *, default: SensorTrustState = SensorTrustState.DEGRADED) -> SensorTrustState:
    if isinstance(value, SensorTrustState):
        return value
    text = str(value or "").strip().lower().replace(" ", "_")
    return _EXPLICIT_STATE_ALIASES.get(text, default)


def normalize_sensor_trust_reason(value: SensorTrustReason | str | None) -> SensorTrustReason:
    if isinstance(value, SensorTrustReason):
        return value
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    for item in SensorTrustReason:
        if text == item.value:
            return item
    return SensorTrustReason.RUNTIME_READINGS_OK


def normalize_sensor_trust_override(value: str | SensorTrustOverride | None) -> SensorTrustOverride:
    if isinstance(value, SensorTrustOverride):
        return value
    text = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "": SensorTrustOverride.AUTO,
        "auto": SensorTrustOverride.AUTO,
        "clear": SensorTrustOverride.AUTO,
        "reset": SensorTrustOverride.AUTO,
        "trusted": SensorTrustOverride.TRUSTED,
        "trust": SensorTrustOverride.TRUSTED,
        "ok": SensorTrustOverride.TRUSTED,
        "degraded": SensorTrustOverride.DEGRADED,
        "degrade": SensorTrustOverride.DEGRADED,
        "warn": SensorTrustOverride.DEGRADED,
        "conflicting": SensorTrustOverride.CONFLICTING,
        "conflict": SensorTrustOverride.CONFLICTING,
        "lottery": SensorTrustOverride.LOTTERY,
        "uncertain": SensorTrustOverride.LOTTERY,
        "anomaly": SensorTrustOverride.LOTTERY,
        "blind": SensorTrustOverride.BLIND,
        "body-only": SensorTrustOverride.BLIND,
        "bodyonly": SensorTrustOverride.BLIND,
    }
    return aliases.get(text, SensorTrustOverride.AUTO)


def assess_sensor_trust(
    *,
    hardware_model: Any | None = None,
    telemetry: Mapping[str, Any] | None = None,
    radar_tracks: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]] | None = None,
    observation_objective: Mapping[str, Any] | None = None,
    operator_override: SensorTrustOverride | str | None = None,
) -> SensorTrustSnapshot:
    override = normalize_sensor_trust_override(operator_override)
    if override is not SensorTrustOverride.AUTO:
        state = normalize_sensor_trust_state(override.value, default=SensorTrustState.DEGRADED)
        return _make_snapshot(
            state=state,
            reason=SensorTrustReason.OPERATOR_LOCAL_OVERRIDE,
            reason_ru=f"оператор локально пометил сенсоры как {state.value}; это UI/decision hint, не runtime truth",
            confidence={
                SensorTrustState.TRUSTED: 0.75,
                SensorTrustState.DEGRADED: 0.52,
                SensorTrustState.CONFLICTING: 0.35,
                SensorTrustState.LOTTERY: 0.18,
                SensorTrustState.BLIND: 0.12,
            }[state],
            evidence=["LOCAL operator override; runtime telemetry not changed"],
            source_path="LOCAL operator sensor trust override",
            metadata={"operator_override": override.value},
        )
    return build_sensor_trust_snapshot(
        telemetry=telemetry,
        radar_tracks=radar_tracks,
        hardware_model=hardware_model,
        observation_objective=observation_objective,
    )


def build_sensor_trust_snapshot(
    *,
    sensor_frame: SensorFrameSnapshot | Mapping[str, Any] | None = None,
    telemetry: Mapping[str, Any] | None = None,
    radar_tracks: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]] | None = None,
    hardware_model: Any | None = None,
    incidents: Sequence[Mapping[str, Any]] | None = None,
    lower_layer_health: Mapping[str, Any] | None = None,
    observation_objective: Mapping[str, Any] | None = None,
    required_sensor_ids: Sequence[str] = _DEFAULT_REQUIRED_SENSOR_IDS,
    now_ts: float | None = None,
    stale_after_s: float = 5.0,
    dead_after_s: float = 30.0,
) -> SensorTrustSnapshot:
    del observation_objective  # Kept for old ORION API compatibility; runtime trust reads sensor frames.
    tel = telemetry if isinstance(telemetry, Mapping) else {}
    frame = _coerce_sensor_frame(sensor_frame, tel)
    explicit = _explicit_state(tel, frame_metadata=frame.metadata if frame is not None else None)
    explicit_confidence = _explicit_confidence(tel, explicit) if explicit is not None else None
    evaluation_now = _frame_now(frame, tel, now_ts)

    if frame is None:
        return _legacy_or_missing_snapshot(
            tel,
            radar_tracks=radar_tracks,
            hardware_model=hardware_model,
            incidents=incidents,
            explicit=explicit,
            explicit_confidence=explicit_confidence,
            now_ts=evaluation_now,
        )

    readings_by_id = {reading.sensor_id: reading for reading in frame.readings}
    evidence_items: list[SensorTrustEvidence] = []
    evidence_text: list[str] = []
    degraded_sensors: list[str] = []
    conflict_markers: list[str] = []
    missing_critical: list[str] = []
    freshness_summary: dict[str, str] = {}
    observation_ids: list[str] = []
    confidence_values: list[float] = []

    for reading in frame.readings:
        freshness = reading.freshness(now_ts=evaluation_now, stale_after_s=stale_after_s, dead_after_s=dead_after_s)
        freshness_summary[reading.sensor_id] = freshness.value
        if reading.confidence is not None:
            confidence_values.append(reading.confidence)
        if reading.observation_id:
            observation_ids.append(reading.observation_id)
        if reading.source_kind is SensorSourceKind.CONFIG:
            degraded_sensors.append(reading.sensor_id)
            _append_evidence(
                evidence_items,
                reason=SensorTrustReason.CONFIG_ONLY_SENSOR,
                message=f"{reading.sensor_id} is config-only; cannot be trusted as live runtime",
                reading=reading,
                severity="warn",
            )
        if reading.source_kind is SensorSourceKind.MISSING:
            degraded_sensors.append(reading.sensor_id)
            _append_evidence(
                evidence_items,
                reason=SensorTrustReason.MISSING_CRITICAL_SENSOR,
                message=f"{reading.sensor_id} source is missing",
                reading=reading,
                severity="warn",
            )
        if freshness in {SensorFreshness.STALE, SensorFreshness.DEAD}:
            degraded_sensors.append(reading.sensor_id)
            _append_evidence(
                evidence_items,
                reason=SensorTrustReason.DEAD_SENSOR if freshness is SensorFreshness.DEAD else SensorTrustReason.STALE_SENSOR,
                message=f"{reading.sensor_id} freshness={freshness.value}",
                reading=reading,
                severity="warn",
            )
        if reading.status in _BAD_STATUSES or reading.status in _DEGRADED_STATUSES:
            degraded_sensors.append(reading.sensor_id)
            _append_evidence(
                evidence_items,
                reason=SensorTrustReason.BAD_STATUS,
                message=f"{reading.sensor_id} status={reading.status.value}",
                reading=reading,
                severity="crit" if reading.status in _BAD_STATUSES else "warn",
            )
        if reading.confidence is not None and reading.confidence < 0.25:
            degraded_sensors.append(reading.sensor_id)
            _append_evidence(
                evidence_items,
                reason=SensorTrustReason.LOW_CONFIDENCE,
                message=f"{reading.sensor_id} confidence={reading.confidence:.2f}",
                reading=reading,
                severity="warn",
            )

    for sensor_id in required_sensor_ids:
        reading = readings_by_id.get(str(sensor_id))
        if reading is None:
            missing_critical.append(str(sensor_id))
            evidence_items.append(
                SensorTrustEvidence(
                    reason=SensorTrustReason.MISSING_CRITICAL_SENSOR,
                    message=f"critical sensor {sensor_id} absent from SensorFrameSnapshot",
                    sensor_id=str(sensor_id),
                    source_path="SensorFrameSnapshot.readings",
                    world_snapshot_id=frame.world_snapshot_id,
                    severity="warn",
                )
            )
        elif reading.source_kind in {SensorSourceKind.CONFIG, SensorSourceKind.MISSING} or reading.status in {SensorStatus.MISSING, SensorStatus.UNKNOWN}:
            missing_critical.append(str(sensor_id))

    conflict_markers.extend(_snapshot_conflict_markers(frame, readings_by_id, tel, radar_tracks))
    if conflict_markers:
        for marker in conflict_markers:
            evidence_items.append(
                SensorTrustEvidence(
                    reason=SensorTrustReason.SENSOR_CONFLICT,
                    message=marker,
                    source_path="qiki.shared.sensor_trust.conflict_detector",
                    world_snapshot_id=frame.world_snapshot_id,
                    severity="crit",
                )
            )

    lower = _lower_layer_health_from_inputs(tel, lower_layer_health, readings_by_id, hardware_model)
    lower_degraded = [f"{key}={value}" for key, value in lower.items() if str(value).strip().lower() not in {"ok", "true", "1", "nominal", "healthy", ""}]
    for item in lower_degraded:
        evidence_items.append(
            SensorTrustEvidence(
                reason=SensorTrustReason.LOWER_LAYER_HEALTH,
                message=f"lower layer health degrades sensors: {item}",
                source_path="telemetry.lower_layers",
                world_snapshot_id=frame.world_snapshot_id,
                severity="warn",
            )
        )

    lottery_marker = _lottery_marker(tel, readings_by_id, incidents, frame_metadata=frame.metadata)
    if lottery_marker:
        evidence_items.append(
            SensorTrustEvidence(
                reason=SensorTrustReason.LOTTERY_ENVIRONMENT,
                message=lottery_marker,
                source_path="telemetry.sensor_environment",
                world_snapshot_id=frame.world_snapshot_id,
                severity="crit",
            )
        )

    external_readings = [reading for reading in frame.readings if reading.sensor_id in _EXTERNAL_SENSOR_IDS or reading.sensor_type in _EXTERNAL_SENSOR_IDS]
    external_live = [reading for reading in external_readings if reading.source_kind is SensorSourceKind.LIVE and reading.status in {SensorStatus.OK, SensorStatus.WARN, SensorStatus.DEGRADED}]
    all_external_unavailable = bool(external_readings) and not external_live

    state = SensorTrustState.TRUSTED
    reason = SensorTrustReason.RUNTIME_READINGS_OK
    reason_ru = "sensor frame has fresh live readings with no hard conflict markers"
    if lottery_marker:
        state = SensorTrustState.LOTTERY
        reason = SensorTrustReason.LOTTERY_ENVIRONMENT
        reason_ru = "радиация/аномалия делает синтаксически валидные данные недостоверными"
    elif conflict_markers:
        state = SensorTrustState.CONFLICTING
        reason = SensorTrustReason.SENSOR_CONFLICT
        reason_ru = "сенсорные источники дают несовместимую картину"
    elif all_external_unavailable or _body_only_mode(tel):
        state = SensorTrustState.BLIND
        reason = SensorTrustReason.BLIND_EXTERNAL_CONTOUR
        reason_ru = "внешнее восприятие выключено или недоступно; остаётся корпусная телеметрия"
    elif missing_critical or degraded_sensors or lower_degraded:
        state = SensorTrustState.DEGRADED
        reason = _primary_degraded_reason(evidence_items)
        reason_ru = "часть сенсорного контура сообщает деградацию, отсутствие или устаревшие данные"

    state, reason, reason_ru, explicit_note = _combine_with_explicit_state(
        computed_state=state,
        computed_reason=reason,
        computed_reason_ru=reason_ru,
        explicit=explicit,
    )
    if explicit_note:
        evidence_items.append(
            SensorTrustEvidence(
                reason=SensorTrustReason.EXPLICIT_RUNTIME_STATE,
                message=explicit_note,
                source_path="telemetry.sensor_trust",
                world_snapshot_id=frame.world_snapshot_id,
                severity="info",
            )
        )

    for item in evidence_items:
        if item.message:
            evidence_text.append(item.message)
    if not evidence_text:
        evidence_text = ["fresh live SensorFrameSnapshot with no conflict markers"]

    confidence = _confidence_for_state(state, confidence_values, explicit_confidence=explicit_confidence)
    observation_frame_id = _observation_frame_id_from_frame(frame)
    sensor_frame_id = _sensor_frame_id_from_frame(frame)
    return _make_snapshot(
        state=state,
        reason=reason,
        reason_ru=reason_ru,
        confidence=confidence,
        evidence=evidence_text,
        source_path="qiki.shared.sensor_trust.build_sensor_trust_snapshot",
        world_tick_id=frame.world_tick_id,
        world_snapshot_id=frame.world_snapshot_id,
        source_world_snapshot_id=frame.source_world_snapshot_id or frame.world_snapshot_id,
        sim_time_s=frame.sim_time_s,
        sensor_frame_id=sensor_frame_id,
        observation_frame_id=observation_frame_id,
        input_sensor_ids=tuple(sorted(readings_by_id)),
        input_observation_ids=tuple(sorted(set(observation_ids))),
        freshness_summary=freshness_summary,
        missing_critical_sensors=tuple(sorted(set(missing_critical))),
        degraded_sensors=tuple(sorted(set(degraded_sensors))),
        conflict_markers=tuple(conflict_markers),
        lower_layer_health=lower,
        evidence_items=tuple(evidence_items),
        metadata={
            "required_sensor_ids": list(required_sensor_ids),
            "hard_conflicts_override_explicit_trusted": True,
            "authority": "derived_sensor_confidence_not_runtime_truth_mutation",
        },
    )


def sensor_trust_from_telemetry(telemetry: Mapping[str, Any], *, now_ts: float | None = None) -> SensorTrustSnapshot:
    return build_sensor_trust_snapshot(telemetry=telemetry, now_ts=now_ts)


def _legacy_or_missing_snapshot(
    tel: Mapping[str, Any],
    *,
    radar_tracks: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]] | None,
    hardware_model: Any | None,
    incidents: Sequence[Mapping[str, Any]] | None,
    explicit: SensorTrustState | None,
    explicit_confidence: float | None,
    now_ts: float,
) -> SensorTrustSnapshot:
    del hardware_model
    evidence: list[str] = []
    sensor_plane = _as_mapping(tel.get("sensor_plane"))
    track_count = _track_count(radar_tracks)
    if track_count:
        evidence.append(f"radar tracks={track_count}")
    if sensor_plane:
        evidence.append("legacy sensor_plane present")

    lottery_marker = _legacy_lottery_marker(tel, sensor_plane, incidents)
    conflict_markers = _legacy_conflict_markers(tel, sensor_plane, track_count)
    state = SensorTrustState.DEGRADED
    reason = SensorTrustReason.MISSING_SENSOR_FRAME
    reason_ru = "нет SensorFrameSnapshot; доверие понижено до legacy/derived mode"
    if lottery_marker:
        state = SensorTrustState.LOTTERY
        reason = SensorTrustReason.LOTTERY_ENVIRONMENT
        reason_ru = "радиация/аномалия делает синтаксически валидные данные недостоверными"
        evidence.append(lottery_marker)
    elif conflict_markers:
        state = SensorTrustState.CONFLICTING
        reason = SensorTrustReason.SENSOR_CONFLICT
        reason_ru = "сенсорные источники дают несовместимую картину"
        evidence.extend(conflict_markers)
    elif _body_only_mode(tel):
        state = SensorTrustState.BLIND
        reason = SensorTrustReason.BLIND_EXTERNAL_CONTOUR
        reason_ru = "внешнее восприятие выключено или недоступно; остаётся корпусная телеметрия"
    elif explicit is not None:
        state = explicit
        reason = SensorTrustReason.EXPLICIT_RUNTIME_STATE
        reason_ru = _reason_for_explicit(explicit)
        evidence.append(f"explicit legacy telemetry state={explicit.value}")

    state, reason, reason_ru, explicit_note = _combine_with_explicit_state(
        computed_state=state,
        computed_reason=reason,
        computed_reason_ru=reason_ru,
        explicit=explicit,
    )
    if explicit_note:
        evidence.append(explicit_note)
    if not evidence:
        evidence.append("no live SensorFrameSnapshot / no raw runtime sensor evidence")
    return _make_snapshot(
        state=state,
        reason=reason,
        reason_ru=reason_ru,
        confidence=explicit_confidence if explicit_confidence is not None else _STATE_CONFIDENCE_FALLBACK[state],
        evidence=evidence,
        source_path="qiki.shared.sensor_trust.legacy_telemetry_adapter",
        world_tick_id=_str_or_none(tel.get("world_tick_id")),
        world_snapshot_id=_str_or_none(tel.get("world_snapshot_id")),
        source_world_snapshot_id=_str_or_none(tel.get("source_world_snapshot_id") or tel.get("world_snapshot_id")),
        sim_time_s=tel.get("sim_time_s"),
        metadata={"legacy_adapter": True, "evaluated_at_epoch_s": now_ts},
    )


def _coerce_sensor_frame(sensor_frame: SensorFrameSnapshot | Mapping[str, Any] | None, telemetry: Mapping[str, Any]) -> SensorFrameSnapshot | None:
    candidate: Any = sensor_frame
    if candidate is None:
        candidate = telemetry.get("sensor_runtime") or telemetry.get("sensor_frame")
    if isinstance(candidate, SensorFrameSnapshot):
        return candidate
    if isinstance(candidate, Mapping):
        try:
            return SensorFrameSnapshot.from_mapping(candidate)
        except Exception:
            return None
    return None


def _frame_now(frame: SensorFrameSnapshot | None, telemetry: Mapping[str, Any], now_ts: float | None) -> float:
    if now_ts is not None:
        return float(now_ts)
    if frame is not None:
        return float(frame.generated_at_epoch_s)
    ts_unix_ms = _finite_float_or_none(telemetry.get("ts_unix_ms"))
    if ts_unix_ms is not None:
        return ts_unix_ms / 1000.0
    return time.time()


def _make_snapshot(
    *,
    state: SensorTrustState,
    reason: SensorTrustReason,
    reason_ru: str,
    confidence: float,
    evidence: Sequence[str],
    source_path: str,
    world_tick_id: str | None = None,
    world_snapshot_id: str | None = None,
    source_world_snapshot_id: str | None = None,
    sim_time_s: Any = None,
    sensor_frame_id: str | None = None,
    observation_frame_id: str | None = None,
    input_sensor_ids: tuple[str, ...] = (),
    input_observation_ids: tuple[str, ...] = (),
    freshness_summary: Mapping[str, str] | None = None,
    missing_critical_sensors: tuple[str, ...] = (),
    degraded_sensors: tuple[str, ...] = (),
    conflict_markers: tuple[str, ...] = (),
    lower_layer_health: Mapping[str, Any] | None = None,
    evidence_items: tuple[SensorTrustEvidence, ...] = (),
    metadata: Mapping[str, Any] | None = None,
) -> SensorTrustSnapshot:
    return SensorTrustSnapshot(
        state=state,
        confidence=confidence,
        reason=reason,
        reason_ru=reason_ru,
        evidence=tuple(evidence),
        source_path=source_path,
        world_tick_id=world_tick_id,
        world_snapshot_id=world_snapshot_id,
        source_world_snapshot_id=source_world_snapshot_id or world_snapshot_id,
        sim_time_s=sim_time_s,
        sensor_frame_id=sensor_frame_id,
        observation_frame_id=observation_frame_id,
        input_sensor_ids=input_sensor_ids,
        input_observation_ids=input_observation_ids,
        freshness_summary=freshness_summary or {},
        missing_critical_sensors=missing_critical_sensors,
        degraded_sensors=degraded_sensors,
        conflict_markers=conflict_markers,
        lower_layer_health=lower_layer_health or {},
        evidence_items=evidence_items,
        metadata=metadata or {},
    )


def _append_evidence(
    target: list[SensorTrustEvidence],
    *,
    reason: SensorTrustReason,
    message: str,
    reading: SensorReadingSnapshot,
    severity: str,
) -> None:
    target.append(
        SensorTrustEvidence(
            reason=reason,
            message=message,
            sensor_id=reading.sensor_id,
            source_path=reading.source_path,
            world_snapshot_id=reading.world_snapshot_id,
            observation_id=reading.observation_id,
            severity=severity,
        )
    )


def _snapshot_conflict_markers(
    frame: SensorFrameSnapshot,
    readings_by_id: Mapping[str, SensorReadingSnapshot],
    telemetry: Mapping[str, Any],
    radar_tracks: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]] | None,
) -> list[str]:
    markers: list[str] = []
    explicit = _pick_text(
        telemetry,
        ("sensor_conflict",),
        ("sensor_plane", "conflict"),
        ("sensor_plane", "contradiction"),
    )
    if explicit and explicit.lower() not in {"false", "0", "none", "no"}:
        markers.append(f"explicit conflict={explicit}")

    snapshot_ids = {reading.world_snapshot_id for reading in readings_by_id.values() if reading.world_snapshot_id}
    if frame.world_snapshot_id and snapshot_ids and any(item != frame.world_snapshot_id for item in snapshot_ids):
        markers.append("sensor readings reference multiple world_snapshot_id values")

    proximity = readings_by_id.get("sensor_proximity")
    track_count = _track_count(radar_tracks)
    if proximity is not None and isinstance(proximity.value, Mapping):
        contacts = _first_number(proximity.value.get("contacts"), proximity.value.get("contacts_count"))
        min_range = _first_number(proximity.value.get("min_range_m"))
        if contacts is not None and contacts > 0 and radar_tracks is not None and track_count == 0:
            markers.append("proximity sees contact but radar has no tracks")
        if min_range is not None and 0 <= min_range <= 250 and radar_tracks is not None and track_count == 0:
            markers.append("close range contact without radar track")
    star = readings_by_id.get("star_tracker")
    imu = readings_by_id.get("imu_main")
    if star is not None and isinstance(star.value, Mapping):
        locked = _first_bool(star.value.get("locked"), star.value.get("ok"))
        if locked is False and imu is not None and imu.status is SensorStatus.OK:
            markers.append("IMU attitude present while star tracker reports unlocked")
    return markers


def _lower_layer_health_from_inputs(
    telemetry: Mapping[str, Any],
    lower_layer_health: Mapping[str, Any] | None,
    readings_by_id: Mapping[str, SensorReadingSnapshot],
    hardware_model: Any | None,
) -> dict[str, Any]:
    health: dict[str, Any] = dict(lower_layer_health or {})
    power_reading = readings_by_id.get("sensor_power")
    thermal_reading = readings_by_id.get("sensor_thermal")
    if power_reading is not None and power_reading.status in _BAD_STATUSES:
        health.setdefault("power_sensor_status", power_reading.status.value)
    if thermal_reading is not None and thermal_reading.status in _BAD_STATUSES:
        health.setdefault("thermal_sensor_status", thermal_reading.status.value)
    power = _as_mapping(telemetry.get("power"))
    faults = power.get("faults")
    if faults:
        health.setdefault("power_faults", ",".join(str(item) for item in faults) if isinstance(faults, Sequence) and not isinstance(faults, (str, bytes)) else str(faults))
    thermal = _as_mapping(telemetry.get("thermal"))
    nodes = thermal.get("nodes")
    if isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes)):
        tripped = [str(node.get("id") or "unknown") for node in nodes if isinstance(node, Mapping) and bool(node.get("tripped"))]
        if tripped:
            health.setdefault("thermal_trip_nodes", ",".join(tripped))
    subsystem = _subsystem(hardware_model, "sensors")
    if subsystem is not None and not _subsystem_has_values(subsystem):
        health.setdefault("hardware_sensors", "no_values")
    return health


def _primary_degraded_reason(evidence_items: Sequence[SensorTrustEvidence]) -> SensorTrustReason:
    for preferred in (
        SensorTrustReason.MISSING_CRITICAL_SENSOR,
        SensorTrustReason.STALE_SENSOR,
        SensorTrustReason.DEAD_SENSOR,
        SensorTrustReason.LOW_CONFIDENCE,
        SensorTrustReason.BAD_STATUS,
        SensorTrustReason.LOWER_LAYER_HEALTH,
    ):
        if any(item.reason is preferred for item in evidence_items):
            return preferred
    return SensorTrustReason.BAD_STATUS


def _lottery_marker(
    telemetry: Mapping[str, Any],
    readings_by_id: Mapping[str, SensorReadingSnapshot],
    incidents: Sequence[Mapping[str, Any]] | None,
    *,
    frame_metadata: Mapping[str, Any] | None = None,
) -> str:
    radiation = readings_by_id.get("sensor_radiation")
    radiation_value = radiation.value if radiation is not None and isinstance(radiation.value, Mapping) else {}
    radiation_usvh = _first_number(radiation_value.get("background_usvh"), telemetry.get("radiation_usvh"))
    radiation_status = radiation.status if radiation is not None else SensorStatus.UNKNOWN
    if radiation_usvh is not None and radiation_usvh >= 5000.0:
        return f"radiation={radiation_usvh:g} uSv/h exceeds sensor trust lottery threshold"
    if radiation_status is SensorStatus.FAULT and radiation_usvh is not None and radiation_usvh >= 1000.0:
        return f"radiation sensor fault under high radiation={radiation_usvh:g} uSv/h"
    frame_metadata = frame_metadata if isinstance(frame_metadata, Mapping) else {}
    fields = [
        _pick_text(telemetry, ("anomaly", "state"), ("anomaly", "kind"), ("environment", "anomaly")),
        _pick_text(telemetry, ("sim_state", "anomaly"), ("sim_state", "causality")),
        _pick_text(frame_metadata, ("anomaly",), ("sensor_mode",), ("sensor_trust",)),
    ]
    if any(_contains_any(item, ("lottery", "uncertain", "causal", "anomaly", "jet", "radiation storm")) for item in fields):
        return "telemetry/anomaly marker indicates lottery sensor environment"
    for incident in incidents or ():
        joined = " ".join(str(value) for value in incident.values())
        if _contains_any(joined, ("lottery", "sensor trust", "сенсоры", "radiation", "джет", "causal")):
            return "incident marker indicates lottery sensor environment"
    return ""


def _combine_with_explicit_state(
    *,
    computed_state: SensorTrustState,
    computed_reason: SensorTrustReason,
    computed_reason_ru: str,
    explicit: SensorTrustState | None,
) -> tuple[SensorTrustState, SensorTrustReason, str, str]:
    if explicit is None:
        return computed_state, computed_reason, computed_reason_ru, ""
    if _STATE_RANK[computed_state] > _STATE_RANK[explicit]:
        return (
            computed_state,
            computed_reason,
            computed_reason_ru,
            f"explicit state={explicit.value} ignored because computed state={computed_state.value} is stricter",
        )
    if _STATE_RANK[explicit] > _STATE_RANK[computed_state]:
        return explicit, SensorTrustReason.EXPLICIT_RUNTIME_STATE, _reason_for_explicit(explicit), f"explicit state={explicit.value} applied"
    return computed_state, computed_reason, computed_reason_ru, f"explicit state={explicit.value} matches computed state"


def _confidence_for_state(state: SensorTrustState, values: Sequence[float], *, explicit_confidence: float | None) -> float:
    if explicit_confidence is not None and state in {SensorTrustState.CONFLICTING, SensorTrustState.LOTTERY, SensorTrustState.BLIND}:
        return min(explicit_confidence, _STATE_CONFIDENCE_FALLBACK[state])
    if explicit_confidence is not None and state is SensorTrustState.TRUSTED:
        return explicit_confidence
    clean = [float(value) for value in values if 0.0 <= float(value) <= 1.0]
    if not clean:
        return _STATE_CONFIDENCE_FALLBACK[state]
    min_conf = min(clean)
    avg_conf = sum(clean) / len(clean)
    if state is SensorTrustState.TRUSTED:
        return max(0.0, min(1.0, avg_conf))
    if state is SensorTrustState.DEGRADED:
        return max(0.25, min(0.65, min_conf))
    return _STATE_CONFIDENCE_FALLBACK[state]


def _decision_for_state(state: SensorTrustState, confidence: float, reason: SensorTrustReason | str) -> SensorTrustDecision:
    return SensorTrustDecision(
        state=state,
        confidence=confidence,
        reason=reason,
        allowed_for_navigation=state in {SensorTrustState.TRUSTED, SensorTrustState.DEGRADED},
        allowed_for_high_risk_action=state is SensorTrustState.TRUSTED and confidence >= 0.65,
        recommended_mainfsm_sensor_trust=state.value.upper(),
        recommended_operator_posture={
            SensorTrustState.TRUSTED: "normal",
            SensorTrustState.DEGRADED: "cautious",
            SensorTrustState.CONFLICTING: "evidence_required",
            SensorTrustState.LOTTERY: "body_only_manual_confirmation",
            SensorTrustState.BLIND: "body_only",
        }[state],
    )


def _observation_frame_id_from_frame(frame: SensorFrameSnapshot) -> str | None:
    if isinstance(frame.sensor_observation, Mapping):
        value = frame.sensor_observation.get("observation_frame_id")
        if value:
            return str(value)
    return _str_or_none(frame.metadata.get("sensor_observation_frame_id") if isinstance(frame.metadata, Mapping) else None)


def _sensor_frame_id_from_frame(frame: SensorFrameSnapshot) -> str:
    if isinstance(frame.metadata, Mapping):
        value = frame.metadata.get("sensor_frame_id")
        if value:
            return str(value)
    if frame.world_snapshot_id:
        return f"SF-{frame.world_snapshot_id}"
    return f"SF-{int(frame.generated_at_epoch_s * 1000)}"


def _explicit_state(telemetry: Mapping[str, Any], *, frame_metadata: Mapping[str, Any] | None = None) -> SensorTrustState | None:
    frame_metadata = frame_metadata if isinstance(frame_metadata, Mapping) else {}
    raw = _pick_text(
        telemetry,
        ("sensor_trust", "state"),
        ("sensor_trust", "mode"),
        ("sensor_trust", "trust"),
        ("sensor_trust_state",),
        ("sensor_mode",),
        ("anomaly", "sensor_trust"),
    ) or _pick_text(
        frame_metadata,
        ("sensor_trust", "state"),
        ("sensor_trust", "mode"),
        ("sensor_trust",),
        ("sensor_trust_state",),
        ("sensor_mode",),
    )
    if not raw:
        return None
    return normalize_sensor_trust_state(raw, default=SensorTrustState.DEGRADED)


def _explicit_confidence(telemetry: Mapping[str, Any], state: SensorTrustState | None) -> float | None:
    if state is None:
        return None
    value = _first_number(_get(telemetry, "sensor_trust", "confidence"), telemetry.get("sensor_confidence"))
    if value is None:
        return _STATE_CONFIDENCE_FALLBACK[state]
    return _clamp01(value)


def _reason_for_explicit(state: SensorTrustState) -> str:
    return {
        SensorTrustState.TRUSTED: "runtime явно пометил сенсорный контур как trusted",
        SensorTrustState.DEGRADED: "runtime явно пометил сенсорный контур как degraded",
        SensorTrustState.CONFLICTING: "runtime явно пометил сенсорный контур как conflicting",
        SensorTrustState.LOTTERY: "runtime/anomaly явно пометил сенсорный контур как lottery",
        SensorTrustState.BLIND: "runtime явно пометил контур как blind/body-only",
    }[state]


def _reason_ru_for_state(state: SensorTrustState) -> str:
    return {
        SensorTrustState.TRUSTED: "нет признаков конфликта, lottery-mode или blind-mode",
        SensorTrustState.DEGRADED: "часть сенсорного контура сообщает деградацию или устаревшие данные",
        SensorTrustState.CONFLICTING: "сенсорные источники дают несовместимую картину",
        SensorTrustState.LOTTERY: "радиация/аномалия делает синтаксически валидные данные недостоверными",
        SensorTrustState.BLIND: "внешнее восприятие выключено или недоступно; остаётся корпусная телеметрия",
    }[state]


def _legacy_lottery_marker(telemetry: Mapping[str, Any], sensor_plane: Mapping[str, Any], incidents: Sequence[Mapping[str, Any]] | None) -> str:
    radiation_usvh = _first_number(
        _get(sensor_plane, "radiation", "background_usvh"),
        _get(sensor_plane, "radiation", "background_uSv_h"),
        _get(telemetry, "radiation", "background_usvh"),
        telemetry.get("radiation_usvh"),
    )
    radiation_status = _status_text(_get(sensor_plane, "radiation", "status"), _get(telemetry, "radiation", "status"))
    if radiation_usvh is not None and radiation_usvh >= 5000.0:
        return f"radiation={radiation_usvh:g} uSv/h exceeds sensor trust lottery threshold"
    if _contains_any(radiation_status, ("critical", "crit", "severe", "storm", "anomaly", "крит", "шторм")):
        return f"radiation status={radiation_status}"
    for incident in incidents or ():
        joined = " ".join(str(value) for value in incident.values())
        if _contains_any(joined, ("lottery", "sensor trust", "сенсоры", "radiation", "джет", "causal")):
            return "incident marker indicates lottery sensor environment"
    return ""


def _legacy_conflict_markers(telemetry: Mapping[str, Any], sensor_plane: Mapping[str, Any], track_count: int) -> list[str]:
    markers: list[str] = []
    explicit = _pick_text(telemetry, ("sensor_conflict",), ("sensor_plane", "conflict"), ("sensor_plane", "contradiction"))
    if explicit and explicit.lower() not in {"false", "0", "none", "no"}:
        markers.append(f"explicit conflict={explicit}")
    proximity_contacts = _first_number(_get(sensor_plane, "proximity", "contacts"), _get(telemetry, "proximity", "contacts"))
    if proximity_contacts is not None and proximity_contacts > 0 and track_count == 0:
        markers.append("proximity sees contact but radar has no tracks")
    return markers


def _body_only_mode(telemetry: Mapping[str, Any]) -> bool:
    raw = _pick_text(telemetry, ("sensor_mode",), ("sensor_plane", "mode"), ("guidance", "sensor_mode"))
    return _contains_any(raw, ("body_only", "body-only", "blind", "external_off", "корпус"))


def _subsystem(hardware_model: Any | None, subsystem_id: str) -> Any | None:
    subsystems = getattr(hardware_model, "subsystems", None)
    if isinstance(subsystems, Mapping):
        return subsystems.get(subsystem_id)
    return None


def _subsystem_has_values(subsystem: Any | None) -> bool:
    if subsystem is None:
        return False
    for field in getattr(subsystem, "fields", ()) or ():
        value = getattr(field, "value", None)
        if value is None:
            continue
        text = str(value).strip().lower()
        if text and text not in {"нет данных", "none", "null", "unknown", "n/a"}:
            return True
    return False


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _get(source: Any, *path: str) -> Any:
    current = source
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _pick_text(source: Mapping[str, Any], *paths: tuple[str, ...]) -> str:
    for path in paths:
        value = _get(source, *path)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _status_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip().lower()
        if text:
            return text
    return ""


def _track_count(radar_tracks: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]] | None) -> int:
    if radar_tracks is None:
        return 0
    if isinstance(radar_tracks, Mapping):
        return len(radar_tracks)
    if isinstance(radar_tracks, Sequence) and not isinstance(radar_tracks, (str, bytes)):
        return len(radar_tracks)
    return 0


def _contains_any(text: str, needles: Sequence[str]) -> bool:
    normalized = str(text or "").strip().lower()
    return any(str(needle).lower() in normalized for needle in needles)


def _first_number(*values: Any) -> float | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            parsed = float(value)
            return parsed if math.isfinite(parsed) else None
        try:
            parsed = float(str(value).strip())
        except (TypeError, ValueError):
            continue
        return parsed if math.isfinite(parsed) else None
    return None


def _first_bool(*values: Any) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
        if value is None:
            continue
        text = str(value).strip().lower()
        if text in {"true", "yes", "1", "locked", "ok", "healthy"}:
            return True
        if text in {"false", "no", "0", "unlocked", "lost", "failed"}:
            return False
    return None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _finite_float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _clamp01(value: Any) -> float:
    parsed = _finite_float_or_none(value)
    if parsed is None:
        return 0.0
    return max(0.0, min(1.0, parsed))


__all__ = [
    "SensorTrustDecision",
    "SensorTrustEvidence",
    "SensorTrustOverride",
    "SensorTrustReason",
    "SensorTrustSnapshot",
    "SensorTrustState",
    "assess_sensor_trust",
    "build_sensor_trust_snapshot",
    "normalize_sensor_trust_override",
    "normalize_sensor_trust_reason",
    "normalize_sensor_trust_state",
    "sensor_trust_from_telemetry",
]
