import json
import os
from typing import Any
from uuid import uuid4

import pytest

try:
    import nats  # type: ignore
except Exception:
    pytest.skip("nats not installed; skip", allow_module_level=True)
else:
    from nats.errors import NoServersError, TimeoutError  # type: ignore

try:
    from qiki.shared.models.radar import (
        RadarTrackModel,
        FriendFoeEnum,
        ObjectTypeEnum,
        RadarTrackStatusEnum,
        TransponderModeEnum,
    )
except Exception:
    pytest.skip("imports not available; skip", allow_module_level=True)


NATS_URL = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
TRACKS_TOPIC = "qiki.radar.v1.tracks"


@pytest.mark.asyncio
async def test_receive_radar_track_from_nats():
    try:
        nc = await nats.connect(NATS_URL, connect_timeout=1)
    except (NoServersError, TimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {NATS_URL}: {exc}")
    try:
        sub = await nc.subscribe(TRACKS_TOPIC)

        track = RadarTrackModel(
            track_id=uuid4(),
            object_type=ObjectTypeEnum.SHIP,
            iff=FriendFoeEnum.FRIEND,
            range_m=500.0,
            bearing_deg=30.0,
            elev_deg=0.0,
            vr_mps=1.0,
            snr_db=15.0,
            rcs_dbsm=2.5,
            quality=0.9,
            status=RadarTrackStatusEnum.TRACKED,
            transponder_mode=TransponderModeEnum.ON,
            transponder_on=True,
        )
        await nc.publish(TRACKS_TOPIC, track.model_dump_json().encode("utf-8"))
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
