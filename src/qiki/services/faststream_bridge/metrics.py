"""Prometheus metrics for radar FastStream bridge."""

from __future__ import annotations

try:  # pragma: no cover - import guard for minimal environments
    from prometheus_client import Counter, Gauge, Histogram  # type: ignore
except ModuleNotFoundError:  # pragma: no cover

    class _NoOpMetric:
        def observe(self, *_args, **_kwargs) -> None:
            return None

        def set(self, *_args, **_kwargs) -> None:
            return None

        def inc(self, *_args, **_kwargs) -> None:
            return None

        def labels(self, *_args, **_kwargs) -> "_NoOpMetric":
            return self

    def _noop_metric_factory(*_args, **_kwargs) -> _NoOpMetric:
        return _NoOpMetric()

    Histogram = Gauge = Counter = _noop_metric_factory  # type: ignore


_RADAR_FRAME_LATENCY_MS = Histogram(
    "qiki_radar_frame_latency_ms",
    "Processing latency for radar frames in FastStream bridge",
    buckets=(1, 5, 10, 20, 50, 100, 250, 500, 1000, 1500, 2000),
)
_RADAR_TRACK_ACTIVE_TOTAL = Gauge(
    "qiki_radar_active_tracks",
    "Number of active radar tracks maintained in TrackStore",
)
_RADAR_REDELIVERIES_TOTAL = Counter(
    "qiki_radar_redeliveries_total",
    "Count of redelivered radar frames from JetStream",
)
_JETSTREAM_CONSUMER_LAG = Gauge(
    "qiki_jetstream_consumer_lag",
    "Number of pending messages in JetStream consumer",
    labelnames=("consumer",),
)


def observe_frame(duration_ms: float, track_count: int) -> None:
    """Record processing latency and track count."""

    _RADAR_FRAME_LATENCY_MS.observe(max(duration_ms, 0.0))
    _RADAR_TRACK_ACTIVE_TOTAL.set(max(track_count, 0))


def incr_redelivery() -> None:
    """Increment redelivery counter."""

    _RADAR_REDELIVERIES_TOTAL.inc()


def set_consumer_lag(consumer: str, pending: int) -> None:
    """Expose JetStream consumer pending count as gauge."""

    _JETSTREAM_CONSUMER_LAG.labels(consumer=consumer).set(max(pending, 0))
