"""Live-smoke среза staleness (M5 + пауза↔xpdr + консольные призраки).

A. Пауза↔xpdr на живом gRPC/NATS (rerun аудиторского прогона): RUNNING →
   PAUSED → sim.xpdr.mode SPOOF → ротация (GetSensorData) и внешнее чтение
   (GetRadarFrame) несут ОДИН замороженный кадр — SPOOF не просачивается.
B. Консоль (Pilot + живой NATS): трек виден → через >5с без данных строка
   получает пометку «уст Nс» живьём; dead-ветка (>30с) — бэкдейтом
   received_at (честный инжект, чтобы не держать смок полминуты).

Мир возвращается в STOPPED (канонное состояние).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from uuid import uuid4

import grpc
import nats
from textual.widgets import Static

from generated.q_sim_api_pb2 import GetRadarFrameRequest, GetSensorDataRequest
from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub
from generated.common_types_pb2 import SensorType as ProtoSensorType
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.models.radar import (
    FriendFoeEnum,
    RadarTrackModel,
    RadarTrackStatusEnum,
    TransponderModeEnum,
)
from qiki.shared.nats_subjects import COMMANDS_CONTROL
from qiki.shared.radar_freshness import RADAR_TRACK_DEAD_S, RADAR_TRACK_STALE_S

GRPC_ADDRESS = os.getenv("QSIM_GRPC_ADDRESS", "q-sim-service:50051")
TRACKS_SUBJECT = os.getenv("RADAR_TRACKS_SUBJECT", "qiki.radar.v1.tracks")
os.environ["RADAR_TRACKS_DURABLE"] = ""  # эфемерная подписка, без durable-конфликта


def _publish_control(command_name: str, parameters: dict | None = None) -> None:
    async def _run() -> None:
        options: dict = {}
        token = os.getenv("NATS_TOKEN", "").strip()
        if token:
            options["token"] = token
        nc = await nats.connect(os.getenv("NATS_URL", "nats://nats:4222"), **options)
        cmd = CommandMessage(
            command_name=command_name,
            parameters=parameters or {},
            metadata=MessageMetadata(
                correlation_id=uuid4(),
                message_type="control_command",
                source="tools.radar_staleness_smoke",
                destination="q_sim_service",
            ),
        )
        await nc.publish(COMMANDS_CONTROL, json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))
        await nc.flush()
        await nc.close()

    asyncio.run(_run())


def _radar_frame_status(stub: QSimAPIServiceStub):
    try:
        response = stub.GetRadarFrame(GetRadarFrameRequest(), timeout=5.0)
        return "frame", response.frame
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.FAILED_PRECONDITION:
            return "precondition", None
        raise


def _rotation_radar_ids(stub: QSimAPIServiceStub, reads: int = 9) -> set[str] | None:
    for _ in range(reads):
        reading = stub.GetSensorData(GetSensorDataRequest(), timeout=5.0).reading
        if int(reading.sensor_type) == int(ProtoSensorType.RADAR):
            return {d.transponder_id for d in reading.radar_data.detections}
    return None


def _wait_state(stub: QSimAPIServiceStub, wanted: str, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status, _ = _radar_frame_status(stub)
        if status == wanted:
            return
        time.sleep(0.5)
    raise AssertionError(f"мир не пришёл в состояние {wanted}")


def part_a_pause_xpdr() -> None:
    channel = grpc.insecure_channel(GRPC_ADDRESS)
    stub = QSimAPIServiceStub(channel)

    status, _ = _radar_frame_status(stub)
    assert status == "precondition", "смок ожидает канонный STOPPED на старте"

    _publish_control("sim.start")
    _wait_state(stub, "frame")
    time.sleep(1.5)  # дать tick'у опубликовать кадры (radar_frames непуст)

    _publish_control("sim.pause")
    time.sleep(1.0)
    _, frozen = _radar_frame_status(stub)
    assert frozen is not None, "на паузе внешнее чтение должно отдавать замороженный кадр"
    frozen_ids = {d.transponder_id for d in frozen.detections}

    _publish_control("sim.xpdr.mode", {"mode": "SPOOF"})
    time.sleep(1.0)

    rotation_ids = _rotation_radar_ids(stub)
    assert rotation_ids is not None, "пауза не должна глушить радар в ротации (канон M4)"
    _, external = _radar_frame_status(stub)
    external_ids = {d.transponder_id for d in external.detections}

    assert rotation_ids == external_ids == frozen_ids, (
        f"рассинхрон на паузе: ротация {rotation_ids} / внешнее {external_ids} / "
        f"замороженный {frozen_ids}"
    )
    assert not any(str(t).startswith("SPOOF-") for t in rotation_ids), (
        "SPOOF просочился в замороженный мир"
    )
    print(f"[smoke] ПАУЗА: ротация и внешнее чтение несут один замороженный кадр {sorted(frozen_ids)} ✓")
    print("[smoke] xpdr SPOOF на паузе НЕ просочился в кадры (рассинхрон закрыт) ✓")

    _publish_control("sim.xpdr.mode", {"mode": "ON"})
    _publish_control("sim.stop")
    _wait_state(stub, "precondition")
    print("[smoke] мир возвращён в STOPPED (FAILED_PRECONDITION) ✓")


def _wire_track(track_id) -> dict:
    return RadarTrackModel(
        track_id=track_id,
        iff=FriendFoeEnum.FRIEND,
        transponder_on=True,
        transponder_mode=TransponderModeEnum.ON,
        transponder_id="ALLY-STALE1",
        quality=0.9,
        status=RadarTrackStatusEnum.TRACKED,
        range_m=900.0,
        bearing_deg=10.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=20.0,
        rcs_dbsm=1.0,
        timestamp=datetime.now(UTC),
    ).model_dump(mode="json")


async def _publish_track(payload: dict) -> None:
    options: dict = {}
    token = os.getenv("NATS_TOKEN", "").strip()
    if token:
        options["token"] = token
    nc = await nats.connect(os.getenv("NATS_URL", "nats://nats:4222"), **options)
    await nc.publish(TRACKS_SUBJECT, json.dumps(payload).encode("utf-8"))
    await nc.flush()
    await nc.close()


async def _left_mfd_text(app) -> str:
    return app.query_one("#orionv-mfd-left-screen", Static).render().plain


async def _wait_for(app, pilot, predicate, *, timeout_s: float = 15.0, label: str = "") -> str:
    deadline = asyncio.get_event_loop().time() + timeout_s
    text = ""
    while asyncio.get_event_loop().time() < deadline:
        await pilot.pause()
        text = await _left_mfd_text(app)
        if predicate(text):
            return text
        await asyncio.sleep(0.4)
    raise AssertionError(f"не дождались: {label}\n--- последний экран:\n{text}")


async def part_b_console_staleness() -> None:
    from qiki.services.operator_console.orion_v.app import OrionVApp

    app = OrionVApp()
    async with app.run_test(size=(180, 50)) as pilot:
        for _ in range(40):
            await pilot.pause()
            if app._nats_client.connection_state == "connected":
                break
            await asyncio.sleep(0.25)
        assert app._nats_client.connection_state == "connected", "нет NATS"
        await asyncio.sleep(2.5)
        await pilot.pause()
        app._latest_radar_tracks.clear()

        await _publish_track(_wire_track(uuid4()))
        await _wait_for(app, pilot, lambda t: "ALLY-STALE1" in t, label="свежий трек виден")
        print("[smoke] консоль: свежий трек ALLY-STALE1 на странице РАДАР ✓")

        text = await _wait_for(
            app,
            pilot,
            lambda t: "ALLY-STALE1" in t and "| уст" in t,
            timeout_s=RADAR_TRACK_STALE_S + 8.0,
            label=f"пометка «уст» после {RADAR_TRACK_STALE_S:.0f}с без данных",
        )
        row = next(line for line in text.splitlines() if "ALLY-STALE1" in line)
        print(f"[smoke] живое устаревание (> {RADAR_TRACK_STALE_S:.0f}с): {row.strip()} ✓")

        # dead-ветка: бэкдейт времени приёма (честный инжект — не ждать 30с)
        for payload in app._latest_radar_tracks.values():
            payload["_orion_received_at_unix_s"] = time.time() - (RADAR_TRACK_DEAD_S + 2.0)
        text = await _wait_for(
            app,
            pilot,
            lambda t: "ALLY-STALE1" not in t and "скрыто устаревших: 1" in t,
            label="мёртвый трек скрыт с честным счётчиком",
        )
        assert "эфир чист" not in text, "страница врёт «эфир чист» при мёртвых данных"
        print("[smoke] dead-трек скрыт: «скрыто устаревших: 1», без ложного «эфир чист» ✓")


def main() -> int:
    part_a_pause_xpdr()
    asyncio.run(part_b_console_staleness())
    print("[smoke] Срез staleness PASS: пауза↔xpdr и возраст треков честны живьём")
    return 0


if __name__ == "__main__":
    sys.exit(main())
