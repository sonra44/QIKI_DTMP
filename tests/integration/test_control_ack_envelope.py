import asyncio
import json
import os
from uuid import uuid4

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.models.core import CommandMessage, MessageMetadata


@pytest.mark.integration
@pytest.mark.asyncio
async def test_control_ack_envelope_is_backward_compatible_and_complete() -> None:
    """
    Proof (no-mocks): q_sim_service publishes a control ACK on qiki.responses.control with:
    - version/kind/timestamp
    - requestId + request_id aliases
    - success + ok aliases
    - structured error_detail when ok=false (not asserted here; see xpdr gating test)
    """
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    req_id = uuid4()
    meta = MessageMetadata(message_type="control_command", source="integration_test", destination="q_sim_service", message_id=req_id)
    cmd = CommandMessage(command_name="sim.start", parameters={"speed": 1.0}, metadata=meta)

    fut: asyncio.Future[dict] = asyncio.get_running_loop().create_future()

    async def handler(msg) -> None:
        if fut.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        raw = payload.get("request_id") or payload.get("requestId")
        if str(raw) == str(req_id):
            fut.set_result(payload)

    sub = await nc.subscribe("qiki.responses.control", cb=handler)
    try:
        await nc.publish("qiki.commands.control", json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))
        ack = await asyncio.wait_for(fut, timeout=6.0)

        assert ack.get("version") == 1
        assert ack.get("kind") == "sim.start"

        assert ack.get("requestId") == str(req_id)
        assert ack.get("request_id") == str(req_id)

        assert ack.get("success") is True
        assert ack.get("ok") is True

        ts = ack.get("timestamp")
        assert isinstance(ts, str) and ts

        inner = ack.get("payload")
        assert isinstance(inner, dict)
        assert inner.get("command_name") == "sim.start"
        assert inner.get("status") == "applied"
    finally:
        await sub.unsubscribe()
        await nc.close()

