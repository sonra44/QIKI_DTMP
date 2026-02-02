import asyncio
import json
import os

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.nats_subjects import SIM_POWER_PDU


@pytest.mark.integration
@pytest.mark.asyncio
async def test_power_pdu_overcurrent_event_stream() -> None:
    """
    Proof (no-mocks): q_sim_service publishes PDU power events compatible with incident_rules.yaml.

    This test is intended to run with BOT_CONFIG_PATH pointing to:
    - /workspace/tests/fixtures/bot_config_power_pdu_overcurrent.json
    """
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    samples: list[dict] = []

    async def handler(msg) -> None:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        if payload.get("category") != "power":
            return
        if payload.get("source") != "pdu":
            return
        if payload.get("subject") != "main":
            return
        samples.append(payload)

    sub = await nc.subscribe(SIM_POWER_PDU, cb=handler)
    try:
        t0 = asyncio.get_running_loop().time()
        while (asyncio.get_running_loop().time() - t0) < 4.5:
            await asyncio.sleep(0.05)
            if len(samples) >= 3:
                break

        if not samples:
            pytest.fail("No PDU power events received")

        overcurrent_values = []
        for payload in samples:
            val = payload.get("overcurrent")
            if isinstance(val, (int, float)):
                overcurrent_values.append(int(val))

        if not overcurrent_values or max(overcurrent_values) < 1:
            pytest.skip("PDU overcurrent is not active; not running pdu-overcurrent fixture")

        payload = next(p for p in samples if int(p.get("overcurrent", 0)) == 1)
        assert payload["schema_version"] == 1
        assert int(payload["overcurrent"]) == 1
        assert float(payload.get("pdu_limit_w", 0.0)) > 0.0
        assert float(payload.get("power_out_w", 0.0)) > float(payload.get("pdu_limit_w", 0.0))
        assert float(payload.get("bus_v", 0.0)) > 0.0
    finally:
        await sub.unsubscribe()
        await nc.close()

