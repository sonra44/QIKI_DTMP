import logging

import pytest

from qiki.services.q_bios_service.nats_publisher import NatsJsonPublisher


@pytest.mark.asyncio
async def test_nats_publisher_close_logs_exceptions(caplog) -> None:
    class DummyNc:
        async def drain(self) -> None:
            raise RuntimeError("drain boom")

        async def close(self) -> None:
            raise RuntimeError("close boom")

    caplog.set_level(logging.DEBUG)

    pub = NatsJsonPublisher(nats_url="nats://example:4222")
    pub._nc = DummyNc()  # type: ignore[assignment]

    await pub.close()

    messages = {r.message for r in caplog.records}
    assert "bios_nats_publisher_drain_failed" in messages
    assert "bios_nats_publisher_close_failed" in messages

