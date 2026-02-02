import asyncio
import json
import os
from uuid import uuid4

import pytest

try:
    import nats  # type: ignore
except Exception:
    pytest.skip("nats not installed; skip", allow_module_level=True)
else:
    from nats.errors import NoServersError, TimeoutError as NatsTimeoutError  # type: ignore

from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.radar import RadarFrameModel, RadarTrackModel, RangeBand
from qiki.shared.nats_subjects import COMMANDS_CONTROL, RADAR_FRAMES, RADAR_TRACKS, RESPONSES_CONTROL


@pytest.mark.integration
@pytest.mark.asyncio
async def test_radar_lr_sr_fusion_sim_truth() -> None:
    """
    Proof (no-mocks, sim-truth):

    - q_sim_service publishes a union frame containing both LR and SR detections
      with proper per-detection range_band + id_present population.
    - faststream-bridge fuses LR+SR (same contact) and publishes an SR track
      (range_band=RR_SR, id_present=true) with ts_event/ts_ingest present.

    Note: q_sim_service starts STOPPED by default; this test explicitly sends sim.start.
    """

    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    loop = asyncio.get_running_loop()
    fut_ack: asyncio.Future[dict] = loop.create_future()
    fut_frame: asyncio.Future[dict] = loop.create_future()
    fut_track: asyncio.Future[dict] = loop.create_future()

    request_id = str(uuid4())

    async def ack_handler(msg) -> None:
        if fut_ack.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        rid = payload.get("request_id") or payload.get("requestId")
        if str(rid) != request_id:
            return
        fut_ack.set_result(payload)

    async def frame_handler(msg) -> None:
        if fut_frame.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        try:
            frame = RadarFrameModel.model_validate(payload)
        except Exception:
            return
        if len(frame.detections) < 2:
            return
        # We only care about real sim frames which have band annotations.
        if not any(det.range_band in {RangeBand.RR_LR, RangeBand.RR_SR} for det in frame.detections):
            return
        fut_frame.set_result(payload)

    async def track_handler(msg) -> None:
        if fut_track.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        try:
            track = RadarTrackModel.model_validate(payload)
        except Exception:
            return
        # We expect the published best track to be SR in the deterministic sim.
        if track.range_band != RangeBand.RR_SR:
            return
        if not isinstance(track.id_present, bool) or not track.id_present:
            return
        fut_track.set_result(payload)

    sub_ack = await nc.subscribe(RESPONSES_CONTROL, cb=ack_handler)
    sub_frame = await nc.subscribe(RADAR_FRAMES, cb=frame_handler)
    sub_track = await nc.subscribe(RADAR_TRACKS, cb=track_handler)
    try:
        await nc.flush(timeout=2.0)

        meta = MessageMetadata(
            message_id=request_id,
            message_type="control_command",
            source="test",
            destination="q_sim_service",
        )
        cmd = CommandMessage(command_name="sim.start", parameters={"speed": 1.0}, metadata=meta)
        await nc.publish(COMMANDS_CONTROL, json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))
        await nc.flush(timeout=2.0)

        ack = await asyncio.wait_for(fut_ack, timeout=6.0)
        assert bool(ack.get("ok", ack.get("success"))) is True

        frame_payload = await asyncio.wait_for(fut_frame, timeout=10.0)
        frame = RadarFrameModel.model_validate(frame_payload)
        assert frame.ts_event is not None
        assert frame.ts_ingest is not None
        assert len(frame.detections) >= 2

        lr = next(det for det in frame.detections if det.range_band == RangeBand.RR_LR)
        sr = next(det for det in frame.detections if det.range_band == RangeBand.RR_SR)

        assert lr.id_present is False
        assert lr.transponder_id is None

        assert sr.id_present is True
        assert sr.transponder_id is not None

        track_payload = await asyncio.wait_for(fut_track, timeout=12.0)
        track = RadarTrackModel.model_validate(track_payload)
        assert track.ts_event is not None
        assert track.ts_ingest is not None
        assert track.range_band == RangeBand.RR_SR
        assert track.id_present is True
        assert track.transponder_id is not None

    finally:
        await sub_ack.unsubscribe()
        await sub_frame.unsubscribe()
        await sub_track.unsubscribe()
        await nc.drain()
        await nc.close()

