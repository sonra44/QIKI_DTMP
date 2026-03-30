import time

import pytest


@pytest.mark.asyncio
async def test_orion_inspector_shows_telemetry_raw_when_no_selection() -> None:
    pytest.importorskip("textual")
    from rich.console import Console

    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp

    app = OrionApp()
    app.nats_connected = True
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-1",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="info",
            payload={"schema_version": 1, "source": "q_sim_service", "power": {"soc_pct": 50.0}},
        )
    )

    class _Size:
        height = 40

    class _FakeInspector:
        size = _Size()

        def __init__(self) -> None:
            self.last = None

        def update(self, renderable) -> None:  # noqa: ANN001
            self.last = renderable

    def _fake_query_one(selector, _cls=None):  # noqa: ANN001
        if selector == "#orion-inspector":
            return inspector  # type: ignore[name-defined]
        raise LookupError(selector)

    inspector = _FakeInspector()
    app.query_one = _fake_query_one  # type: ignore[method-assign]
    app.active_screen = "system"
    app._selection_by_app.pop("system", None)

    app._refresh_inspector()

    assert inspector.last is not None
    console = Console(width=140, record=True)
    console.print(inspector.last)
    rendered = console.export_text()
    assert "schema_version" in rendered
    assert "q_sim_service" in rendered
