"""Этап 6 «f1-radar-page»: страница РАДАР левого MFD — треки, риск, честная пустота.

По `03_F1_COCKPIT_SPEC.md` Z4 (+G5 из F1_GAME_FIELD_REWORK) и
`08_VERIFICATION_PLAN.md` (этап 6): строка трека
`пеленг | дальность | скорость | IFF | качество | риск(derived)`;
пусто → «эфир чист | охват 360° | режим: НАВИГАЦИЯ».
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from qiki.services.operator_console.orion_v.mfd_page_content import render_left_mfd_page
from qiki.services.operator_console.orion_v.radar_page_view_model import (
    build_radar_page_vm,
    format_radar_page_lines,
    format_radar_track_row_lines,
    iff_code,
    is_lost_status,
)
from qiki.shared.radar_risk import (
    RADAR_CPA_CRIT_DIST_M,
    RADAR_CPA_CRIT_T_S,
    classify_approach_risk,
)


def _wire_track(**overrides) -> dict:
    """Payload как с провода: RadarTrackModel.model_dump(mode="json") — енумы int."""
    payload = {
        "schema_version": 1,
        "track_id": str(uuid4()),
        "object_type": 2,
        "iff": 1,  # FRIEND
        "transponder_on": True,
        "transponder_mode": 1,
        "transponder_id": "ALLY-652D53",
        "quality": 0.91,
        "status": 2,  # TRACKED
        "range_m": 1200.0,
        "bearing_deg": 42.0,
        "elev_deg": 0.0,
        "vr_mps": -12.0,
        "snr_db": 20.0,
        "rcs_dbsm": 1.0,
        "age_s": 3.0,
    }
    payload.update(overrides)
    return payload


# ── Риск: shared-владелец порогов ────────────────────────────────────────────

def test_classify_risk_thresholds() -> None:
    assert classify_approach_risk(300.0, -20.0) == ("warn", pytest.approx(15.0))
    level, t_cpa = classify_approach_risk(100.0, -20.0)
    assert level == "crit" and t_cpa == pytest.approx(5.0)
    assert classify_approach_risk(200.0, 5.0) == ("ok", None)  # удаляется
    # медленное t_cpa, но высокая скорость сближения → warn (closing-speed)
    level, _ = classify_approach_risk(10000.0, -6.0)
    assert level == "warn"
    # граница: t_cpa < CRIT_T, но дистанция ≥ CRIT_DIST → warn, не crit
    level, t_cpa = classify_approach_risk(RADAR_CPA_CRIT_DIST_M + 50.0, -50.0)
    assert t_cpa < RADAR_CPA_CRIT_T_S and level == "warn"


# ── Строка трека: все шесть полей из wire-payload'а ──────────────────────────

def test_track_row_renders_all_six_fields() -> None:
    vm = build_radar_page_vm({"t1": _wire_track()})
    assert vm.rows and not vm.empty
    line = format_radar_track_row_lines(vm)[0]
    assert "ALLY-652D53" in line
    assert "пеленг" in line and "042" in line
    assert "дальн" in line and "1200" in line
    assert "скор" in line and "-12.0" in line
    assert "IFF FRND" in line
    assert "кач 0.91" in line
    assert "риск" in line


def test_risk_marked_derived_in_footer() -> None:
    vm = build_radar_page_vm({"t1": _wire_track(range_m=100.0, vr_mps=-20.0)})
    lines = format_radar_track_row_lines(vm)
    assert "CRIT" in lines[0] and "t_cpa" in lines[0]
    # derived-пометка одна на страницу (footer), не мусор в каждом ряду
    assert "(derived)" not in lines[0]
    assert any("derived" in line for line in lines[1:])
    # строки треков не начинаются с '#' — ui_rich красит #-буллеты в muted,
    # и главная T0-страница становилась серой (UI-ревью P1)
    assert not lines[0].startswith("#")


def test_zero_values_render_honestly() -> None:
    """0.0 — это данные, а не их отсутствие (falsy-zero через or-цепочки)."""
    vm = build_radar_page_vm({"t1": _wire_track(bearing_deg=0.0, quality=0.0)})
    row = vm.rows[0]
    assert row.bearing_deg == 0.0 and row.quality == 0.0
    line = format_radar_track_row_lines(vm)[0]
    assert "пеленг 000°" in line and "кач 0.00" in line


def test_missing_kinematics_show_unknown_risk() -> None:
    """Без range/vr риск честно «—», а не «OK (derived)»."""
    vm = build_radar_page_vm({"t1": {"track_label": "TGT-1"}})
    row = vm.rows[0]
    assert row.risk_level == "none"
    lines = format_radar_track_row_lines(vm)
    assert "риск —" in lines[0]
    assert not any("derived" in line for line in lines)  # нечего derive'ить


# ── Пустой эфир ──────────────────────────────────────────────────────────────

def test_empty_air_lines() -> None:
    vm = build_radar_page_vm({})
    assert vm.empty
    assert format_radar_track_row_lines(vm) == ["эфир чист | охват 360°"]
    page = format_radar_page_lines(vm)
    assert page[0] == "эфир чист | охват 360° | режим: НАВИГАЦИЯ"
    assert any("target-only" in line for line in page)  # честность метки режима


# ── Нормализация wire-енумов ─────────────────────────────────────────────────

def test_iff_normalization_int_and_str() -> None:
    assert iff_code(1) == "FRND"
    assert iff_code("2") == "FOE"
    assert iff_code("UNKNOWN") == "UNK"
    assert iff_code(3) == "UNK"
    assert iff_code(0) == "—"
    assert iff_code(None) == "—"


def test_lost_status_normalization() -> None:
    assert is_lost_status(3)
    assert is_lost_status("3")
    assert is_lost_status("LOST")
    assert is_lost_status("lost")
    assert not is_lost_status(2)
    assert not is_lost_status("TRACKED")
    assert not is_lost_status(None)


def test_lost_tracks_skipped_in_vm() -> None:
    vm = build_radar_page_vm({"dead": _wire_track(status=3), "live": _wire_track()})
    assert vm.total_tracks == 1 and len(vm.rows) == 1


# ── Сортировка и лимит ───────────────────────────────────────────────────────

def test_sort_crit_first_then_range_and_limit() -> None:
    tracks = {
        "far_ok": _wire_track(range_m=9000.0, vr_mps=1.0),
        "crit": _wire_track(range_m=100.0, vr_mps=-20.0),
        "near_ok": _wire_track(range_m=500.0, vr_mps=2.0),
    }
    tracks["no_kinematics"] = {"track_label": "GHOST-1"}
    vm = build_radar_page_vm(tracks)
    assert [row.risk_level for row in vm.rows[:1]] == ["crit"]
    levels = [row.risk_level for row in vm.rows]
    # неизвестный риск выше подтверждённого ok (не хоронить неопределённость)
    assert levels.index("none") < levels.index("ok")
    ok_ranges = [row.range_m for row in vm.rows if row.risk_level == "ok"]
    assert ok_ranges == sorted(ok_ranges)

    many = {f"t{i}": _wire_track(range_m=1000.0 + i) for i in range(12)}
    vm = build_radar_page_vm(many, limit=9)
    assert len(vm.rows) == 9 and vm.hidden_count == 3
    overflow = [line for line in format_radar_track_row_lines(vm) if "+ 3" in line]
    assert overflow and "F8" not in overflow[0]  # F8 не знает деталей треков


# ── Канонический рендерер MFD использует view-model ──────────────────────────

def test_left_mfd_radar_page_uses_view_model() -> None:
    text = render_left_mfd_page(
        page="radar",
        body_vm=None,
        telemetry={},
        observation_objective=None,
        radar_tracks={},
        incidents=[],
        safe_mode=None,
    )
    assert "эфир чист | охват 360°" in text
    assert "живых радар-треков нет" not in text


# ── Фикс LOST-эвикции в консоли (int-статус с провода) ───────────────────────

def test_on_track_evicts_lost_int_status() -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.orion_v.app import OrionVApp

    app = OrionVApp()
    track = _wire_track()
    track_id = track["track_id"]

    asyncio.run(app._on_track({"data": dict(track)}))
    assert track_id in app._latest_radar_tracks

    asyncio.run(app._on_track({"data": dict(track, status=3)}))
    assert track_id not in app._latest_radar_tracks  # int LOST выселяет
