from datetime import UTC, datetime
from uuid import uuid4

import pytest

from qiki.services.faststream_bridge.track_publisher import RadarTrackPublisher
from qiki.shared.models.radar import RadarTrackModel


def _make_track() -> RadarTrackModel:
    return RadarTrackModel(
        track_id=uuid4(),
        range_m=100.0,
        bearing_deg=10.0,
        elev_deg=2.0,
        vr_mps=0.0,
        snr_db=12.0,
        rcs_dbsm=1.0,
        timestamp=datetime.now(UTC),
    )


@pytest.mark.parametrize("event_type", ["qiki.radar.v1.Track"])
def test_track_headers_contain_cloudevents(event_type: str) -> None:
    publisher = RadarTrackPublisher("nats://localhost:4222")
    track = _make_track()

    headers = publisher.build_headers(track)

    assert headers["ce_specversion"] == "1.0"
    assert headers["ce_id"] == str(track.track_id)
    assert headers["ce_type"] == event_type
    assert headers["ce_source"] == "urn:qiki:faststream-bridge:radar"
    assert headers["ce_datacontenttype"] == "application/json"
    assert headers["ce_time"].endswith("Z")
    assert headers["Nats-Msg-Id"] == str(track.track_id)
