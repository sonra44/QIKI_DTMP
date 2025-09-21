import pytest

from qiki.services.faststream_bridge.metrics import set_consumer_lag


def test_set_consumer_lag_updates_gauge():
    # Should not raise and should clamp negative values to zero
    set_consumer_lag("test_consumer", -5)
    set_consumer_lag("test_consumer", 7)

    # Access internal value via private attribute (Prometheus Gauge stores _value)
    from qiki.services.faststream_bridge.metrics import _JETSTREAM_CONSUMER_LAG  # type: ignore[attr-defined]

    metric = _JETSTREAM_CONSUMER_LAG.labels(consumer="test_consumer")
    if hasattr(metric, "_value"):
        assert metric._value.get() == 7
    else:  # pragma: no cover - fallback when prometheus_client отсутствует
        pytest.skip("Prometheus client not available")
