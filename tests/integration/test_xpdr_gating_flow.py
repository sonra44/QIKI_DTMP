import asyncio
import json
import os
from uuid import uuid4

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.models.core import CommandMessage, MessageMetadata


async def _wait_for_telemetry(nc: nats.NATS, *, timeout_s: float = 5.0) -> dict:
    fut: asyncio.Future[dict] = asyncio.get_running_loop().create_future()

    async def handler(msg) -> None:
        if fut.done():
            return
        try:
            fut.set_result(json.loads(msg.data.decode("utf-8")))
        except Exception:
            # Ignore bad payloads; keep waiting.
            return

    sub = await nc.subscribe("qiki.telemetry", cb=handler)
    try:
        return await asyncio.wait_for(fut, timeout=timeout_s)
    finally:
        await sub.unsubscribe()


async def _wait_for_control_ack(nc: nats.NATS, *, request_id: str, timeout_s: float = 5.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout_s

    while asyncio.get_running_loop().time() < deadline:
        fut: asyncio.Future[dict] = asyncio.get_running_loop().create_future()

        async def handler(msg) -> None:
            if fut.done():
                return
            try:
                payload = json.loads(msg.data.decode("utf-8"))
            except Exception:
                return
            raw = payload.get("request_id") or payload.get("requestId")
            if str(raw) == request_id:
                fut.set_result(payload)

        sub = await nc.subscribe("qiki.responses.control", cb=handler)
        try:
            return await asyncio.wait_for(fut, timeout=deadline - asyncio.get_running_loop().time())
        finally:
            await sub.unsubscribe()

    raise AssertionError("control ACK not received in time")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_xpdr_mode_command_applies_when_comms_enabled() -> None:
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    try:
        telemetry = await _wait_for_telemetry(nc)
        comms = telemetry.get("comms") or {}
        if not isinstance(comms, dict) or comms.get("enabled") is not True:
            pytest.skip("Comms plane is not enabled in this stack run")

        req_id = uuid4()
        meta = MessageMetadata(message_type="control_command", source="integration_test", destination="q_sim_service", message_id=req_id)
        cmd = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "SILENT"}, metadata=meta)
        await nc.publish("qiki.commands.control", json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))

        ack = await _wait_for_control_ack(nc, request_id=str(req_id))
        ok = ack.get("ok") if "ok" in ack else ack.get("success")
        assert ok is True

        # Prove effect in telemetry (no-mocks): mode becomes SILENT and power plane reflects it.
        t0 = asyncio.get_running_loop().time()
        while (asyncio.get_running_loop().time() - t0) < 5.0:
            telemetry = await _wait_for_telemetry(nc)
            xpdr = ((telemetry.get("comms") or {}).get("xpdr") or {})
            if isinstance(xpdr, dict) and xpdr.get("mode") == "SILENT":
                assert xpdr.get("active") is False
                assert xpdr.get("id") is None
                power = telemetry.get("power") or {}
                loads = power.get("loads_w") or {}
                assert isinstance(loads, dict)
                assert float(loads.get("transponder") or 0.0) == pytest.approx(0.0)
                break
        else:
            pytest.fail("XPDR mode did not transition to SILENT in telemetry")

        # Restore ON so this test does not leak state into other integration tests.
        req_id = uuid4()
        meta = MessageMetadata(message_type="control_command", source="integration_test", destination="q_sim_service", message_id=req_id)
        cmd = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "ON"}, metadata=meta)
        await nc.publish("qiki.commands.control", json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))

        ack = await _wait_for_control_ack(nc, request_id=str(req_id))
        ok = ack.get("ok") if "ok" in ack else ack.get("success")
        assert ok is True

        t0 = asyncio.get_running_loop().time()
        while (asyncio.get_running_loop().time() - t0) < 5.0:
            telemetry = await _wait_for_telemetry(nc)
            xpdr = ((telemetry.get("comms") or {}).get("xpdr") or {})
            if isinstance(xpdr, dict) and xpdr.get("mode") == "ON":
                assert xpdr.get("active") is True
                assert xpdr.get("id") is not None
                power = telemetry.get("power") or {}
                loads = power.get("loads_w") or {}
                assert isinstance(loads, dict)
                assert float(loads.get("transponder") or 0.0) > 0.0
                return
        pytest.fail("XPDR mode did not transition back to ON in telemetry")
    finally:
        await nc.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_xpdr_on_rejected_when_comms_disabled() -> None:
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    try:
        telemetry = await _wait_for_telemetry(nc)
        comms = telemetry.get("comms") or {}
        if not isinstance(comms, dict) or comms.get("enabled") is not False:
            pytest.skip("Comms plane is not disabled in this stack run")

        req_id = uuid4()
        meta = MessageMetadata(message_type="control_command", source="integration_test", destination="q_sim_service", message_id=req_id)
        cmd = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "ON"}, metadata=meta)
        await nc.publish("qiki.commands.control", json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))

        ack = await _wait_for_control_ack(nc, request_id=str(req_id))
        ok = ack.get("ok") if "ok" in ack else ack.get("success")
        assert ok is False
        err = ack.get("error_detail") or {}
        assert isinstance(err, dict)
        assert err.get("code") == "comms_disabled"

        # Prove sim truth is forced OFF.
        telemetry = await _wait_for_telemetry(nc)
        xpdr = ((telemetry.get("comms") or {}).get("xpdr") or {})
        assert xpdr.get("mode") == "OFF"
        assert xpdr.get("active") is False
        assert xpdr.get("id") is None
    finally:
        await nc.close()
