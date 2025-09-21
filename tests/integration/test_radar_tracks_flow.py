import json
from typing import Any

import pytest

try:
    import nats  # type: ignore
except Exception:
    pytest.skip("nats not installed; skip", allow_module_level=True)

try:
    from qiki.shared.models.radar import RadarTrackModel
except Exception:
    pytest.skip("imports not available; skip", allow_module_level=True)


NATS_URL = "nats://nats:4222"
TRACKS_TOPIC = "qiki.radar.v1.tracks"


@pytest.mark.asyncio
async def test_receive_radar_track_from_nats():
    nc = await nats.connect(NATS_URL)
    try:
        sub = await nc.subscribe(TRACKS_TOPIC)
        msg = await sub.next_msg(timeout=15.0)

        payload = msg.data.decode("utf-8")
        data: Any = json.loads(payload)
        track = RadarTrackModel.model_validate(data)

        assert isinstance(track, RadarTrackModel)
        assert track.quality >= 0.0
        assert track.status is not None
        assert track.transponder_mode is not None
    finally:
        await nc.close()
