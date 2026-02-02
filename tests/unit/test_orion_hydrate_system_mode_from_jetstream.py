import pytest


@pytest.mark.asyncio
async def test_orion_hydrates_mode_from_jetstream() -> None:
    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._qiki_mode = "N/A/—"

    class _FakeNatsClient:
        async def fetch_last_event_json(self, *, stream: str, subject: str):  # noqa: ANN001
            return {"mode": "FACTORY"}

    app.nats_client = _FakeNatsClient()  # type: ignore[assignment]

    await app._hydrate_qiki_mode_from_jetstream()

    assert app._qiki_mode == "FACTORY"

