import asyncio
import json
import os

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.telemetry import TelemetrySnapshotModel


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sim_start_accepts_speed_multiplier() -> None:
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    telemetry_latest: dict | None = None

    async def on_telemetry(msg) -> None:
        nonlocal telemetry_latest
        try:
            payload = json.loads(msg.data.decode("utf-8"))
            telemetry_latest = TelemetrySnapshotModel.normalize_payload(payload)
        except Exception:
            return

    await nc.subscribe("qiki.telemetry", cb=on_telemetry)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    async def publish(cmd: CommandMessage) -> None:
        await nc.publish("qiki.commands.control", json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))
        await nc.flush(timeout=1)

    async def wait_for(predicate, *, timeout_s: float = 6.0) -> dict:
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            if telemetry_latest is not None and predicate(telemetry_latest):
                return telemetry_latest
            await asyncio.sleep(0.05)
        raise AssertionError("Timeout waiting for telemetry condition")

    try:
        speed = 2.0
        await publish(CommandMessage(command_name="sim.start", parameters={"speed": speed}, metadata=meta))

        await wait_for(
            lambda t: (t.get("sim_state") or {}).get("fsm_state") == "RUNNING"
            and abs(float((t.get("sim_state") or {}).get("speed", 0.0)) - speed) < 1e-6,
            timeout_s=8.0,
        )

        # Cleanup: restore normal speed.
        await publish(CommandMessage(command_name="sim.start", parameters={"speed": 1.0}, metadata=meta))
        await wait_for(lambda t: abs(float((t.get("sim_state") or {}).get("speed", 0.0)) - 1.0) < 1e-6)
    finally:
        await nc.close()
