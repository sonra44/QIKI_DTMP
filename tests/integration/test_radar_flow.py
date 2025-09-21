import json
from typing import Any

import pytest

try:
    import nats  # type: ignore
except Exception:
    pytest.skip("nats not installed; skip", allow_module_level=True)

try:
    from qiki.shared.models.radar import RadarFrameModel
except Exception:
    pytest.skip("imports not available; skip", allow_module_level=True)


NATS_URL = "nats://nats:4222"
RADAR_TOPIC = "qiki.radar.v1.frames"


@pytest.mark.asyncio
async def test_receive_radar_frame_from_nats():
    nc = await nats.connect(NATS_URL)
    try:
        sub = await nc.subscribe(RADAR_TOPIC)

        # Ждём первое сообщение с кадром
        msg = await sub.next_msg(timeout=10.0)

        # Парсим JSON → Pydantic
        payload = msg.data.decode("utf-8")
        data: Any = json.loads(payload)
        frame = RadarFrameModel.model_validate(data)

        assert isinstance(frame, RadarFrameModel)
        assert len(frame.detections) >= 1
        detection = frame.detections[0]
        assert detection.transponder_mode is not None
        assert detection.transponder_id is not None or detection.transponder_on is False
    finally:
        await nc.close()
