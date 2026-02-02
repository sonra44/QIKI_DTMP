import asyncio
import os
from pathlib import Path

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.record_replay import record_jsonl, replay_jsonl


@pytest.mark.integration
@pytest.mark.asyncio
async def test_record_and_replay_jsonl_round_trip(tmp_path: Path) -> None:
    """
    Proof (no-mocks): record real Phase1 telemetry+events to JSONL and replay back to NATS.

    No new parallel contracts: replay publishes into a prefix for isolation.
    """
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    out_path = tmp_path / "capture.jsonl"

    try:
        result = await record_jsonl(
            nats_url=nats_url,
            subjects=["qiki.telemetry", "qiki.events.v1.>"],
            duration_s=2.0,
            output_path=out_path,
        )

        counts = (result or {}).get("counts") if isinstance(result, dict) else None
        assert isinstance(counts, dict)
        assert int(counts.get("telemetry", 0)) >= 1, "No telemetry recorded"

        # Events can be disabled in some stack runs; skip to keep gate stable.
        if int(counts.get("event", 0)) < 1:
            pytest.skip("No events recorded; events are likely disabled in this stack run")

        telemetry_seen = 0
        event_seen = 0
        done: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

        async def on_replay_telemetry(_msg) -> None:
            nonlocal telemetry_seen
            telemetry_seen += 1
            if telemetry_seen >= 1 and event_seen >= 1 and not done.done():
                done.set_result(True)

        async def on_replay_event(_msg) -> None:
            nonlocal event_seen
            event_seen += 1
            if telemetry_seen >= 1 and event_seen >= 1 and not done.done():
                done.set_result(True)

        sub_t = await nc.subscribe("replay.qiki.telemetry", cb=on_replay_telemetry)
        sub_e = await nc.subscribe("replay.qiki.events.v1.>", cb=on_replay_event)
        try:
            await replay_jsonl(
                nats_url=nats_url,
                input_path=out_path,
                speed=10.0,
                subject_prefix="replay",
                no_timing=True,
            )
            await asyncio.wait_for(done, timeout=4.0)
            assert telemetry_seen >= 1
            assert event_seen >= 1
        finally:
            await sub_t.unsubscribe()
            await sub_e.unsubscribe()
    finally:
        await nc.close()

