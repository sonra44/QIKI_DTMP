"""Срез staleness (M5 карты + MED пауза↔xpdr + MED консольные призраки).

M-pause-xpdr — на паузе ротация (`generate_sensor_data` → мозг) отдавала
СВЕЖЕгенерированный кадр (с новым xpdr-состоянием), а
`radar_frame_for_external_read` — замороженный последний опубликованный:
два потребителя видели разные миры (живой прогон ревью: SPOOF-… vs ALLY-…).
M5 — треки замолчавшего сенсора в мозговой WorldModel бессмертны: фантом
умершего сенсора держит вечный critical-гвард.
MED консоль — `_latest_radar_tracks` вечно живые до LOST: после sim.stop
страница РАДАР показывает призраков как живые контакты.

Пороги — единый владелец `qiki.shared.radar_freshness` (зеркало
sensor_runtime: stale 5с / dead 30с).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from qiki.services.operator_console.orion_v.radar_page_view_model import (
    build_radar_page_vm,
    format_radar_track_row_lines,
)
from qiki.services.q_core_agent.core.guard_table import GuardTable
from qiki.services.q_core_agent.core.world_model import WorldModel
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import SensorData, SensorTypeEnum
from qiki.shared.models.radar import (
    FriendFoeEnum,
    RadarDetectionModel,
    RadarFrameModel,
    TransponderModeEnum,
)
from qiki.shared.radar_freshness import (
    RADAR_TRACK_DEAD_S,
    RADAR_TRACK_STALE_S,
    classify_track_freshness,
)


# ── владелец порогов ─────────────────────────────────────────────────────────

def test_freshness_classification_bounds() -> None:
    assert classify_track_freshness(0.0) == "fresh"
    assert classify_track_freshness(RADAR_TRACK_STALE_S - 0.1) == "fresh"
    assert classify_track_freshness(RADAR_TRACK_STALE_S) == "stale"
    assert classify_track_freshness(RADAR_TRACK_DEAD_S) == "dead"
    # неизвестный возраст — честный минимум stale, не fresh и не dead
    assert classify_track_freshness(None) == "stale"
    assert classify_track_freshness(float("nan")) == "stale"


# ── M-pause-xpdr: один мир для ротации и внешнего чтения ─────────────────────

def _sim(monkeypatch) -> QSimService:
    monkeypatch.setenv("RADAR_ENABLED", "1")
    # comms_plane.enabled=True — дефолт bot_config; env-ручки у comms нет
    return QSimService(QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO"))


def _xpdr_cmd(mode: str):
    from qiki.shared.models.core import CommandMessage, MessageMetadata

    return CommandMessage(
        command_name="sim.xpdr.mode",
        parameters={"mode": mode},
        metadata=MessageMetadata(
            correlation_id=uuid4(),
            message_type="control_command",
            source="test",
            destination="q_sim_service",
        ),
    )


def _rotation_radar_frame(sim: QSimService, reads: int = 6):
    """Первый радарный SensorReading из ротации (или None)."""
    from generated.common_types_pb2 import SensorType as ProtoSensorType

    for _ in range(reads):
        reading = sim.generate_sensor_data()
        if int(reading.sensor_type) == int(ProtoSensorType.RADAR):
            return reading.radar_data
    return None


def test_paused_rotation_serves_frozen_frame_not_live_xpdr(monkeypatch) -> None:
    """Пауза = мир заморожен ДЛЯ ВСЕХ: смена xpdr на паузе не должна
    просачиваться в ротационный кадр, пока external-read отдаёт старый."""
    sim = _sim(monkeypatch)
    sim._sim_running = True
    frozen = sim.generate_radar_frame()
    sim.radar_frames.append(frozen)
    sim._sim_paused = True

    assert sim.apply_control_command(_xpdr_cmd("SPOOF")) is True

    external = sim.radar_frame_for_external_read()
    assert external is frozen  # замороженный последний опубликованный

    rotation = _rotation_radar_frame(sim)
    assert rotation is not None, "пауза не глушит радар в ротации (канон M4)"
    rotation_ids = {d.transponder_id for d in rotation.detections}
    frozen_ids = {d.transponder_id or "" for d in frozen.detections}
    assert rotation_ids == frozen_ids, (
        f"ротация на паузе несёт другой мир: {rotation_ids} != {frozen_ids} "
        "(рассинхрон пауза↔xpdr: ротация генерирует свежий кадр)"
    )
    assert not any(str(t).startswith("SPOOF-") for t in rotation_ids)


def test_paused_rotation_with_no_published_frame_gives_no_radar(monkeypatch) -> None:
    """Пауза без единого опубликованного кадра: ротация честно без радара
    (как external-read → None), а не свежая генерация замороженного мира."""
    sim = _sim(monkeypatch)
    sim._sim_running = True
    sim._sim_paused = True
    assert sim.radar_frame_for_external_read() is None
    assert _rotation_radar_frame(sim) is None


# ── M5: треки замолчавшего сенсора смертны ───────────────────────────────────

def _detection(range_m: float = 50.0) -> RadarDetectionModel:
    return RadarDetectionModel(
        range_m=range_m,
        bearing_deg=0.0,
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


def test_brain_track_survives_until_dead_threshold() -> None:
    wm = WorldModel(GuardTable(schema_version=1, rules=[]))
    wm.ingest_sensor_data(_radar_reading("radar_a", [_detection()]), now_ts=1000.0)
    assert wm.snapshot(now_ts=1000.0 + RADAR_TRACK_DEAD_S - 1.0)["active_track_count"] == 1


def test_brain_evicts_dead_sensor_ghost() -> None:
    """Аудиторский сценарий M5: сенсор замолчал — его контакт не бессмертен."""
    wm = WorldModel(GuardTable(schema_version=1, rules=[]))
    wm.ingest_sensor_data(_radar_reading("radar_a", [_detection()]), now_ts=1000.0)
    snap = wm.snapshot(now_ts=1000.0 + RADAR_TRACK_DEAD_S + 1.0)
    assert snap["active_track_count"] == 0, "фантом замолчавшего сенсора бессмертен (M5)"
    assert snap["radar_tracks"] == []
    # владение не держит висячих id после эвикции
    assert not wm._frame_derived_track_ids


def test_brain_ghost_guard_dies_with_track() -> None:
    """Аудиторский сценарий M5 целиком: контакт в guard-зоне, сенсор умер —
    critical-гвард фантома НЕ вечен (снимается эвикцией, включая чтение
    guard_results без нового ingest'а — путь agent.py)."""
    from qiki.services.q_core_agent.core.guard_table import GuardRule

    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CLOSE",
            "description": "Unknown contact within 70m.",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "iff": FriendFoeEnum.UNKNOWN,
            "max_range_m": 70.0,
            "min_quality": 0.1,
        }
    )
    wm = WorldModel(GuardTable(schema_version=1, rules=[rule]))
    wm.ingest_sensor_data(_radar_reading("radar_a", [_detection(range_m=50.0)]), now_ts=1000.0)
    assert wm.snapshot(now_ts=1001.0)["critical_guard_count"] == 1  # гвард реально стоял

    ghosts = wm.guard_results(now_ts=1000.0 + RADAR_TRACK_DEAD_S + 1.0)
    assert ghosts == [], "critical-гвард фантома пережил смерть сенсора (M5)"
    assert wm.snapshot(now_ts=1000.0 + RADAR_TRACK_DEAD_S + 2.0)["active_track_count"] == 0


