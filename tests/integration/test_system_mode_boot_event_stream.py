import asyncio
import json
import os
import time
from uuid import uuid4

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.models.qiki_chat import QikiChatRequestV1, QikiMode
from qiki.shared.nats_subjects import EVENTS_STREAM_NAME, QIKI_INTENTS, SYSTEM_MODE_EVENT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_mode_event_is_persisted_in_jetstream() -> None:
    """Proof (no-mocks): faststream-bridge publishes system mode and it is persisted in JetStream.

    Note: for determinism we trigger a mode publish via the existing QIKI intent subject (no new contracts).
    Boot publishing uses the same publisher path and is validated by the restart checklist.
    """
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

        # Deterministic trigger: publish "mode factory" intent and assert the resulting event is persisted.
        t0 = time.time()
        req = QikiChatRequestV1(
            request_id=uuid4(),
            ts_epoch_ms=int(t0 * 1000),
            mode_hint=QikiMode.FACTORY,
            input={"text": "mode factory", "lang_hint": "auto"},
        )
        await nc.publish(QIKI_INTENTS, req.model_dump_json().encode("utf-8"))
        await nc.flush(timeout=2.0)

        deadline = time.time() + 3.0
        last_exc: Exception | None = None
        while time.time() < deadline:
            try:
                msg = await js.get_last_msg(EVENTS_STREAM_NAME, SYSTEM_MODE_EVENT)
                assert msg.subject == SYSTEM_MODE_EVENT
                assert msg.data, "empty system_mode payload"
                payload = json.loads(msg.data.decode("utf-8"))
                assert isinstance(payload, dict), "system_mode payload is not a dict"
                assert payload.get("mode") == QikiMode.FACTORY.value
                ts_epoch = payload.get("ts_epoch")
                assert isinstance(ts_epoch, (int, float))
                # Make sure we observed the event produced by this test run (not an old retained one).
                assert float(ts_epoch) >= (t0 - 0.5)
                return
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(0.2)

        pytest.fail(f"No persisted system_mode event in JetStream: {last_exc}")
    finally:
        await nc.close()
