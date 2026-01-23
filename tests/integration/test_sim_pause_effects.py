import asyncio
import json
import os

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.models.core import CommandMessage, MessageMetadata


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sim_pause_stops_radar_frames_and_start_resumes() -> None:
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    frames: list[float] = []
    paused_at: float | None = None
    resumed_at: float | None = None

    def now() -> float:
        return asyncio.get_running_loop().time()

    async def on_frame(_msg) -> None:
        t = now()
        if paused_at is not None and (t - paused_at) < 0.3:
            return
        if resumed_at is not None and (t - resumed_at) < 0.1:
            return
        frames.append(t)

    await nc.subscribe("qiki.radar.v1.frames", cb=on_frame)

    try:
        # Wait for at least one frame while running.
        t0 = now()
        while not frames and (now() - t0) < 5.0:
            await asyncio.sleep(0.05)
        assert frames, "No radar frames observed before pause"

        meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

        paused_at = now()
        pause_cmd = CommandMessage(command_name="sim.pause", parameters={}, metadata=meta)
        await nc.publish("qiki.commands.control", json.dumps(pause_cmd.model_dump(mode="json")).encode("utf-8"))

        # After pause, we should not see new frames.
        frames_before = len(frames)
        await asyncio.sleep(2.5)
        assert len(frames) == frames_before, "Radar frames continued during pause"

        resumed_at = now()
        start_cmd = CommandMessage(command_name="sim.start", parameters={"speed": 1.0}, metadata=meta)
        await nc.publish("qiki.commands.control", json.dumps(start_cmd.model_dump(mode="json")).encode("utf-8"))

        # After resume, we should see at least one new frame.
        t1 = now()
        while len(frames) == frames_before and (now() - t1) < 5.0:
            await asyncio.sleep(0.05)
        assert len(frames) > frames_before, "Radar frames did not resume after start"
    finally:
        await nc.close()
