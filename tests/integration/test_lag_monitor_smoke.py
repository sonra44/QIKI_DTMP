"""Integration smoke test for JetStream lag monitoring."""

import pytest

try:
    # Try to import required modules
    from qiki.services.faststream_bridge.lag_monitor import JetStreamLagMonitor, ConsumerTarget
except Exception:
    pytest.skip("Dependencies not available; skipping integration tests", allow_module_level=True)


@pytest.mark.integration
def test_lag_monitor_smoke():
    """Smoke test for JetStream lag monitoring - basic import and instantiation."""
    # This test just verifies that we can import and create the monitor
    # In a real environment, this would connect to NATS and monitor actual consumers
    
    consumers = [
        ConsumerTarget(durable="radar_frames_pull", label="frames"),
        ConsumerTarget(durable="radar_tracks_pull", label="tracks")
    ]
    
    monitor = JetStreamLagMonitor(
        nats_url="nats://qiki-nats-phase1:4222",
        stream="QIKI_RADAR_V1",
        consumers=consumers,
        interval_sec=5.0
    )
    
    # Just verify the object was created successfully
    assert monitor is not None
    assert monitor._nats_url == "nats://qiki-nats-phase1:4222"
    assert monitor._stream == "QIKI_RADAR_V1"
    assert len(monitor._consumers) == 2