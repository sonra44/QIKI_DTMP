import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pytest

import qiki.services.operator_console.main_orion as main_orion
from qiki.services.operator_console.main_orion import OrionApp


@pytest.mark.asyncio
async def test_record_start_and_stop_creates_and_cancels_task(monkeypatch: pytest.MonkeyPatch) -> None:
    app = OrionApp()
    app.nats_client = cast(Any, SimpleNamespace(url="nats://example:4222"))

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def fake_record_jsonl(**_: object) -> dict[str, object]:
        started.set()
        try:
            await asyncio.sleep(60)
            return {"published": 0}
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(main_orion, "record_jsonl", fake_record_jsonl)

    await app._run_command("record start /tmp/qiki_test_record.jsonl 60")
    assert app._record_task is not None
    await asyncio.wait_for(started.wait(), timeout=1.0)

    await app._run_command("record stop")
    task = app._record_task
    assert task is not None
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)
    await asyncio.wait_for(cancelled.wait(), timeout=1.0)
    assert app._record_task is None


@pytest.mark.asyncio
async def test_replay_start_and_stop_creates_and_cancels_task(monkeypatch: pytest.MonkeyPatch) -> None:
    app = OrionApp()
    app.nats_client = cast(Any, SimpleNamespace(url="nats://example:4222"))

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def fake_replay_jsonl(**_: object) -> dict[str, object]:
        started.set()
        try:
            await asyncio.sleep(60)
            return {"published": 0}
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(main_orion, "replay_jsonl", fake_replay_jsonl)

    await app._run_command("replay /tmp/qiki_test_replay.jsonl speed=1.0")
    assert app._replay_task is not None
    await asyncio.wait_for(started.wait(), timeout=1.0)

    await app._run_command("replay stop")
    task = app._replay_task
    assert task is not None
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)
    await asyncio.wait_for(cancelled.wait(), timeout=1.0)
    assert app._replay_task is None


@pytest.mark.asyncio
async def test_replay_parses_speed_prefix_and_no_timing(monkeypatch: pytest.MonkeyPatch) -> None:
    app = OrionApp()
    app.nats_client = cast(Any, SimpleNamespace(url="nats://example:4222"))

    called = asyncio.Event()
    captured: dict[str, object] = {}

    async def fake_replay_jsonl(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        called.set()
        return {"published": 1}

    monkeypatch.setattr(main_orion, "replay_jsonl", fake_replay_jsonl)

    await app._run_command("replay /tmp/session.jsonl speed=2.5 prefix=lab no_timing")
    await asyncio.wait_for(called.wait(), timeout=1.0)

    assert captured.get("nats_url") == "nats://example:4222"
    assert captured.get("input_path") == "/tmp/session.jsonl"
    assert captured.get("speed") == 2.5
    assert captured.get("subject_prefix") == "lab"
    assert captured.get("no_timing") is True
