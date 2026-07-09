"""View-model страницы РАДАР левого MFD (этап 6, спека Z4 + G5).

Единственный владелец радар-страницы для ОБОИХ рендер-путей (cockpit F1 и
mfd_page_content/systems): проекция `app._latest_radar_tracks` в строки пульта.
Не источник истины: треки приходят с NATS `qiki.radar.v1.tracks`
(RadarTrackModel.model_dump(mode="json") — енумы НА ПРОВОДЕ int), риск —
derived из range/vr через shared-владельца порогов (`qiki.shared.radar_risk`).
Команд не исполняет, состояние не мутирует.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from qiki.shared.models.radar import FriendFoeEnum, RadarTrackStatusEnum
from qiki.shared.radar_risk import classify_approach_risk

# Wire-коды остаются кодами (канон): значения IFF показываются латинскими
# кодами, подписи полей — русские.
_IFF_CODE_BY_ENUM: dict[int, str] = {
    int(FriendFoeEnum.FRIEND_FOE_UNSPECIFIED): "—",
    int(FriendFoeEnum.FRIEND): "FRND",
    int(FriendFoeEnum.FOE): "FOE",
    int(FriendFoeEnum.UNKNOWN): "UNK",
}
_IFF_CODE_BY_NAME: dict[str, str] = {
    "FRIEND": "FRND",
    "FOE": "FOE",
    "UNKNOWN": "UNK",
}

_RISK_CODE: dict[str, str] = {"ok": "OK", "warn": "WARN", "crit": "CRIT"}

EMPTY_AIR_ROW = "эфир чист | охват 360°"
# R.L.S.M/режим восприятия — target-only метка: q-sim источник не отдаёт.
PERCEPTION_MODE_LABEL = "НАВИГАЦИЯ"
PERCEPTION_MODE_NOTE = "режим — target-only метка (q-sim не отдаёт)"


def iff_code(value: Any) -> str:
    """Wire-IFF (int | «int-строка» | имя | None) → код пульта FRND/FOE/UNK/—."""
    if value is None:
        return "—"
    try:
        return _IFF_CODE_BY_ENUM.get(int(str(value).strip()), "—")
    except (TypeError, ValueError):
        pass
    return _IFF_CODE_BY_NAME.get(str(value).strip().upper(), "—")


def is_lost_status(value: Any) -> bool:
    """Wire-статус LOST в любой форме: int 3 / "3" / "LOST" / enum."""
    if value is None:
        return False
    try:
        return int(str(value).strip()) == int(RadarTrackStatusEnum.LOST)
    except (TypeError, ValueError):
        pass
    return str(value).strip().upper() == RadarTrackStatusEnum.LOST.name


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class RadarTrackRowVM:
    track_id: str
    label: str
    bearing_deg: float | None
    range_m: float | None
    vr_mps: float | None
    iff_code: str
    quality: float | None
    age_s: float | None
    risk_level: str
    t_cpa_s: float | None
    risk_source: str = "derived"


@dataclass(frozen=True, slots=True)
class RadarPageVM:
    rows: tuple[RadarTrackRowVM, ...]
    total_tracks: int
    hidden_count: int
    empty: bool
    coverage_label: str = "360°"
    perception_mode_label: str = PERCEPTION_MODE_LABEL


_RISK_SORT_ORDER = {"crit": 0, "warn": 1, "ok": 2}


def build_radar_page_vm(
    latest_radar_tracks: Mapping[str, Mapping[str, Any]],
    *,
    now_unix_s: float | None = None,
    limit: int = 9,
) -> RadarPageVM:
    rows: list[RadarTrackRowVM] = []
    for track_id, track in (latest_radar_tracks or {}).items():
        if not isinstance(track, Mapping):
            continue
        if is_lost_status(track.get("status")):
            continue  # защита в глубину поверх эвикции в _on_track
        range_m = _num(track.get("range_m") or track.get("range") or track.get("distance_m"))
        vr_mps = _num(track.get("vr_mps"))
        if range_m is not None and vr_mps is not None:
            risk_level, t_cpa_s = classify_approach_risk(range_m, vr_mps)
        else:
            risk_level, t_cpa_s = "ok", None
        age_s = _num(track.get("age_s") or track.get("age"))
        if age_s is None and now_unix_s is not None:
            source_ts = _num(track.get("_orion_source_timestamp_unix_s"))
            if source_ts is not None:
                age_s = max(0.0, now_unix_s - source_ts)
        label = str(
            track.get("transponder_id")
            or track.get("track_label")
            or track.get("label")
            or str(track_id)[:8]
        )
        rows.append(
            RadarTrackRowVM(
                track_id=str(track_id),
                label=label,
                bearing_deg=_num(track.get("bearing_deg") or track.get("bearing")),
                range_m=range_m,
                vr_mps=vr_mps,
                iff_code=iff_code(track.get("iff") or track.get("iff_class") or track.get("iffClass")),
                quality=_num(track.get("quality") or track.get("confidence")),
                age_s=age_s,
                risk_level=risk_level,
                t_cpa_s=t_cpa_s,
            )
        )

    rows.sort(
        key=lambda row: (
            _RISK_SORT_ORDER.get(row.risk_level, 3),
            row.range_m if row.range_m is not None else float("inf"),
            row.track_id,
        )
    )
    total = len(rows)
    shown = rows[: max(0, int(limit))]
    return RadarPageVM(
        rows=tuple(shown),
        total_tracks=total,
        hidden_count=total - len(shown),
        empty=total == 0,
    )


def _fmt(value: float | None, spec: str, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:{spec}}{suffix}"


def format_radar_track_row_lines(vm: RadarPageVM) -> list[str]:
    """Строки треков для section_lines-рамок (systems/target/sensors-пути)."""
    if vm.empty:
        return [EMPTY_AIR_ROW]
    lines: list[str] = []
    for index, row in enumerate(vm.rows, start=1):
        risk = _RISK_CODE.get(row.risk_level, row.risk_level.upper())
        risk_text = f"риск {risk}"
        if row.t_cpa_s is not None and row.risk_level in {"warn", "crit"}:
            risk_text += f" t_cpa={row.t_cpa_s:.0f}с"
        risk_text += f" ({row.risk_source})"
        lines.append(
            f"#{index} {row.label}"
            f" | пеленг {_fmt(row.bearing_deg, '03.0f', '°')}"
            f" | дальн {_fmt(row.range_m, '.0f', ' м')}"
            f" | скор {_fmt(row.vr_mps, '.1f', ' м/с')}"
            f" | IFF {row.iff_code}"
            f" | кач {_fmt(row.quality, '.2f')}"
            f" | {risk_text}"
        )
    if vm.hidden_count > 0:
        lines.append(f"+ {vm.hidden_count} ещё — детали: F8")
    return lines


def format_radar_page_lines(vm: RadarPageVM) -> list[str]:
    """Полная страница РАДАР для кокпита F1."""
    if vm.empty:
        return [
            f"{EMPTY_AIR_ROW} | режим: {vm.perception_mode_label}",
            PERCEPTION_MODE_NOTE,
        ]
    return [
        *format_radar_track_row_lines(vm),
        f"охват {vm.coverage_label} | режим: {vm.perception_mode_label} | {PERCEPTION_MODE_NOTE}",
    ]
