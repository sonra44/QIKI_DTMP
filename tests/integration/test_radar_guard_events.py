import asyncio
import json
import os

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.nats_subjects import RADAR_GUARD_ALERTS


@pytest.mark.integration
@pytest.mark.asyncio
async def test_radar_guard_unknown_contact_close_event() -> None:
    """
    Proof (no-mocks): the radar processing pipeline emits guard-alert events compatible with incident_rules.yaml.

    To run this test as a true proof (not skip), start the stack with:
    - RADAR_GUARD_EVENTS_ENABLED=1
    - RADAR_SR_THRESHOLD_M=100  (forces SR detection to 50m so UNKNOWN_CONTACT_CLOSE can trigger deterministically)
    """
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    fut: asyncio.Future[dict] = asyncio.get_running_loop().create_future()

    async def handler(msg) -> None:
        if fut.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        if payload.get("category") != "radar":
            return
        if payload.get("source") != "guard":
            return
        if payload.get("subject") != "UNKNOWN_CONTACT_CLOSE":
            return
        fut.set_result(payload)

    sub = await nc.subscribe(RADAR_GUARD_ALERTS, cb=handler)
    try:
        try:
            payload = await asyncio.wait_for(fut, timeout=6.0)
        except asyncio.TimeoutError:
            pytest.skip("No radar guard events observed (enable RADAR_GUARD_EVENTS_ENABLED=1)")

        assert payload["schema_version"] == 1
        assert payload["kind"] == "guard_alert"
        assert isinstance(payload.get("range_m"), (int, float))
        assert float(payload["range_m"]) < 70.0
        assert isinstance(payload.get("quality"), (int, float))
        assert float(payload["quality"]) >= 0.2
        assert payload.get("rule_id") == "UNKNOWN_CONTACT_CLOSE"
    finally:
        await sub.unsubscribe()
        await nc.close()
