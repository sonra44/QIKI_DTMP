"""Этап 2 (Блок 0 «радар»): live-smoke честного радарного ingest.

Живой стек phase1 (q-sim gRPC + NATS). Проверяет на настоящем мире:

1. Гейт GetRadarFrame (0.9): STOPPED не отдаёт свежих контактов
   (FAILED_PRECONDITION), RUNNING — отдаёт кадр.
2. Стабильный sensor_id кадра (0.2): два кадра подряд — один сенсор.
3. Ротация refresh (0.1): радар доходит до потребителя в пределах бюджета
   чтений и «0 треков при живом контакте» = 0 на выборке. Проба конкурирует
   с живым мозгом за очередь глубины 1, поэтому бюджет = 2 ротации (6 чтений)
   на цикл; номинальную мозговую метрику (одиночный потребитель, ≤3 чтений)
   пинуют юниты test_block0_radar_ingest. Полный 30-мин прогон — гейт этапа 11.

Сим переводится в RUNNING канонной операторской командой `sim.start`
(qiki.commands.control) и возвращается в исходное состояние в конце.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import uuid4

import grpc

from generated.q_sim_api_pb2 import GetRadarFrameRequest
from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub
from qiki.services.q_core_agent.core.grpc_data_provider import GrpcDataProvider
from qiki.services.q_core_agent.core.guard_table import GuardTable
from qiki.services.q_core_agent.core.world_model import WorldModel
from qiki.shared.models.core import CommandMessage, MessageMetadata, SensorTypeEnum
from qiki.shared.nats_subjects import COMMANDS_CONTROL

GRPC_ADDRESS = os.getenv("QSIM_GRPC_ADDRESS", "q-sim-service:50051")
PROBE_CYCLES = int(os.getenv("PROBE_CYCLES", "12"))
# Проба делит очередь=1 с живым мозгом (он тоже читает до 3 подряд) → бюджет
# на цикл = 2 полных ротации.
READ_BUDGET = int(os.getenv("PROBE_READ_BUDGET", "6"))


def _publish_control(command_name: str) -> None:
    """Канонный операторский путь: CommandMessage → qiki.commands.control."""

    async def _run() -> None:
        import nats

        options: dict = {}
        token = os.getenv("NATS_TOKEN", "").strip()
        if token:
            options["token"] = token
        nc = await nats.connect(os.getenv("NATS_URL", "nats://nats:4222"), **options)
        cmd = CommandMessage(
            command_name=command_name,
            parameters={},
            metadata=MessageMetadata(
                correlation_id=uuid4(),
                message_type="control_command",
                source="tools.radar_track_visible_smoke",
                destination="q_sim_service",
            ),
        )
        await nc.publish(COMMANDS_CONTROL, json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))
        await nc.flush()
        await nc.close()

    asyncio.run(_run())


def _radar_frame_status(stub: QSimAPIServiceStub) -> tuple[str, object]:
    """→ ("frame", frame) | ("precondition", None) — состояние гейта 0.9."""
    try:
        response = stub.GetRadarFrame(GetRadarFrameRequest(), timeout=5.0)
        return "frame", response.frame
    except grpc.RpcError as exc:
        if exc.code() == grpc.StatusCode.FAILED_PRECONDITION:
            return "precondition", None
        raise


def main() -> int:
    channel = grpc.insecure_channel(GRPC_ADDRESS)
    stub = QSimAPIServiceStub(channel)

    status, _ = _radar_frame_status(stub)
    sim_was_stopped = status == "precondition"
    if sim_was_stopped:
        print("[smoke] сим STOPPED: GetRadarFrame честно отвечает FAILED_PRECONDITION (гейт 0.9 ✓)")
        print("[smoke] sim.start (канонная операторская команда) ...")
        _publish_control("sim.start")
        import time

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            status, frame = _radar_frame_status(stub)
            if status == "frame":
                break
            time.sleep(0.5)
        assert status == "frame", "после sim.start кадр так и не появился"
        print("[smoke] RUNNING: кадр отдаётся (гейт открылся) ✓")
    else:
        print("[smoke] сим уже RUNNING (живой мир оператора) — стоп-сторону гейта не трогаем")

    # 0.2: стабильный sensor_id между кадрами.
    # LOW-guard: FAILED_PRECONDITION здесь означает «гейт закрыт» (STOPPED
    # ИЛИ обесточка/выключенный радар) — если мир изменился между чтениями,
    # падаем с честным сообщением, а не AttributeError на None-кадре.
    status_a, frame_a = _radar_frame_status(stub)
    status_b, frame_b = _radar_frame_status(stub)
    assert status_a == status_b == "frame" and frame_a is not None and frame_b is not None, (
        "радарный гейт закрылся между кадрами (STOPPED/обесточка?) — "
        f"статусы: {status_a}/{status_b}"
    )
    sid_a, sid_b = frame_a.sensor_id.value, frame_b.sensor_id.value
    assert sid_a and sid_a == sid_b, f"sensor_id нестабилен: {sid_a} != {sid_b}"
    print(f"[smoke] sensor_id стабилен между кадрами: {sid_a} ✓")

    # 0.1: доля refresh-циклов с радаром (правило мозга: до 3 чтений до радара)
    provider = GrpcDataProvider(GRPC_ADDRESS)
    wm = WorldModel(GuardTable(schema_version=1, rules=[]))
    radar_cycles = 0
    zero_tracks_with_live_contact = 0
    reads_used: list[int] = []
    for cycle in range(PROBE_CYCLES):
        got_radar = False
        for read_no in range(1, READ_BUDGET + 1):
            sensor_data = provider.get_sensor_data()
            wm.ingest_sensor_data(sensor_data)
            if sensor_data.sensor_type == SensorTypeEnum.RADAR:
                got_radar = True
                reads_used.append(read_no)
                break
        if got_radar:
            radar_cycles += 1
            if wm.snapshot()["active_track_count"] == 0:
                zero_tracks_with_live_contact += 1
        print(f"[smoke] цикл {cycle + 1}/{PROBE_CYCLES}: радар={'да' if got_radar else 'НЕТ'}", flush=True)

    share = radar_cycles / PROBE_CYCLES
    print(
        f"[smoke] циклов с радаром: {radar_cycles}/{PROBE_CYCLES} ({share:.0%}); "
        f"чтений до радара: {reads_used}; «0 треков при живом контакте»: {zero_tracks_with_live_contact}"
    )

    if sim_was_stopped:
        print("[smoke] возвращаю сим в исходное состояние: sim.stop")
        _publish_control("sim.stop")

    assert share >= 0.95, f"доля циклов с радаром {share:.0%} < 95%"
    assert zero_tracks_with_live_contact == 0, "радар пришёл, а треков нет — снос жив"
    print("[smoke] Этап 2 PASS: радарный ingest честен на живом стеке")
    return 0


if __name__ == "__main__":
    sys.exit(main())
