"""Блок 0, этап 2 «радар»: refresh-ротация, per-sensor треки, гейт GetRadarFrame.

По `02_BLOCK0_DEFECT_BASELINE.md` (0.1/0.2/0.9) и `08_VERIFICATION_PLAN.md`
(этап 2). Кросс-сенсорная непрерывность идентичности трека (спуф-тест в
test_radar_guards.py:207) — сохраняемый контракт: матчинг глобальный,
сносятся только треки своего сенсора.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import grpc

from generated.q_sim_api_pb2 import GetRadarFrameRequest
from qiki.services.q_core_agent.core.agent import QCoreAgent
from qiki.services.q_core_agent.core.guard_table import GuardTable
from qiki.services.q_core_agent.core.interfaces import IDataProvider
from qiki.services.q_core_agent.core.world_model import WorldModel
from qiki.services.q_sim_service.grpc_server import QSimAPIService
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QCoreAgentConfig, QSimServiceConfig
from qiki.shared.models.core import SensorData, SensorTypeEnum
from qiki.shared.models.radar import (
    RadarDetectionModel,
    RadarFrameModel,
    TransponderModeEnum,
)


def _detection(range_m: float = 50.0, bearing_deg: float = 0.0) -> RadarDetectionModel:
    return RadarDetectionModel(
        range_m=range_m,
        bearing_deg=bearing_deg,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=20.0,
        rcs_dbsm=1.0,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
    )


def _radar_reading(sensor_id: str, detections: list[RadarDetectionModel]) -> SensorData:
    return SensorData(
        sensor_id=sensor_id,
        sensor_type=SensorTypeEnum.RADAR,
        radar_frame=RadarFrameModel(
            sensor_id=uuid4(),
            timestamp=datetime.now(UTC),
            detections=detections,
        ),
    )


def _sim(monkeypatch, *, radar: bool = True) -> QSimService:
    monkeypatch.setenv("RADAR_ENABLED", "1" if radar else "0")
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    return QSimService(cfg)


# ── 0.2: кадр чужого сенсора НЕ сносит все треки ─────────────────────────────

def test_empty_frame_from_other_sensor_does_not_wipe_tracks() -> None:
    wm = WorldModel(GuardTable(schema_version=1, rules=[]))

    wm.ingest_sensor_data(_radar_reading("radar_lr", [_detection()]))
    assert wm.snapshot()["active_track_count"] == 1

    # пустой кадр ДРУГОГО радара (аудит: доказано живым прогоном — сносил всё)
    wm.ingest_sensor_data(_radar_reading("radar_sr", []))
    assert wm.snapshot()["active_track_count"] == 1

    # пустой кадр СВОЕГО радара честно убирает свои треки
    wm.ingest_sensor_data(_radar_reading("radar_lr", []))
    assert wm.snapshot()["active_track_count"] == 0


def test_cross_sensor_rematch_transfers_ownership() -> None:
    """Перематч чужим сенсором переносит владение: старый хозяин пустым кадром
    трек больше не сносит, новый — сносит."""
    wm = WorldModel(GuardTable(schema_version=1, rules=[]))

    wm.ingest_sensor_data(_radar_reading("radar_lr", [_detection()]))
    track_id = wm.snapshot()["radar_tracks"][0]["track_id"]

    # тот же объект видит второй радар → идентичность сохраняется (спуф-контракт)
    wm.ingest_sensor_data(_radar_reading("radar_sr", [_detection()]))
    snap = wm.snapshot()
    assert snap["active_track_count"] == 1
    assert snap["radar_tracks"][0]["track_id"] == track_id

    # владение перенесено: пустой кадр СТАРОГО хозяина трек не трогает
    wm.ingest_sensor_data(_radar_reading("radar_lr", []))
    assert wm.snapshot()["active_track_count"] == 1

    # пустой кадр НОВОГО хозяина честно убирает трек
    wm.ingest_sensor_data(_radar_reading("radar_sr", []))
    assert wm.snapshot()["active_track_count"] == 0


# ── 0.2: фиксированный sensor_id радара в симе ───────────────────────────────

def test_sim_radar_sensor_id_stable_across_frames_and_restarts(monkeypatch) -> None:
    sim = _sim(monkeypatch)
    first = sim.generate_radar_frame()
    second = sim.generate_radar_frame()
    assert first.sensor_id == second.sensor_id  # был uuid4 на каждый кадр

    restarted = _sim(monkeypatch)  # «рестарт» сервиса
    assert restarted.generate_radar_frame().sensor_id == first.sensor_id


# ── 0.1: refresh дочитывает ротацию до радара ────────────────────────────────

def _agent() -> QCoreAgent:
    return QCoreAgent(
        QCoreAgentConfig(
            tick_interval=1,
            log_level="INFO",
            recovery_delay=1,
            proposal_confidence_threshold=0.8,
            mock_neural_proposals_enabled=False,
            grpc_server_address="localhost:50051",
        )
    )


def test_refresh_reads_rotation_until_radar() -> None:
    """Ротация сима [LIDAR→RADAR→IMU] с очередью=1: одно чтение на refresh
    теряет радар в ~2/3 случаев. Refresh обязан дочитать до радара (≤3)."""
    agent = _agent()
    readings = [
        SensorData(sensor_id="imu_main", sensor_type=SensorTypeEnum.IMU, vector_data=[0.0, 0.0, 0.0]),
        SensorData(sensor_id="lidar_front", sensor_type=SensorTypeEnum.LIDAR, scalar_data=1.0),
        _radar_reading("radar_lr", [_detection()]),
    ]
    provider = Mock(spec=IDataProvider)
    provider.get_sensor_data.side_effect = readings

    agent._ingest_sensor_data(provider)

    assert provider.get_sensor_data.call_count == 3
    assert agent.world_model.snapshot()["active_track_count"] == 1


def test_refresh_stops_early_when_radar_first() -> None:
    agent = _agent()
    provider = Mock(spec=IDataProvider)
    provider.get_sensor_data.side_effect = [
        _radar_reading("radar_lr", [_detection()]),
        SensorData(sensor_id="imu_main", sensor_type=SensorTypeEnum.IMU, vector_data=[0.0, 0.0, 0.0]),
    ]

    agent._ingest_sensor_data(provider)

    assert provider.get_sensor_data.call_count == 1  # радар пришёл — не тянем лишнее
    assert agent.world_model.snapshot()["active_track_count"] == 1


# ── 0.9: GetRadarFrame гейтится состоянием сима ──────────────────────────────

def test_radar_frame_external_read_gated_by_sim_state(monkeypatch) -> None:
    sim = _sim(monkeypatch)

    # канон: сим стартует STOPPED — контактов до sim.start быть не должно
    assert sim.radar_frame_for_external_read() is None

    sim._sim_running = True
    live = sim.radar_frame_for_external_read()
    assert live is not None and live.detections

    # пауза: мир заморожен — отдаётся последний опубликованный кадр, не свежий
    sim._append_radar_frame(live)
    sim._sim_paused = True
    frozen = sim.radar_frame_for_external_read()
    assert frozen is live

    # обесточка (power shedding): радару запрещено светить
    sim._sim_paused = False
    sim.world_model.radar_allowed = False
    assert sim.radar_frame_for_external_read() is None

    # радар выключен конфигурацией
    sim.world_model.radar_allowed = True
    sim.radar_enabled = False
    assert sim.radar_frame_for_external_read() is None


def test_grpc_get_radar_frame_fails_precondition_when_gated(monkeypatch) -> None:
    sim = _sim(monkeypatch)  # STOPPED by default
    servicer = QSimAPIService(sim)

    codes: list = []
    context = SimpleNamespace(
        set_code=lambda code: codes.append(code),
        set_details=lambda _details: None,
    )
    response = asyncio.run(servicer.GetRadarFrame(GetRadarFrameRequest(), context))

    assert grpc.StatusCode.FAILED_PRECONDITION in codes
    assert not response.HasField("frame")
