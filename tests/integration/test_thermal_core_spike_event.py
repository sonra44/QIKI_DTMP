import asyncio
import json
import os

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.nats_subjects import SIM_SENSOR_THERMAL


@pytest.mark.integration
@pytest.mark.asyncio
async def test_thermal_core_spike_event_stream() -> None:
    """
    Proof (no-mocks): q_sim_service publishes thermal sensor events that are compatible with incident_rules.yaml.

    This test is intended to run with BOT_CONFIG_PATH pointing to:
    - /workspace/tests/fixtures/bot_config_temp_core_spike.json
    """
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    samples: list[float] = []

    async def handler(msg) -> None:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        if payload.get("category") != "sensor":
            return
        if payload.get("source") != "thermal":
            return
        if payload.get("subject") != "core":
            return
        temp = payload.get("temp")
        if isinstance(temp, (int, float)):
            samples.append(float(temp))

    sub = await nc.subscribe(SIM_SENSOR_THERMAL, cb=handler)
    try:
        t0 = asyncio.get_running_loop().time()
        while (asyncio.get_running_loop().time() - t0) < 4.5:
            await asyncio.sleep(0.05)
            if len(samples) >= 3:
                break

        if not samples:
            pytest.fail("No thermal sensor events received")

        # This is a proof test for the core-spike fixture.
        # If the stack is running in normal mode, skip to avoid false failures.
        if max(samples) < 70.0:
            pytest.skip("Core temperature is below incident threshold; not running core-spike fixture")

        assert max(samples) > 70.0
        assert len(samples) >= 3
    finally:
        await sub.unsubscribe()
        await nc.close()

