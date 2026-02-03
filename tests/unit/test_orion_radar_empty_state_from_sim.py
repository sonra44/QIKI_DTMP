import time

import pytest


def _sample_payload(*, fsm_state: str) -> dict:
    return {
        "schema_version": 1,
        "source": "q_sim_service",
        "timestamp": "2026-02-03T00:00:00.000Z",
        "ts_unix_ms": 1770076800000,
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "velocity": 0.0,
        "heading": 0.0,
        "attitude": {"roll_rad": 0.0, "pitch_rad": 0.0, "yaw_rad": 0.0},
        "battery": 50.0,
        "hull": {"integrity": 100.0},
        "power": {"soc_pct": 50.0, "power_in_w": 0.0, "power_out_w": 0.0, "bus_v": 28.0, "bus_a": 0.0},
        "thermal": {"nodes": [{"id": "core", "temp_c": 20.0}]},
        "radiation_usvh": 0.0,
        "temp_external_c": -60.0,
        "temp_core_c": 20.0,
        "sim_state": {"running": fsm_state.upper() == "RUNNING", "paused": False, "speed": 1.0, "fsm_state": fsm_state},
    }


@pytest.mark.asyncio
async def test_orion_radar_empty_when_stopped_is_not_na() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp
    from qiki.services.operator_console.ui import i18n as I18N

    app = OrionApp()

    captured: dict[str, list[str]] = {}

    class _FakeDataTable:
        id = "radar-table"

        def clear(self) -> None:
            return

        def add_row(self, *cells, key: str | None = None) -> None:  # noqa: ANN001
            if key is not None:
                captured[str(key)] = [str(c) for c in cells]

    def _fake_query_one(selector, _cls=None):  # noqa: ANN001
        if selector == "#radar-table":
            return _FakeDataTable()
        raise LookupError(selector)

    app.query_one = _fake_query_one  # type: ignore[method-assign]
    app._tracks_by_id = {}
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-1",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="info",
            payload=_sample_payload(fsm_state="STOPPED"),
        )
    )

    app._render_tracks_table()

    assert "seed" in captured
    cells = captured["seed"]
    # columns: Track, Status, Range, Bearing, Vr, Q, Info (7)
    assert len(cells) == 7
    assert cells[1] == I18N.bidi("Stopped", "Остановлено")
    assert "start" in cells[-1].lower() or "запуст" in cells[-1].lower()


@pytest.mark.asyncio
async def test_orion_radar_empty_when_running_shows_no_tracks() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp
    from qiki.services.operator_console.ui import i18n as I18N

    app = OrionApp()

    captured: dict[str, list[str]] = {}

    class _FakeDataTable:
        id = "radar-table"

        def clear(self) -> None:
            return

        def add_row(self, *cells, key: str | None = None) -> None:  # noqa: ANN001
            if key is not None:
                captured[str(key)] = [str(c) for c in cells]

    def _fake_query_one(selector, _cls=None):  # noqa: ANN001
        if selector == "#radar-table":
            return _FakeDataTable()
        raise LookupError(selector)

    app.query_one = _fake_query_one  # type: ignore[method-assign]
    app._tracks_by_id = {}
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-1",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="info",
            payload=_sample_payload(fsm_state="RUNNING"),
        )
    )

    app._render_tracks_table()

    assert "seed" in captured
    cells = captured["seed"]
    assert len(cells) == 7
    assert cells[1] == I18N.bidi("No tracks", "Треков нет")
    assert I18N.NO_TRACKS_YET in cells[-1]

