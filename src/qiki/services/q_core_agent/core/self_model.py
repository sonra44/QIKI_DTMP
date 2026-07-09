"""SelfModel — внутренняя самоперцепция QIKI: «как я вижу себя» без консоли.

Срез 1 плана SelfModel (2026-07-09, [[qiki-selfmodel-plan]]). Канон
01_BODY_CANON / 10_READER_MANUAL: истина о теле — из runtime-источников;
«модель не подтверждает физический факт» — эта структура строится
ДЕТЕРМИНИРОВАННО, LLM её только описывает словами; неполнота маркируется
(missing / stale / no_data), а не выдумывается.

Принципы (по адверсариальной атаке на план):
- входы НЕ слиты (telemetry | world | catalog отдельно) — провенанс per-узел
  честный, поле source не выдумано;
- значения только валидированные (числа isfinite / enum из словарей
  qiki.shared.body_status) — wire-строки (id, transponder, reasons) в модель
  не попадают (канал косвенной инъекции закрыт);
- правда о занятости граней/установленных модулях живёт в процессе консоли и
  мозгу НЕ передаётся — узел body_structure несёт статику канона + honest
  missing (перенос правды тела — отдельный трек, Срез 4);
- карго — номинал склада (каталог): рантайм-списания у мозга нет — missing
  runtime_ledger, не выдуманный «остаток»;
- SAFE/гейтинг — владельца SAFE в runtime нет (sim эмитит unknown) — узел
  честно no_data/unknown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from qiki.shared.body_status import (
    COMMS_LAT_CRIT_MS,
    COMMS_LAT_WARN_MS,
    COMPUTE_CPU_CRIT_PCT,
    COMPUTE_CPU_WARN_PCT,
    DOCKING_STATES,
    FSM_STATES,
    HULL_INTEGRITY_CRIT_PCT,
    HULL_INTEGRITY_WARN_PCT,
    LINK_STATES,
    ORBIT_STATES,
    POWER_SOC_CRIT_PCT,
    POWER_SOC_WARN_PCT,
    PROPULSION_FUEL_CRIT_PCT,
    PROPULSION_FUEL_WARN_PCT,
    SELF_SYSTEM_IDS,
    SENSOR_STATUSES,
    THERMAL_CORE_CRIT_C,
    THERMAL_CORE_WARN_C,
    NodeStatus,
    status_by_max,
    status_by_min,
)

Freshness = Literal["fresh", "stale", "unknown"]

_STALE_AFTER_S = 5.0
_SENSOR_NAMES = ("imu", "radiation", "star_tracker", "proximity", "solar", "magnetometer")


@dataclass(frozen=True)
class SystemNode:
    """Один узел самоперцепции: значения + статус + провенанс + честные дыры."""

    system_id: str
    label_ru: str
    status: NodeStatus | Literal["unknown"]
    values: dict[str, Any] = field(default_factory=dict)  # только числа/bool/enum
    freshness: Freshness = "unknown"
    age_s: float | None = None
    source: str = "none"  # telemetry | world | catalog | canon | none
    missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class SelfModel:
    """Модель «Я» целиком: 14 узлов + идентичность (статика канона)."""

    nodes: dict[str, SystemNode]
    identity: dict[str, Any]
    generated_at_ts: float


def _num(section: Any, key: str) -> float | None:
    v = section.get(key) if isinstance(section, dict) else None
    if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
        return float(v)
    return None


def _top_num(snapshot: dict[str, Any] | None, key: str) -> float | None:
    v = snapshot.get(key) if isinstance(snapshot, dict) else None
    if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
        return float(v)
    return None


def _enum(section: Any, key: str, vocab: frozenset[str], *, lower: bool = True) -> str | None:
    raw = section.get(key) if isinstance(section, dict) else None
    if raw is None:
        return None
    text = str(raw).strip()
    text = text.lower() if lower else text.upper()
    return text if text in vocab else "unknown"


def build_self_model(
    *,
    telemetry: dict[str, Any] | None,
    world: dict[str, Any] | None,
    catalog_entries: Sequence[Any] = (),
    now_ts: float,
) -> SelfModel:
    """Собрать SelfModel от НЕслитых входов (провенанс честный)."""
    tel = telemetry if isinstance(telemetry, dict) else {}
    wrl = world if isinstance(world, dict) else {}

    # свежесть телеметрии (одна на все телеметрийные узлы)
    ts_raw = tel.get("ts_unix_ms")
    tel_age: float | None = None
    tel_fresh: Freshness = "unknown"
    if isinstance(ts_raw, (int, float)) and not isinstance(ts_raw, bool) and math.isfinite(float(ts_raw)):
        src_ts = float(ts_raw) / 1000.0 if float(ts_raw) > 10_000_000_000 else float(ts_raw)
        tel_age = max(0.0, now_ts - src_ts)
        tel_fresh = "stale" if tel_age >= _STALE_AFTER_S else "fresh"

    nodes: dict[str, SystemNode] = {}

    def tel_node(system_id: str, status: NodeStatus, values: dict[str, Any],
                 missing: tuple[str, ...] = ()) -> None:
        nodes[system_id] = SystemNode(
            system_id=system_id, label_ru=SELF_SYSTEM_IDS[system_id], status=status,
            values=values, freshness=tel_fresh, age_s=tel_age,
            source="telemetry" if values or status != "no_data" else "none",
            missing=missing,
        )

    # ── питание ──
    power = tel.get("power")
    soc = _num(power, "soc_pct")
    values: dict[str, Any] = {}
    if soc is not None:
        values["soc_pct"] = soc
    for k in ("bus_v", "bus_a", "supercap_soc_pct"):
        v = _num(power, k)
        if v is not None:
            values[k] = v
    if isinstance(power, dict):
        values["load_shedding"] = bool(power.get("load_shedding"))
    tel_node("power", status_by_min(soc, POWER_SOC_WARN_PCT, POWER_SOC_CRIT_PCT), values)

    # ── тепло ──
    thermal = tel.get("thermal")
    t_nodes = thermal.get("nodes") if isinstance(thermal, dict) else None
    if not isinstance(t_nodes, list):
        t_nodes = []
    temps = [
        float(n["temp_c"]) for n in t_nodes
        if isinstance(n, dict) and isinstance(n.get("temp_c"), (int, float))
        and not isinstance(n.get("temp_c"), bool) and math.isfinite(float(n["temp_c"]))
    ]
    max_temp = max(temps) if temps else None
    tripped = sum(1 for n in t_nodes if isinstance(n, dict) and bool(n.get("tripped")))
    warned = sum(1 for n in t_nodes if isinstance(n, dict) and bool(n.get("warned")))
    thermal_status = status_by_max(max_temp, THERMAL_CORE_WARN_C, THERMAL_CORE_CRIT_C)
    if thermal_status == "ok" and (tripped or warned):
        thermal_status = "crit" if tripped else "warn"
    tel_node("thermal", thermal_status,
             ({"max_temp_c": max_temp, "nodes_total": len(temps),
               "tripped": tripped, "warned": warned} if temps else {}))

    # ── двигатели ──
    propulsion = tel.get("propulsion")
    fuel = _num(propulsion, "fuel_pct")
    values = {}
    if fuel is not None:
        values["fuel_pct"] = fuel
    for k in ("remaining_fuel_g", "fuel_rate_gs", "propellant_tank_pressure_pa"):
        v = _num(propulsion, k)
        if v is not None:
            values[k] = v
    tel_node("propulsion", status_by_min(fuel, PROPULSION_FUEL_WARN_PCT, PROPULSION_FUEL_CRIT_PCT),
             values, missing=("rcs_thrust_maps",))  # RCS мёртв: карт тяги нет (бэклог сим)

    # ── корпус ──
    hull = _num(tel.get("hull"), "integrity")
    tel_node("hull", status_by_min(hull, HULL_INTEGRITY_WARN_PCT, HULL_INTEGRITY_CRIT_PCT),
             ({"integrity_pct": hull} if hull is not None else {}))

    # ── вычислитель ──
    cpu = _top_num(tel, "cpu_usage")
    mem = _top_num(tel, "memory_usage")
    values = {}
    if cpu is not None:
        values["cpu_pct"] = cpu
    if mem is not None:
        values["memory_pct"] = mem
    tel_node("compute", status_by_max(cpu, COMPUTE_CPU_WARN_PCT, COMPUTE_CPU_CRIT_PCT), values)

    # ── связь ──
    comms = tel.get("comms")
    link = _enum(comms, "link_state", LINK_STATES) or _enum(comms, "link", LINK_STATES)
    latency = _num(comms, "latency_ms")
    loss = _num(comms, "packet_loss_pct")
    comms_status: NodeStatus = (
        "no_data" if link is None
        else "crit" if link in {"offline", "down"}
        else "warn" if link in {"degraded", "unknown"}
        else status_by_max(latency, COMMS_LAT_WARN_MS, COMMS_LAT_CRIT_MS)
    )
    values = {}
    if link is not None:
        values["link"] = link
    if latency is not None:
        values["latency_ms"] = latency
    if loss is not None:
        values["packet_loss_pct"] = loss
    tel_node("comms", comms_status, values, missing=("emcon_state",))  # EMCON нет в профиле

    # ── стыковка ──
    docking = tel.get("docking")
    dock_state = _enum(docking, "state", DOCKING_STATES)
    values = {}
    if dock_state is not None:
        values["state"] = dock_state
        if isinstance(docking, dict):
            values["connected"] = bool(docking.get("connected"))
    tel_node("docking", "ok" if dock_state and dock_state != "unknown" else
             ("warn" if dock_state == "unknown" else "no_data"), values)

    # ── сенсоры ──
    sensor_plane = tel.get("sensor_plane")
    sensor_values: dict[str, Any] = {}
    issues = 0
    seen = 0
    if isinstance(sensor_plane, dict):
        for name in _SENSOR_NAMES:
            status = _enum(sensor_plane.get(name) if isinstance(sensor_plane.get(name), dict) else None,
                           "status", SENSOR_STATUSES)
            if status is None:
                continue
            seen += 1
            sensor_values[name] = status
            if status not in {"ok", "na", "off"}:
                issues += 1
    tel_node("sensors", ("no_data" if not seen else "warn" if issues else "ok"), sensor_values)

    # ── радар (источник: МИР, не телеметрия — свой провенанс) ──
    tracks = wrl.get("radar_tracks")
    if isinstance(tracks, list):
        ranges = [
            float(t["range_m"]) for t in tracks
            if isinstance(t, dict) and isinstance(t.get("range_m"), (int, float))
            and not isinstance(t.get("range_m"), bool) and math.isfinite(float(t["range_m"]))
        ]
        radar_values: dict[str, Any] = {"tracks_total": len(tracks)}
        if ranges:
            radar_values["nearest_range_m"] = min(ranges)
        nodes["radar"] = SystemNode(
            system_id="radar", label_ru=SELF_SYSTEM_IDS["radar"], status="ok",
            values=radar_values, freshness="fresh", age_s=None, source="world",
        )
    else:
        nodes["radar"] = SystemNode(
            system_id="radar", label_ru=SELF_SYSTEM_IDS["radar"], status="no_data",
            source="none", missing=("world_snapshot",),
        )

    # ── навигация ──
    pos = tel.get("position")
    px, py, pz = _num(pos, "x"), _num(pos, "y"), _num(pos, "z")
    speed = _top_num(tel, "speed_m_s")
    orbit_state = _enum(tel.get("orbit"), "state", ORBIT_STATES)
    values = {}
    if px is not None and py is not None and pz is not None:
        values.update({"pos_x_m": px, "pos_y_m": py, "pos_z_m": pz})
    if speed is not None:
        values["speed_m_s"] = speed
    if orbit_state is not None:
        values["orbit"] = orbit_state
    tel_node("navigation", "ok" if values else "no_data", values)

    # ── среда ──
    rad = _top_num(tel, "radiation_usvh")
    t_ext = _top_num(tel, "temp_external_c")
    values = {}
    if rad is not None:
        values["radiation_usvh"] = rad
    if t_ext is not None:
        values["temp_external_c"] = t_ext
    tel_node("environment", "ok" if values else "no_data", values)

    # ── мир/FSM входит в identity-контекст? Нет: sim_state — часть навигационного
    #    контекста борта; кладём в navigation values (fsm) для полноты ──
    fsm = _enum(tel.get("sim_state"), "fsm_state", FSM_STATES, lower=False)
    if fsm is not None and "navigation" in nodes:
        nav = nodes["navigation"]
        nodes["navigation"] = SystemNode(
            system_id=nav.system_id, label_ru=nav.label_ru, status=nav.status,
            values={**nav.values, "world_fsm": fsm}, freshness=nav.freshness,
            age_s=nav.age_s, source=nav.source, missing=nav.missing,
        )

    # ── структура тела: правда (занятость/модули) живёт в процессе консоли и
    #    мозгу НЕ передаётся — статика канона + honest missing (Срез 4 — перенос) ──
    nodes["body_structure"] = SystemNode(
        system_id="body_structure", label_ru=SELF_SYSTEM_IDS["body_structure"],
        status="no_data",
        values={"faces_total": 12, "bayonets": 2, "form": "dodecahedron"},
        source="canon",
        missing=("occupancy", "installed_modules"),
    )

    # ── грузовой отсек: номинал склада; рантайм-списания у мозга нет ──
    entries = list(catalog_entries or ())
    nodes["cargo"] = SystemNode(
        system_id="cargo", label_ru=SELF_SYSTEM_IDS["cargo"],
        status="ok" if entries else "no_data",
        values={"entries_total": len(entries)} if entries else {},
        source="catalog",
        missing=("runtime_ledger",),  # остатки = номинал, без учёта списаний
    )

    # ── SAFE/гейтинг: владельца SAFE в runtime нет — честно unknown ──
    if_records = tel.get("body_if_records")
    pdu = if_records.get("pdu_permissions") if isinstance(if_records, dict) else None
    safe_raw = None
    if isinstance(pdu, list) and pdu and isinstance(pdu[0], dict):
        safe_raw = str(pdu[0].get("SAFE_state") or "").strip().lower() or None
    nodes["safe_gating"] = SystemNode(
        system_id="safe_gating", label_ru=SELF_SYSTEM_IDS["safe_gating"],
        status="no_data",
        values={"safe_state": safe_raw if safe_raw in {"unknown", "safe", "unsafe"} else "unknown"},
        source="telemetry" if safe_raw is not None else "none",
        missing=("safe_owner",),  # SAFE→PDU проводка не подключена (бэклог сим)
    )

    identity = {
        "designation": "QIKI",
        "core": "Q-Core",
        "form": "dodecahedron",
        "faces": 12,
        "bayonets": 2,
        # Face Map частично fixture (body_structure.py: skeleton, NOT canon)
        "face_map_status": "fixture",
    }
    return SelfModel(nodes=nodes, identity=identity, generated_at_ts=now_ts)
