"""Этап 6 live-smoke: страница РАДАР на F1 против живого NATS.

1. STOPPED-мир: левый MFD (дефолт «radar») показывает «эфир чист | охват 360°».
2. Публикация wire-трека (RadarTrackModel.model_dump(mode="json"), енумы int)
   в qiki.radar.v1.tracks → строка трека с пеленгом/IFF/риском (derived).
3. Тот же track_id со status=3 (LOST int) → трек исчезает (фикс эвикции живьём).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

import nats
from textual.widgets import Static

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.shared.models.radar import (
    FriendFoeEnum,
    RadarTrackModel,
    RadarTrackStatusEnum,
    TransponderModeEnum,
)

TRACKS_SUBJECT = os.getenv("RADAR_TRACKS_SUBJECT", "qiki.radar.v1.tracks")

# Рядом живёт консоль оператора с durable-consumer'ом — второй инстанс с тем же
# durable ловит «consumer is already bound» и остаётся глухим (известный каветт).
# Пустой durable => эфемерная подписка (авточистка, без конфликта).
os.environ["RADAR_TRACKS_DURABLE"] = ""


def _wire_track(track_id, *, status: RadarTrackStatusEnum) -> dict:
    return RadarTrackModel(
        track_id=track_id,
        iff=FriendFoeEnum.FRIEND,
        transponder_on=True,
        transponder_mode=TransponderModeEnum.ON,
        transponder_id="ALLY-SMK001",
        quality=0.91,
        status=status,
        range_m=1200.0,
        bearing_deg=42.0,
        elev_deg=0.0,
        vr_mps=-12.0,
        snr_db=20.0,
        rcs_dbsm=1.0,
        age_s=1.0,
        timestamp=datetime.now(UTC),
    ).model_dump(mode="json")


async def _publish(payload: dict) -> None:
    options: dict = {}
    token = os.getenv("NATS_TOKEN", "").strip()
    if token:
        options["token"] = token
    nc = await nats.connect(os.getenv("NATS_URL", "nats://nats:4222"), **options)
    await nc.publish(TRACKS_SUBJECT, json.dumps(payload).encode("utf-8"))
    await nc.flush()
    await nc.close()


async def _left_mfd_text(app: OrionVApp) -> str:
    return app.query_one("#orionv-mfd-left-screen", Static).render().plain


async def _wait_for(app, pilot, predicate, *, timeout_s: float = 12.0, label: str = "") -> str:
    deadline = asyncio.get_event_loop().time() + timeout_s
    text = ""
    while asyncio.get_event_loop().time() < deadline:
        await pilot.pause()
        text = await _left_mfd_text(app)
        if predicate(text):
            return text
        await asyncio.sleep(0.4)
    raise AssertionError(f"не дождались: {label}\n--- последний экран:\n{text}")


async def main() -> int:
    app = OrionVApp()
    async with app.run_test(size=(180, 50)) as pilot:
        for _ in range(40):
            await pilot.pause()
            if app._nats_client.connection_state == "connected":
                break
            await asyncio.sleep(0.25)
        assert app._nats_client.connection_state == "connected", "нет NATS"

        # Эфемерный consumer получает историю стрима (deliver=all) — дать ей
        # осесть и очистить буфер: проверяем именно ПУСТОЙ эфир.
        await asyncio.sleep(2.5)
        await pilot.pause()
        app._latest_radar_tracks.clear()
        await _wait_for(app, pilot, lambda t: "эфир чист | охват 360°" in t, label="эфир чист при STOPPED")
        print("[smoke] STOPPED: «эфир чист | охват 360° | режим: НАВИГАЦИЯ» ✓")

        track_id = uuid4()
        await _publish(_wire_track(track_id, status=RadarTrackStatusEnum.TRACKED))
        text = await _wait_for(
            app,
            pilot,
            lambda t: "ALLY-SMK001" in t and "IFF FRND" in t and "(derived)" in t,
            label="строка трека с IFF и derived-риском",
        )
        row = next(line for line in text.splitlines() if "ALLY-SMK001" in line)
        print(f"[smoke] трек на странице РАДАР: {row.strip()}")
        assert "пеленг 042°" in row and "дальн 1200 м" in row and "скор -12.0 м/с" in row

        await _publish(_wire_track(track_id, status=RadarTrackStatusEnum.LOST))
        await _wait_for(
            app,
            pilot,
            lambda t: "ALLY-SMK001" not in t,
            label="LOST(int) выселяет трек",
        )
        print("[smoke] LOST(status=3) выселил трек — эвикция жива ✓")
    print("[smoke] Этап 6 PASS: страница РАДАР честна на живом стеке")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
