from __future__ import annotations

from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector, ViewStatus


def _compute_field(model, key: str):
    return next(field for field in model.subsystems["compute"].fields if field.key == key)


def test_compute_heartbeat_age_critical() -> None:
    model = HardwareCollector().update({"compute.heartbeat_age_s": 50})

    assert model.subsystems["compute"].status == ViewStatus.CRIT


def test_compute_age_from_last_seen_timestamp() -> None:
    model = HardwareCollector().update(
        {"compute.last_seen_ts": 988.0},
        now_ts=1000.0,
    )
    heartbeat = _compute_field(model, "compute.heartbeat_age_s")

    assert heartbeat.value == 12.0


def test_compute_cpu_critical_sets_subsystem_critical_without_heartbeat() -> None:
    model = HardwareCollector().update({"compute.cpu_pct": 96})
    cpu = _compute_field(model, "compute.cpu_pct")

    assert cpu.status == ViewStatus.CRIT
    assert model.subsystems["compute"].status == ViewStatus.CRIT


def test_compute_cpu_warn_without_heartbeat() -> None:
    model = HardwareCollector().update({"compute.cpu_pct": 90})
    cpu = _compute_field(model, "compute.cpu_pct")

    assert cpu.status == ViewStatus.WARN


def test_compute_empty_snapshot_returns_no_data() -> None:
    model = HardwareCollector().update({})
    compute = model.subsystems["compute"]

    assert compute.status == ViewStatus.NO_DATA
    for field in compute.fields:
        assert field.value == "Нет данных"
        assert field.status == ViewStatus.NO_DATA
