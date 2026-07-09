"""Срез 1 (SelfModel): внутренняя модель «Я» — 14 узлов от НЕслитых входов.

Канон: истина о теле из runtime; модель строится детерминированно (LLM только
описывает); неполнота маркируется honest missing/stale/unknown; провенанс
per-узел (телеметрия|мир|каталог) — входы НЕ сливаются заранее (атака-4).
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.self_model import build_self_model

NOW = 1_800_000_000.0

TELEMETRY = {
    "ts_unix_ms": (NOW - 1.0) * 1000.0,
    "power": {"soc_pct": 80.0, "bus_v": 28.0, "bus_a": 4.1, "load_shedding": False,
              "supercap_soc_pct": 90.0},
    "thermal": {"nodes": [{"id": "T_core", "temp_c": -46.0, "warned": False, "tripped": False}]},
    "propulsion": {"fuel_pct": 100.0, "remaining_fuel_g": 12000.0, "fuel_rate_gs": 0.0},
    "hull": {"integrity": 100.0},
    "cpu_usage": 30.0,
    "comms": {"link_state": "online", "latency_ms": 90.0, "packet_loss_pct": 0.0},
    "docking": {"state": "docked", "connected": True},
    "sim_state": {"paused": False, "fsm_state": "RUNNING"},
    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
    "speed_m_s": 0.0,
    "orbit": {"state": "off"},
    "radiation_usvh": 0.0,
    "temp_external_c": -60.0,
    "sensor_plane": {"imu": {"status": "ok"}, "radiation": {"status": "ok"}},
    "body_if_records": {"pdu_permissions": [{"load_id": "mcqpu", "SAFE_state": "unknown"}]},
}

WORLD = {"radar_tracks": [{"track_id": "t1", "range_m": 8500.0, "transponder_id": "WIRE-EVIL"}]}


class _Entry:
    def __init__(self, module_id, quantity):
        self.module_id = module_id
        self.quantity = quantity
        self.module_class = "sensor"


def _model(**over):
    kwargs = dict(telemetry=TELEMETRY, world=WORLD,
                  catalog_entries=(_Entry("test_sensor_module_001", 2),), now_ts=NOW)
    kwargs.update(over)
    return build_self_model(**kwargs)


def test_fourteen_nodes_present() -> None:
    m = _model()
    from qiki.shared.body_status import SELF_SYSTEM_IDS
    assert set(m.nodes.keys()) == set(SELF_SYSTEM_IDS.keys())


def test_provenance_per_node_from_unmerged_inputs() -> None:
    """Провенанс честный: радар — из мира, питание — из телеметрии."""
    m = _model()
    assert m.nodes["radar"].source == "world"
    assert m.nodes["power"].source == "telemetry"
    assert m.nodes["cargo"].source == "catalog"


def test_power_node_values_and_status() -> None:
    n = _model().nodes["power"]
    assert n.values["soc_pct"] == 80.0
    assert n.values["bus_v"] == 28.0
    assert n.status == "ok"  # 80% > warn 20%


def test_honest_gaps_body_structure_and_safe() -> None:
    """Честные дыры v1: занятость/модули тела мозгу не переданы; SAFE unknown."""
    m = _model()
    body = m.nodes["body_structure"]
    assert "occupancy" in body.missing and "installed_modules" in body.missing
    assert body.values.get("faces_total") == 12  # статика канона
    safe = m.nodes["safe_gating"]
    assert safe.status == "no_data" or safe.values.get("safe_state") == "unknown"


def test_cargo_from_catalog_with_disclaimer() -> None:
    """Карго — номинал склада: списания живут не у мозга (атака-2)."""
    n = _model().nodes["cargo"]
    assert n.values["entries_total"] == 1
    assert n.source == "catalog"
    assert "runtime_ledger" in n.missing  # остатки без учёта списаний — явно


def test_stale_telemetry_marks_nodes_stale_but_not_world() -> None:
    stale_tel = {**TELEMETRY, "ts_unix_ms": (NOW - 120.0) * 1000.0}
    m = _model(telemetry=stale_tel)
    assert m.nodes["power"].freshness == "stale"
    assert m.nodes["radar"].freshness != "stale"  # у мира свой провенанс


def test_wire_strings_do_not_leak_into_values() -> None:
    m = _model()
    flat = repr(m)
    assert "WIRE-EVIL" not in flat  # transponder не течёт в модель


def test_missing_telemetry_gives_no_data_everywhere_honestly() -> None:
    m = build_self_model(telemetry=None, world=None, catalog_entries=(), now_ts=NOW)
    assert m.nodes["power"].status == "no_data"
    assert m.nodes["radar"].status == "no_data"
