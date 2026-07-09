"""Срез «радар-честность-2» карты AUDIT_2026-07-09_POSTFIX.md: M4, M6, LOW-владение.

M4 — ротация сенсоров не кормит мозг радаром у остановленного/обесточенного
сима (вторая половина 0.9: tick() при STOPPED всё равно гоняет step(0.0)).
M6 — эвикция сенсоров в мозговой WorldModel — LRU, а не FIFO: живой сенсор
не выселяется под флудом «плавающих» sensor_id.
LOW — пустой кадр своего сенсора освобождает слот владения (owned ⊆ живые).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from generated.common_types_pb2 import SensorType as ProtoSensorType
from qiki.services.q_core_agent.core.guard_table import GuardTable
from qiki.services.q_core_agent.core.world_model import WorldModel
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
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


def _sim(monkeypatch) -> QSimService:
    monkeypatch.setenv("RADAR_ENABLED", "1")
    return QSimService(QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO"))


def _rotation_types(sim: QSimService, reads: int = 6) -> set[int]:
    return {int(sim.generate_sensor_data().sensor_type) for _ in range(reads)}


# ── M4: ротация честна к состоянию сима ──────────────────────────────────────

def test_rotation_gives_no_radar_while_stopped(monkeypatch) -> None:
    """Канон: сим стартует STOPPED — контактов до sim.start быть не может,
    в том числе через GetSensorData-ротацию (не только GetRadarFrame)."""
    sim = _sim(monkeypatch)
    assert not sim._sim_running  # канонное стартовое состояние
    assert int(ProtoSensorType.RADAR) not in _rotation_types(sim)


def test_rotation_gives_no_radar_when_unpowered(monkeypatch) -> None:
    """Обесточка (power shedding): radar_allowed=False глушит и ротацию."""
    sim = _sim(monkeypatch)
    sim._sim_running = True
    sim.world_model.radar_allowed = False
    assert int(ProtoSensorType.RADAR) not in _rotation_types(sim)


def test_rotation_gives_radar_when_running_and_powered(monkeypatch) -> None:
    sim = _sim(monkeypatch)
    sim._sim_running = True
    sim.world_model.radar_allowed = True
    assert int(ProtoSensorType.RADAR) in _rotation_types(sim)


# ── M6: эвикция сенсоров — LRU, живой сенсор не выселяется под флудом ────────

def test_live_sensor_survives_rogue_sensor_flood() -> None:
    """Аудиторский кейс: живой сенсор с ДРЕЙФУЮЩИМ контактом (кадры не
    перематчиваются, в наборе владения копятся висячие id) держит ключ на
    старой позиции FIFO и выселяется флудом раньше свежих rogue-ключей."""
    wm = WorldModel(GuardTable(schema_version=1, rules=[]))

    identity_breaks = 0
    for i in range(30):
        # живой сенсор говорит КАЖДЫЙ раунд, контакт дрейфует вне матч-порога
        wm.ingest_sensor_data(
            _radar_reading("radar_live", [_detection(range_m=50.0 + i * 3000.0, bearing_deg=(i * 11) % 360)])
        )
        # флуд «плавающих» sensor_id (uuid-на-кадр), далеко от live-зоны
        wm.ingest_sensor_data(
            _radar_reading(f"rogue-{i}", [_detection(range_m=400000.0 + i * 5000.0, bearing_deg=(i * 37) % 360)])
        )
        # непрерывность: контакт сенсора, говорившего в ЭТОМ раунде, жив
        live_alive = any(track["range_m"] < 400000.0 for track in wm.snapshot()["radar_tracks"])
        if not live_alive:
            identity_breaks += 1

    assert identity_breaks == 0, (
        f"живой сенсор выселялся флудом {identity_breaks} раз (FIFO вместо LRU): "
        "разрыв идентичности трека + перевыпуск гвардов"
    )


# ── LOW: пустой кадр своего сенсора освобождает слот владения ────────────────

def test_empty_own_frame_releases_ownership_slot() -> None:
    wm = WorldModel(GuardTable(schema_version=1, rules=[]))

    wm.ingest_sensor_data(_radar_reading("radar_a", [_detection()]))
    assert wm.snapshot()["active_track_count"] == 1

    wm.ingest_sensor_data(_radar_reading("radar_a", []))
    assert wm.snapshot()["active_track_count"] == 0
    # инвариант owned ⊆ живые: пустой набор не занимает слот предохранителя
    assert "radar_a" not in wm._frame_derived_track_ids
