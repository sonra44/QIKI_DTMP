"""Operational health snapshot/evaluation for radar runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .event_store import EventStore, TruthState


_HEALTH_OK = "OK"
_HEALTH_WARN = "WARN"
_HEALTH_CRIT = "CRIT"
_HEALTH_NO_DATA = "NO_DATA"


def _env_float(name: str, default: float, *, min_value: float = 0.0) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except Exception:
        return default
    if value < min_value:
        return min_value
    return value


def _env_int(name: str, default: int, *, min_value: int = 0) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except Exception:
        return default
    if value < min_value:
        return min_value
    return value


@dataclass(frozen=True)
class HealthRules:
    frame_p95_warn_ms: float = 80.0
    frame_p95_crit_ms: float = 140.0
    sqlite_queue_warn: int = 5_000
    sqlite_queue_crit: int = 20_000
    session_stale_ms: float = 2_000.0
    fusion_conflict_warn_rate: float = 0.30
    strict: bool = False

    @classmethod
    def from_env(cls, *, strict: bool = False) -> "HealthRules":
        return cls(
            frame_p95_warn_ms=_env_float("QIKI_HEALTH_FRAME_P95_WARN_MS", 80.0, min_value=1.0),
            frame_p95_crit_ms=_env_float("QIKI_HEALTH_FRAME_P95_CRIT_MS", 140.0, min_value=1.0),
            sqlite_queue_warn=_env_int("QIKI_HEALTH_SQLITE_QUEUE_WARN", 5_000, min_value=1),
            sqlite_queue_crit=_env_int("QIKI_HEALTH_SQLITE_QUEUE_CRIT", 20_000, min_value=1),
            session_stale_ms=_env_float("QIKI_HEALTH_SESSION_STALE_MS", 2_000.0, min_value=10.0),
            fusion_conflict_warn_rate=_env_float("QIKI_HEALTH_FUSION_CONFLICT_WARN_RATE", 0.30, min_value=0.0),
            strict=bool(strict),
        )


@dataclass(frozen=True)
class HealthIssue:
    subsystem: str
    metric: str
    severity: str
    value: float | int | str
    threshold: float | int | str
    reason: str

    @property
    def key(self) -> str:
        return f"{self.subsystem}.{self.metric}"

    @property
    def short(self) -> str:
        return f"{self.subsystem}:{self.metric}={self.value} ({self.reason})"


@dataclass(frozen=True)
class HealthSnapshot:
    ts: float
    overall: str
    pipeline: dict[str, Any]
    fusion: dict[str, Any]
    policy: dict[str, Any]
    eventstore: dict[str, Any]
    session: dict[str, Any]
    replay: dict[str, Any]
    issues: tuple[HealthIssue, ...]
    top_issues: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": float(self.ts),
            "overall": self.overall,
            "pipeline": dict(self.pipeline),
            "fusion": dict(self.fusion),
            "policy": dict(self.policy),
            "eventstore": dict(self.eventstore),
            "session": dict(self.session),
            "replay": dict(self.replay),
            "issues": [
                {
                    "subsystem": issue.subsystem,
                    "metric": issue.metric,
                    "severity": issue.severity,
                    "value": issue.value,
                    "threshold": issue.threshold,
                    "reason": issue.reason,
                }
                for issue in self.issues
            ],
            "top_issues": list(self.top_issues),
        }


def _truth_from_severity(severity: str) -> TruthState:
    if severity == _HEALTH_NO_DATA:
        return TruthState.NO_DATA
    if severity == _HEALTH_CRIT:
        return TruthState.INVALID
    if severity == _HEALTH_WARN:
        return TruthState.NO_DATA
    return TruthState.OK


class HealthMonitor:
    """Evaluates health snapshot and emits transition-only health events."""

    def __init__(self, *, event_store: EventStore | None, rules: HealthRules) -> None:
        self.event_store = event_store
        self.rules = rules
        self._active: dict[str, HealthIssue] = {}

    def evaluate(
        self,
        *,
        ts: float,
        pipeline: dict[str, Any],
        fusion: dict[str, Any],
        policy: dict[str, Any],
        eventstore: dict[str, Any],
        session: dict[str, Any],
        replay: dict[str, Any],
    ) -> HealthSnapshot:
        issues: list[HealthIssue] = []

        frame_p95 = float(pipeline.get("frame_ms_p95", 0.0) or 0.0)
        if frame_p95 >= self.rules.frame_p95_crit_ms:
            issues.append(
                HealthIssue(
                    subsystem="pipeline",
                    metric="frame_ms_p95",
                    severity=_HEALTH_CRIT,
                    value=round(frame_p95, 3),
                    threshold=self.rules.frame_p95_crit_ms,
                    reason="FRAME_P95_CRIT",
                )
            )
        elif frame_p95 >= self.rules.frame_p95_warn_ms:
            issues.append(
                HealthIssue(
                    subsystem="pipeline",
                    metric="frame_ms_p95",
                    severity=_HEALTH_WARN,
                    value=round(frame_p95, 3),
                    threshold=self.rules.frame_p95_warn_ms,
                    reason="FRAME_P95_WARN",
                )
            )

        queue_depth = int(eventstore.get("sqlite_queue_depth", 0) or 0)
        if queue_depth >= self.rules.sqlite_queue_crit:
            issues.append(
                HealthIssue(
                    subsystem="eventstore",
                    metric="sqlite_queue_depth",
                    severity=_HEALTH_CRIT,
                    value=queue_depth,
                    threshold=self.rules.sqlite_queue_crit,
                    reason="SQLITE_QUEUE_CRIT",
                )
            )
        elif queue_depth >= self.rules.sqlite_queue_warn:
            issues.append(
                HealthIssue(
                    subsystem="eventstore",
                    metric="sqlite_queue_depth",
                    severity=_HEALTH_WARN,
                    value=queue_depth,
                    threshold=self.rules.sqlite_queue_warn,
                    reason="SQLITE_QUEUE_WARN",
                )
            )

        dropped = int(eventstore.get("dropped_events", 0) or 0)
        if dropped > 0:
            severity = _HEALTH_CRIT if self.rules.strict else _HEALTH_WARN
            issues.append(
                HealthIssue(
                    subsystem="eventstore",
                    metric="dropped_events",
                    severity=severity,
                    value=dropped,
                    threshold=0,
                    reason="EVENTSTORE_DROP",
                )
            )

        session_mode = str(session.get("mode", "standalone") or "standalone")
        stale_ms = float(session.get("stale_ms", 0.0) or 0.0)
        if session_mode in {"client", "server"} and stale_ms >= self.rules.session_stale_ms:
            issues.append(
                HealthIssue(
                    subsystem="session",
                    metric="stale_ms",
                    severity=_HEALTH_NO_DATA,
                    value=round(stale_ms, 3),
                    threshold=self.rules.session_stale_ms,
                    reason="SESSION_STALE",
                )
            )

        conflict_rate = float(fusion.get("conflict_rate", 0.0) or 0.0)
        if conflict_rate >= self.rules.fusion_conflict_warn_rate:
            issues.append(
                HealthIssue(
                    subsystem="fusion",
                    metric="conflict_rate",
                    severity=_HEALTH_WARN,
                    value=round(conflict_rate, 3),
                    threshold=self.rules.fusion_conflict_warn_rate,
                    reason="FUSION_CONFLICT_RATE_WARN",
                )
            )

        overall = _HEALTH_OK
        if any(issue.severity == _HEALTH_NO_DATA for issue in issues):
            overall = _HEALTH_NO_DATA
        elif any(issue.severity == _HEALTH_CRIT for issue in issues):
            overall = _HEALTH_CRIT
        elif any(issue.severity == _HEALTH_WARN for issue in issues):
            overall = _HEALTH_WARN

        top = tuple(issue.short for issue in issues[:2])
        snapshot = HealthSnapshot(
            ts=float(ts),
            overall=overall,
            pipeline=dict(pipeline),
            fusion=dict(fusion),
            policy=dict(policy),
            eventstore=dict(eventstore),
            session=dict(session),
            replay=dict(replay),
            issues=tuple(issues),
            top_issues=top,
        )
        self._emit_transitions(snapshot)
        return snapshot

    def _emit_transitions(self, snapshot: HealthSnapshot) -> None:
        if self.event_store is None:
            self._active = {issue.key: issue for issue in snapshot.issues}
            return
        current = {issue.key: issue for issue in snapshot.issues}
        for key, issue in current.items():
            previous = self._active.get(key)
            if previous is not None and previous.severity == issue.severity:
                continue
            event_type = {
                _HEALTH_WARN: "HEALTH_WARN",
                _HEALTH_CRIT: "HEALTH_CRIT",
                _HEALTH_NO_DATA: "HEALTH_NO_DATA",
            }.get(issue.severity, "HEALTH_WARN")
            self.event_store.append_new(
                subsystem="HEALTH",
                event_type=event_type,
                payload={
                    "subsystem": issue.subsystem,
                    "metric": issue.metric,
                    "value": issue.value,
                    "threshold": issue.threshold,
                    "overall": snapshot.overall,
                },
                truth_state=_truth_from_severity(issue.severity),
                reason=issue.reason,
            )
        for key, issue in self._active.items():
            if key in current:
                continue
            self.event_store.append_new(
                subsystem="HEALTH",
                event_type="HEALTH_RECOVERED",
                payload={
                    "subsystem": issue.subsystem,
                    "metric": issue.metric,
                    "value": issue.value,
                    "threshold": issue.threshold,
                    "overall": snapshot.overall,
                },
                truth_state=TruthState.OK,
                reason=f"RECOVERED:{issue.reason}",
            )
        self._active = current
