import asyncio
import json
import os
from pathlib import Path

import nats
import pytest
from nats.errors import NoServersError, TimeoutError as NatsTimeoutError

from qiki.shared.nats_subjects import SIM_POWER_PDU
from qiki.shared.record_replay import record_jsonl, replay_jsonl


def _iter_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


@pytest.mark.integration
@pytest.mark.asyncio
async def test_record_replay_reproduces_incident_trigger_event(tmp_path: Path) -> None:
    """
    Proof (P0): record + replay an *incident-triggering* event deterministically.

    This does not introduce any v2 contracts: replay publishes into a subject prefix for isolation.
    The event chosen is `qiki.events.v1.power.pdu` which drives the POWER_PDU_OVERCURRENT rule.

    Intended run mode:
    - Start stack with BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_power_pdu_overcurrent.json
    """
    nats_url = os.getenv("NATS_URL", "nats://127.0.0.1:4222")
    try:
        nc = await nats.connect(nats_url, connect_timeout=1)
    except (NoServersError, NatsTimeoutError, OSError) as exc:
        pytest.skip(f"NATS is not available at {nats_url}: {exc}")

    out_path = tmp_path / "incident_capture.jsonl"
    try:
        result = await record_jsonl(
            nats_url=nats_url,
            subjects=[SIM_POWER_PDU],
            duration_s=2.5,
            output_path=out_path,
        )
        counts = (result or {}).get("counts") if isinstance(result, dict) else None
        assert isinstance(counts, dict)
        assert int(counts.get("event", 0)) >= 1, "No power.pdu events recorded"

        rows = _iter_jsonl(out_path)
        recorded = [
            r.get("data")
            for r in rows
            if r.get("type") == "event" and r.get("subject") == SIM_POWER_PDU and isinstance(r.get("data"), dict)
        ]
        if not recorded:
            pytest.fail("No power.pdu events found in JSONL payloads")

        incident_trigger = next((p for p in recorded if int(p.get("overcurrent", 0)) == 1), None)
        if incident_trigger is None:
            pytest.skip("PDU overcurrent is not active; not running pdu-overcurrent fixture")

        got: list[dict] = []
        done: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

        async def on_replayed(msg) -> None:
            try:
                payload = json.loads(msg.data.decode("utf-8"))
            except Exception:
                return
            if not isinstance(payload, dict):
                return
            if int(payload.get("overcurrent", 0)) != 1:
                return
            got.append(payload)
            if not done.done():
                done.set_result(True)

        sub = await nc.subscribe(f"replay.{SIM_POWER_PDU}", cb=on_replayed)
        try:
            await replay_jsonl(
                nats_url=nats_url,
                input_path=out_path,
                speed=50.0,
                subject_prefix="replay",
                no_timing=True,
            )
            await asyncio.wait_for(done, timeout=3.0)
        finally:
            await sub.unsubscribe()

        replayed = got[-1]
        for k in ("schema_version", "category", "source", "subject", "overcurrent"):
            assert replayed.get(k) == incident_trigger.get(k)
    finally:
        await nc.close()

