import asyncio
import json
import os

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.nats_subjects import EVENTS_STREAM_NAME, SIM_SENSOR_THERMAL_TRIP


@pytest.mark.integration
@pytest.mark.asyncio
async def test_thermal_core_trip_event_stream() -> None:
    """
    Proof (no-mocks): q_sim_service emits a thermal trip edge event compatible with incident_rules.yaml.

    This test is intended to run with BOT_CONFIG_PATH pointing to:
    - /workspace/tests/fixtures/bot_config_temp_core_trip.json
    """
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    try:
        # This is an edge event that can happen before the test subscribes, so use JetStream.
        js = nc.jetstream()
        try:
            msg = await js.get_last_msg(EVENTS_STREAM_NAME, SIM_SENSOR_THERMAL_TRIP)
        except Exception:
            pytest.skip("No thermal trip events in JetStream; not running core-trip fixture")

        payload = json.loads(msg.data.decode("utf-8"))
        if not isinstance(payload, dict):
            pytest.fail("Invalid thermal trip payload")

        if payload.get("category") != "sensor" or payload.get("source") != "thermal" or payload.get("subject") != "core":
            pytest.skip("Last thermal trip event is not for core; not running core-trip fixture")

        assert payload["schema_version"] == 1
        assert payload["kind"] == "thermal_trip"
        assert int(payload["tripped"]) == 1
        assert float(payload["temp"]) >= float(payload.get("trip_c", 0.0))
    finally:
        await nc.close()
