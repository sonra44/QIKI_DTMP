from typing import Any, cast

import pytest

from qiki.services.faststream_bridge.lag_monitor import (
    ConsumerTarget,
    JetStreamLagMonitor,
)
from qiki.services.faststream_bridge.metrics import _JETSTREAM_CONSUMER_LAG  # type: ignore[attr-defined]


class _FakeInfo:
    def __init__(self, pending: int) -> None:
        self.num_pending = pending


class _FakeJS:
    def __init__(self, pending: int, raise_error: bool = False) -> None:
        self._pending = pending
        self._raise = raise_error

    async def consumer_info(self, stream: str, durable: str) -> _FakeInfo:
        if self._raise:
            raise RuntimeError("boom")
        return _FakeInfo(self._pending)


@pytest.mark.asyncio
async def test_poll_once_sets_gauge() -> None:
    monitor = JetStreamLagMonitor(
        nats_url="nats://test",
        stream="STREAM",
        consumers=[ConsumerTarget(durable="durable", label="label")],
        interval_sec=0.1,
    )
    monitor._js = cast(Any, _FakeJS(pending=7))  # type: ignore[attr-defined]

    await monitor._poll_once()

    metric = _JETSTREAM_CONSUMER_LAG.labels(consumer="label")
    if hasattr(metric, "_value"):
        assert metric._value.get() == 7
    else:  # pragma: no cover - Prometheus client отсутствует
        pytest.skip("Prometheus client not available")


@pytest.mark.asyncio
async def test_poll_once_handles_error_and_sets_zero() -> None:
    monitor = JetStreamLagMonitor(
        nats_url="nats://test",
        stream="STREAM",
        consumers=[ConsumerTarget(durable="durable", label="label")],
        interval_sec=0.1,
    )
    monitor._js = cast(Any, _FakeJS(pending=5, raise_error=True))  # type: ignore[attr-defined]

    await monitor._poll_once()

    metric = _JETSTREAM_CONSUMER_LAG.labels(consumer="label")
    if hasattr(metric, "_value"):
        assert metric._value.get() == 0
    else:  # pragma: no cover
        pytest.skip("Prometheus client not available")