def test_brain_evicts_on_wall_clock_path(monkeypatch) -> None:
    """Аудит 0047 (HIGH): боевой путь agent.py зовёт guard_results()/snapshot()
    БЕЗ now_ts (wall-clock). Инжект-only тесты маскировали бы эвикцию,
    работающую только при явном now_ts (мутация выживала)."""
    import qiki.services.q_core_agent.core.world_model as wm_module

    t0 = 1000.0
    monkeypatch.setattr(wm_module.time, "time", lambda: t0)
    wm = WorldModel(GuardTable(schema_version=1, rules=[]))
    wm.ingest_sensor_data(_radar_reading("radar_a", [_detection()]))  # без now_ts
    assert wm.snapshot()["active_track_count"] == 1

    monkeypatch.setattr(wm_module.time, "time", lambda: t0 + RADAR_TRACK_DEAD_S + 1.0)
    assert wm.guard_results() == []  # путь agent.py:183
    assert wm.snapshot()["active_track_count"] == 0  # путь agent.py:184


def test_console_systems_delegate_wires_wall_clock(monkeypatch) -> None:
    """Аудит 0047 (MED): смок покрывает кокпит-путь, а systems/target/sensors
    идут через mfd_page_content._radar_track_lines — мутация «убрать
    now_unix_s из делегата» выживала. Пин на боевой провод time.time."""
    import qiki.services.operator_console.orion_v.mfd_page_content as mfd_module

    now = 9000.0
    monkeypatch.setattr(mfd_module.time, "time", lambda: now)
    lines = mfd_module._radar_track_lines(
        {"t1": _console_track(now - (RADAR_TRACK_DEAD_S + 5.0))}
    )
    assert not any("ALLY-T1" in line for line in lines)
    assert any("скрыто устаревших: 1" in line for line in lines), lines

    lines_stale = mfd_module._radar_track_lines(
        {"t1": _console_track(now - (RADAR_TRACK_STALE_S + 2.0))}
    )
    assert any("уст" in line and "ALLY-T1" in line for line in lines_stale), lines_stale


