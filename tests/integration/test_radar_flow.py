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
        RadarFrameModel,
        RangeBand,
        TransponderModeEnum,
    )
except Exception:
    pytest.skip("imports not available; skip", allow_module_level=True)


NATS_URL = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
RADAR_TOPIC = "qiki.radar.v1.frames"


@pytest.mark.asyncio
async def test_receive_radar_frame_from_nats():
    try:
        nc = await nats.connect(NATS_URL, connect_timeout=1)
    except (NoServersError, TimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {NATS_URL}: {exc}")
    try:
        sub = await nc.subscribe(RADAR_TOPIC)

        # Публикуем тестовый кадр сразу после подписки
        frame = RadarFrameModel(
            sensor_id=uuid4(),
            detections=[
                {
                    "range_m": 10.0,
                    "bearing_deg": 45.0,
                    "elev_deg": 1.0,
                    "vr_mps": 2.0,
                    "snr_db": 20.0,
                    "rcs_dbsm": 1.0,
                    "transponder_on": True,
                    "transponder_mode": TransponderModeEnum.ON,
                    "transponder_id": "ABC123",
                    "range_band": RangeBand.RR_SR,
                    "id_present": True,
                }
            ],
        )
        await nc.publish(RADAR_TOPIC, frame.model_dump_json().encode("utf-8"))

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
