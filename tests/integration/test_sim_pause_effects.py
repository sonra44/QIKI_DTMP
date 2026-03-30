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
    telemetry_latest: dict | None = None

    def now() -> float:
        return asyncio.get_running_loop().time()

    async def on_telemetry(msg) -> None:
        nonlocal telemetry_latest
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if isinstance(payload, dict):
            telemetry_latest = payload

    async def on_frame(_msg) -> None:
        t = now()
        if paused_at is not None and (t - paused_at) < 0.3:
            return
        if resumed_at is not None and (t - resumed_at) < 0.1:
            return
        frames.append(t)

    await nc.subscribe("qiki.telemetry", cb=on_telemetry)
    await nc.subscribe("qiki.radar.v1.frames", cb=on_frame)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    async def publish(cmd: CommandMessage) -> None:
        await nc.publish("qiki.commands.control", json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))
        await nc.flush(timeout=1)

    try:
        # Ensure frames flow (simulation starts explicitly).
        await publish(CommandMessage(command_name="sim.start", parameters={"speed": 1.0}, metadata=meta))

        # Wait for at least one frame while running.
        t0 = now()
        while not frames and (now() - t0) < 6.0:
            await asyncio.sleep(0.05)
        if not frames:
            power = (telemetry_latest or {}).get("power") if isinstance(telemetry_latest, dict) else None
            power = power if isinstance(power, dict) else {}
            shed = power.get("shed_loads") if isinstance(power.get("shed_loads"), list) else []
            if "radar" in shed:
                pytest.skip("Radar is currently shed by Power Plane; frames are not expected")
            pytest.fail("No radar frames observed before pause")

        paused_at = now()
        await publish(CommandMessage(command_name="sim.pause", parameters={}, metadata=meta))

        # After pause, we should not see new frames.
        frames_before = len(frames)
        await asyncio.sleep(2.5)
        assert len(frames) == frames_before, "Radar frames continued during pause"

        resumed_at = now()
        await publish(CommandMessage(command_name="sim.start", parameters={"speed": 1.0}, metadata=meta))

        # After resume, we should see at least one new frame.
        t1 = now()
        while len(frames) == frames_before and (now() - t1) < 6.0:
            await asyncio.sleep(0.05)
        assert len(frames) > frames_before, "Radar frames did not resume after start"
    finally:
        await nc.close()
