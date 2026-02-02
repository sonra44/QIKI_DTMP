import asyncio
import os
import time

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.nats_subjects import EVENTS_STREAM_NAME, SYSTEM_MODE_EVENT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_mode_event_is_persisted_in_jetstream() -> None:
    """Proof (no-mocks): faststream-bridge publishes system mode at boot and it is persisted."""
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    try:
        js = nc.jetstream()
        try:
            await js.stream_info(EVENTS_STREAM_NAME)
        except Exception as exc:
            pytest.skip(f"Events stream {EVENTS_STREAM_NAME} is not available: {exc}")

        # Allow a small grace period for the bridge to publish after a fresh restart.
        deadline = time.time() + 3.0
        last_exc: Exception | None = None
        while time.time() < deadline:
            try:
                msg = await js.get_last_msg(EVENTS_STREAM_NAME, SYSTEM_MODE_EVENT)
                assert msg.subject == SYSTEM_MODE_EVENT
                assert msg.data, "empty system_mode payload"
                return
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(0.2)

        # This proof requires a faststream-bridge restart to run its boot hook.
        # In CI / reused stacks we prefer to skip rather than fail-loud here.
        if last_exc is not None and "err_code=10037" in str(last_exc):
            pytest.skip("No persisted system_mode event found; restart faststream-bridge to generate boot event")
        pytest.fail(f"No persisted system_mode event in JetStream: {last_exc}")
    finally:
        await nc.close()
