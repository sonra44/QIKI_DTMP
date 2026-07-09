"""LOW-пакет радарной зоны (карта AUDIT_2026-07-09_POSTFIX + пост-ревью 0043).

Консольный кэп `_latest_radar_tracks` был FIFO по первой вставке: dict
сохраняет позицию ключа при обновлении, поэтому непрерывно ОБНОВЛЯЕМЫЙ трек
сидел в голове словаря и выселялся кэпом раньше редких новых — тот же класс
дефекта, что M6 в мозговой WorldModel (LRU-урок).
"""

from __future__ import annotations

import asyncio

import pytest


def _wire_track(track_id: str, *, transponder_id: str) -> dict:
    return {
        "track_id": track_id,
        "transponder_id": transponder_id,
        "status": 1,
        "range_m": 1000.0,
        "bearing_deg": 10.0,
        "vr_mps": 0.0,
        "iff": 1,
        "quality": 0.9,
    }


def test_latest_radar_tracks_cap_is_lru_not_fifo() -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.orion_v.app import (
        _MAX_LATEST_RADAR_TRACKS,
        OrionVApp,
    )

    app = OrionVApp()

    async def _run() -> None:
        live_id = "live-track"
        await app._on_track({"data": _wire_track(live_id, transponder_id="ALLY-LIVE")})
        # заполняем кэп до упора чужими треками
        for i in range(_MAX_LATEST_RADAR_TRACKS - 1):
            await app._on_track({"data": _wire_track(f"noise-{i}", transponder_id=f"N-{i}")})
        assert live_id in app._latest_radar_tracks

        # живой трек ОБНОВЛЯЕТСЯ (свежие данные) — его позиция должна освежиться
        await app._on_track({"data": _wire_track(live_id, transponder_id="ALLY-LIVE")})
        # новые треки продавливают кэп — выселяться должен давно не обновлявшийся
        for i in range(3):
            await app._on_track({"data": _wire_track(f"flood-{i}", transponder_id=f"F-{i}")})

        assert live_id in app._latest_radar_tracks, (
            "кэп выселил непрерывно обновляемый трек (FIFO по первой вставке "
            "вместо LRU) — класс дефекта M6"
        )
        assert len(app._latest_radar_tracks) <= _MAX_LATEST_RADAR_TRACKS

    asyncio.run(_run())
