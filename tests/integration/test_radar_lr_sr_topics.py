import asyncio
import os

import pytest
import nats
from nats.errors import TimeoutError

@pytest.mark.asyncio
async def test_radar_lr_sr_topics():
    nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    nc = await nats.connect(nats_url)
    lr_future = asyncio.Future()
    sr_future = asyncio.Future()
    union_future = asyncio.Future()

    async def lr_cb(msg):
        if not lr_future.done():
            lr_future.set_result(msg)

    async def sr_cb(msg):
        if not sr_future.done():
            sr_future.set_result(msg)

    async def union_cb(msg):
        # We need two messages for the union topic
        if not union_future.done():
            union_future.set_result(msg)

    await nc.subscribe("qiki.radar.v1.frames.lr", cb=lr_cb)
    await nc.subscribe("qiki.radar.v1.tracks.sr", cb=sr_cb)
    await nc.subscribe("qiki.radar.v1.frames", cb=union_cb)

    # The test will implicitly wait for the q-sim-service to generate data
    # that crosses the SR threshold.

    try:
        lr_msg = await asyncio.wait_for(lr_future, timeout=10.0)
        sr_msg = await asyncio.wait_for(sr_future, timeout=10.0)
        union_msg = await asyncio.wait_for(union_future, timeout=10.0)

        assert lr_msg is not None
        assert sr_msg is not None
        assert union_msg is not None

        assert lr_msg.headers['x-range-band'] == 'RR_LR'
        assert sr_msg.headers['x-range-band'] == 'RR_SR'
        assert union_msg.headers['x-range-band'] == 'RR_UNSPECIFIED'

    except TimeoutError:
        pytest.fail("Timeout waiting for NATS messages")

    finally:
        await nc.close()
