"""Prometheus metrics for the Q-Core agent world model."""

from __future__ import annotations

from typing import Iterable

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter, Gauge  # type: ignore
except ModuleNotFoundError:  # pragma: no cover

    class _NoOpMetric:
        def set(self, *_args, **_kwargs) -> None:
            return None

        def inc(self, *_args, **_kwargs) -> None:
            return None

    def _noop_metric_factory(*_args, **_kwargs) -> _NoOpMetric:
        return _NoOpMetric()

    Counter = Gauge = _noop_metric_factory  # type: ignore

from qiki.services.q_core_agent.core.guard_table import GuardEvaluationResult


_WORLD_MODEL_ACTIVE_TRACKS = Gauge(
    "qiki_agent_radar_active_tracks",
    "Number of radar tracks currently maintained by the world model",
)
_WORLD_MODEL_CRITICAL_GUARDS = Gauge(
    "qiki_agent_guard_critical_active",
    "Number of active guard events with critical severity",
)
_WORLD_MODEL_WARNING_GUARDS = Gauge(
    "qiki_agent_guard_warning_active",
    "Number of active guard events with warning severity",
)
_WORLD_MODEL_WARNING_TOTAL = Counter(
    "qiki_agent_guard_warning_total",
    "Total number of warning guard events observed",
)


def publish_world_model_metrics(
    active_tracks: int,
    guard_results: Iterable[GuardEvaluationResult],
    new_warning_events: int,
) -> None:
    """Push aggregated world model information to Prometheus metrics."""

    critical = 0
    warning = 0
    for result in guard_results:
        if result.severity == "critical":
            critical += 1
        elif result.severity == "warning":
            warning += 1

    _WORLD_MODEL_ACTIVE_TRACKS.set(max(active_tracks, 0))
    _WORLD_MODEL_CRITICAL_GUARDS.set(max(critical, 0))
    _WORLD_MODEL_WARNING_GUARDS.set(max(warning, 0))
    if new_warning_events > 0:
        _WORLD_MODEL_WARNING_TOTAL.inc(new_warning_events)
