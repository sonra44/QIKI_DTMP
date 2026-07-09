"""View-model страницы РАДАР левого MFD (этап 6, спека Z4 + G5).

Единственный владелец радар-страницы для ОБОИХ рендер-путей (cockpit F1 и
mfd_page_content/systems): проекция `app._latest_radar_tracks` в строки пульта.
Не источник истины: треки приходят с NATS `qiki.radar.v1.tracks`
(RadarTrackModel.model_dump(mode="json") — енумы НА ПРОВОДЕ int), риск —
derived из range/vr через shared-владельца порогов (`qiki.shared.radar_risk`).
Команд не исполняет, состояние не мутирует.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from qiki.shared.models.radar import FriendFoeEnum, RadarTrackStatusEnum
from qiki.shared.radar_freshness import (
    DEAD,
    FRESH,
    RADAR_TRACK_DEAD_S,
    STALE,
    classify_track_freshness,
)
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
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None  # NaN/inf с провода — не данные
    return result


def _first_num(track: Mapping[str, Any], *keys: str) -> float | None:
    """Первый ключ с ЧИСЛОМ. Не `or`-цепочка: 0.0 — данные (пеленг ровно по
    носу, качество 0.0), falsy-провал в fallback терял их (аудит-находка)."""
    for key in keys:
        if key in track:
            value = _num(track.get(key))
            if value is not None:
                return value
    return None


def _first_present(track: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = track.get(key)
        if value is not None:
            return value
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
    # Свежесть по времени ПРИЁМА консолью (wire age_s всегда 0.0 — дефолт
    # модели, для staleness не годится). Неизвестный возраст → fresh без
    # пометки: боевой путь всегда штампует _orion_received_at_unix_s.
    freshness: str = FRESH
    staleness_age_s: float | None = None


@dataclass(frozen=True, slots=True)
class RadarPageVM:
    rows: tuple[RadarTrackRowVM, ...]
    total_tracks: int
    hidden_count: int
    empty: bool
    coverage_label: str = "360°"
    perception_mode_label: str = PERCEPTION_MODE_LABEL
    # Треки без данных дольше RADAR_TRACK_DEAD_S: скрыты из рядов, но не
    # замолчаны — честный счётчик вместо «живого» призрака или «эфир чист».
    dead_count: int = 0


# «none» (нет кинематики) выше подтверждённого ok: неопределённость не хоронится.
_RISK_SORT_ORDER = {"crit": 0, "warn": 1, "none": 2, "ok": 3}


def build_radar_page_vm(
    latest_radar_tracks: Mapping[str, Mapping[str, Any]],
    *,
    now_unix_s: float | None = None,
    limit: int = 9,
) -> RadarPageVM:
    rows: list[RadarTrackRowVM] = []
    dead_count = 0
    for track_id, track in (latest_radar_tracks or {}).items():
        if not isinstance(track, Mapping):
            continue
        if is_lost_status(track.get("status")):
            continue  # защита в глубину поверх эвикции в _on_track
        # Свежесть — по времени приёма консолью (после sim.stop поток трека
        # умирает, а LOST не придёт: без этого призрак «жил» вечно).
        staleness_age_s: float | None = None
        if now_unix_s is not None:
            received_ts = _first_num(
                track, "_orion_received_at_unix_s", "_orion_source_timestamp_unix_s"
            )
            if received_ts is not None:
                staleness_age_s = max(0.0, now_unix_s - received_ts)
        freshness = FRESH if staleness_age_s is None else classify_track_freshness(staleness_age_s)
        if freshness == DEAD:
            dead_count += 1
            continue
        range_m = _first_num(track, "range_m", "range", "distance_m")
        vr_mps = _first_num(track, "vr_mps")
        if range_m is not None and range_m >= 0.0 and vr_mps is not None:
            risk_level, t_cpa_s = classify_approach_risk(range_m, vr_mps)
        else:
            # нет кинематики — риск честно неизвестен, а не «OK (derived)»
            risk_level, t_cpa_s = "none", None
        age_s = _first_num(track, "age_s", "age")
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
                bearing_deg=_first_num(track, "bearing_deg", "bearing"),
                range_m=range_m,
                vr_mps=vr_mps,
                iff_code=iff_code(_first_present(track, "iff", "iff_class", "iffClass")),
                quality=_first_num(track, "quality", "confidence"),
                age_s=age_s,
                risk_level=risk_level,
                t_cpa_s=t_cpa_s,
                freshness=freshness,
                staleness_age_s=staleness_age_s,
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
        # «эфир чист» — только когда контактов нет ВООБЩЕ; умершие по
        # возрасту — это «данных нет», а не «целей нет».
        empty=total == 0 and dead_count == 0,
        dead_count=dead_count,
    )


def _fmt(value: float | None, spec: str, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:{spec}}{suffix}"


def format_radar_track_row_lines(vm: RadarPageVM) -> list[str]:
    """Строки треков для section_lines-рамок (systems/target/sensors-пути)."""
    if vm.empty:
        return [EMPTY_AIR_ROW]
    if not vm.rows and vm.dead_count > 0:
        # все контакты умерли по возрасту — «эфир чист» был бы ложью
        return [f"радар молчит | свежих контактов нет | скрыто устаревших: {vm.dead_count}"]
    lines: list[str] = []
    classified = False
    for index, row in enumerate(vm.rows, start=1):
        if row.risk_level == "none":
            risk_text = "риск —"
        else:
            classified = True
            risk_text = f"риск {_RISK_CODE.get(row.risk_level, row.risk_level.upper())}"
            if row.t_cpa_s is not None and row.risk_level in {"warn", "crit"}:
                risk_text += f" t_cpa={row.t_cpa_s:.0f}с"
        stale_text = ""
        if row.freshness == STALE and row.staleness_age_s is not None:
            stale_text = f" | уст {row.staleness_age_s:.0f}с"
        # без '#'-префикса: ui_rich красит #-буллеты в muted, страница серела
        lines.append(
            f"{index:>2} {row.label}"
            f" | пеленг {_fmt(row.bearing_deg, '03.0f', '°')}"
            f" | дальн {_fmt(row.range_m, '.0f', ' м')}"
            f" | скор {_fmt(row.vr_mps, '.1f', ' м/с')}"
            f" | IFF {row.iff_code}"
            f" | кач {_fmt(row.quality, '.2f')}"
            f" | {risk_text}"
            f"{stale_text}"
        )
    if vm.hidden_count > 0:
        lines.append(f"+ {vm.hidden_count} ещё")
    if vm.dead_count > 0:
        lines.append(
            f"скрыто устаревших: {vm.dead_count} (нет данных > {RADAR_TRACK_DEAD_S:.0f}с)"
        )
    if classified:
        # derived-пометка одна на страницу — честность без мусора в рядах
        lines.append("риск: derived (range/vr)")
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