def test_console_observation_live_track_respects_freshness(monkeypatch) -> None:
    """Аудит 0047 (MED): _find_live_public_track возвращал мёртвый трек →
    track_visible=True при «радар молчит» на странице РАДАР."""
    import pytest as _pytest

    _pytest.importorskip("textual")
    import time as time_module

    from qiki.services.operator_console.orion_v.app import OrionVApp

    app = OrionVApp()
    now = time_module.time()
    dead = _console_track(now - (RADAR_TRACK_DEAD_S + 5.0), track_id="dead1")
    fresh = _console_track(now - 1.0, track_id="fresh1")
    fresh["transponder_id"] = "ALLY-FRESH"
    app._latest_radar_tracks = {"dead1": dead, "fresh1": fresh}

    # dead по прямому id — не «live»
    track_id, track = app._find_live_public_track(qcore_track_id="dead1")
    assert track is None and track_id == ""
    # dead по метке — не матчится, fresh — матчится
    track_id, track = app._find_live_public_track(target_designator="ALLY-DEAD1")
    assert track is None
    track_id, track = app._find_live_public_track(target_designator="ALLY-FRESH")
    assert track_id == "fresh1" and track is not None


def test_brain_refreshed_track_stays_alive() -> None:
    """Живой сенсор перематчивает контакт — эвикция его не трогает."""
    wm = WorldModel(GuardTable(schema_version=1, rules=[]))
    t0 = 1000.0
    for i in range(5):
        wm.ingest_sensor_data(
            _radar_reading("radar_a", [_detection(range_m=50.0 + i)]),
            now_ts=t0 + i * (RADAR_TRACK_DEAD_S - 5.0),
        )
    last_ingest = t0 + 4 * (RADAR_TRACK_DEAD_S - 5.0)
    assert wm.snapshot(now_ts=last_ingest + 1.0)["active_track_count"] == 1


# ── MED консоль: страница РАДАР честна к возрасту треков ─────────────────────

def _console_track(received_at: float, *, track_id: str = "t1") -> dict:
    return {
        "track_id": track_id,
        "transponder_id": f"ALLY-{track_id.upper()}",
        "range_m": 1200.0,
        "bearing_deg": 42.0,
        "vr_mps": -3.0,
        "iff": 1,
        "quality": 0.9,
        "status": 1,
        "_orion_received_at_unix_s": received_at,
    }


def test_console_fresh_track_unmarked() -> None:
    now = 5000.0
    vm = build_radar_page_vm({"t1": _console_track(now - 1.0)}, now_unix_s=now)
    lines = format_radar_track_row_lines(vm)
    assert not any("уст" in line for line in lines)


def test_console_stale_track_marked() -> None:
    now = 5000.0
    vm = build_radar_page_vm(
        {"t1": _console_track(now - (RADAR_TRACK_STALE_S + 2.0))}, now_unix_s=now
    )
    lines = format_radar_track_row_lines(vm)
    assert any("уст" in line for line in lines), (
        f"устаревший трек не помечен: {lines} (консольные призраки, MED)"
    )


def test_console_dead_track_hidden_with_honest_counter() -> None:
    now = 5000.0
    vm = build_radar_page_vm(
        {"t1": _console_track(now - (RADAR_TRACK_DEAD_S + 5.0))}, now_unix_s=now
    )
    lines = format_radar_track_row_lines(vm)
    assert not any("ALLY-T1" in line for line in lines), (
        "мёртвый трек (>30с без данных) всё ещё на странице как живой"
    )
    # страница не врёт «эфир чист»: данных нет, а не «нет целей»
    assert not any("эфир чист" in line for line in lines)
    assert any("устаревш" in line or "радар молчит" in line for line in lines)


def test_console_mixed_dead_hidden_fresh_shown() -> None:
    now = 5000.0
    vm = build_radar_page_vm(
        {
            "t1": _console_track(now - (RADAR_TRACK_DEAD_S + 5.0), track_id="t1"),
            "t2": _console_track(now - 1.0, track_id="t2"),
        },
        now_unix_s=now,
    )
    lines = format_radar_track_row_lines(vm)
    assert any("ALLY-T2" in line for line in lines)
    assert not any("ALLY-T1" in line for line in lines)


def test_console_no_tracks_still_clean_air() -> None:
    vm = build_radar_page_vm({}, now_unix_s=5000.0)
    lines = format_radar_track_row_lines(vm)
    assert any("эфир чист" in line for line in lines)
