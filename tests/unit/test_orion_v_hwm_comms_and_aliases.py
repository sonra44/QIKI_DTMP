from __future__ import annotations

from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector
from qiki.services.operator_console.orion_v.hardware_view_model.key_aliases import canonicalize_snapshot
from qiki.services.operator_console.orion_v.hardware_view_model.types import ViewStatus


def _field(model_key: str, collector: HardwareCollector, snapshot: dict[str, object]):
    model = collector.update(snapshot, now_ts=1000.0)
    comms = model.subsystems["comms"]
    index = {field.key: field for field in comms.fields}
    return index[model_key], comms, model


def test_comms_age_is_derived_from_last_seen_ts() -> None:
    collector = HardwareCollector()
    age_field, comms, _ = _field(
        "comms.age_s",
        collector,
        {
            "comms.last_seen_ts": 988.0,
            "comms.latency_ms": 45.0,
            "comms.packet_loss_pct": 0.2,
        },
    )

    assert age_field.value == 12.0
    assert age_field.status == ViewStatus.WARN
    assert comms.status == ViewStatus.WARN


def test_comms_age_uses_age_s_when_last_seen_missing() -> None:
    collector = HardwareCollector()
    age_field, comms, _ = _field(
        "comms.age_s",
        collector,
        {
            "comms.age_s": 50.0,
            "comms.latency_ms": 45.0,
            "comms.packet_loss_pct": 0.2,
        },
    )

    assert age_field.value == 50.0
    assert age_field.status == ViewStatus.CRIT
    assert comms.status == ViewStatus.CRIT


def test_comms_age_without_any_source_is_no_data() -> None:
    collector = HardwareCollector()
    age_field, comms, _ = _field(
        "comms.age_s",
        collector,
        {
            "comms.latency_ms": 45.0,
            "comms.packet_loss_pct": 0.2,
        },
    )

    assert age_field.value == "Нет данных"
    assert age_field.status == ViewStatus.NO_DATA
    assert comms.status == ViewStatus.OK


def test_comms_warn_by_latency() -> None:
    collector = HardwareCollector()
    latency_field, comms, _ = _field(
        "comms.latency_ms",
        collector,
        {
            "comms.latency_ms": 220.0,
            "comms.packet_loss_pct": 0.1,
            "comms.age_s": 2.0,
        },
    )

    assert latency_field.status == ViewStatus.WARN
    assert comms.status == ViewStatus.WARN


def test_comms_crit_by_packet_loss() -> None:
    collector = HardwareCollector()
    loss_field, comms, _ = _field(
        "comms.packet_loss_pct",
        collector,
        {
            "comms.latency_ms": 100.0,
            "comms.packet_loss_pct": 9.0,
            "comms.age_s": 1.0,
        },
    )

    assert loss_field.status == ViewStatus.CRIT
    assert comms.status == ViewStatus.CRIT


def test_alias_map_populates_canonical_keys() -> None:
    canonical = canonicalize_snapshot({"comms.link": "online", "link.loss_pct": 3.5, "link.latency_ms": 180.0})

    assert canonical["comms.packet_loss_pct"] == 3.5
    assert canonical["comms.latency_ms"] == 180.0
    assert canonical["comms.link_state"] == "online"


def test_comms_extended_metrics_are_in_hardware_fields() -> None:
    collector = HardwareCollector()
    model = collector.update(
        {
            "comms.link": "online",
            "comms.tx_power_w": 7.5,
            "comms.data_rate_kbps": 256.0,
            "comms.antenna_status": "lock",
        },
        now_ts=1000.0,
    )
    comms = model.subsystems["comms"]
    index = {field.key: field for field in comms.fields}

    assert index["comms.link_state"].value == "В РАБОТЕ"
    assert index["comms.tx_power_w"].value == 7.5
    assert index["comms.data_rate_kbps"].value == 256.0
    assert index["comms.antenna_status"].value == "lock"


def test_comms_plane_enabled_is_not_warning() -> None:
    collector = HardwareCollector()
    model = collector.update(
        {
            "comms.link": "online",
            "comms.latency_ms": 90.0,
            "comms.packet_loss_pct": 0.0,
            "comms.age_s": 0.0,
            "comms.plane_enabled": True,
        },
        now_ts=1000.0,
    )
    comms = model.subsystems["comms"]
    index = {field.key: field for field in comms.fields}

    assert index["comms.plane_enabled"].status == ViewStatus.OK
    assert comms.status == ViewStatus.OK


def test_comms_flat_aliases_feed_evidence_record() -> None:
    collector = HardwareCollector()
    model = collector.update(
        {
            "comms.link": "online",
            "comms.available": True,
            "comms.plane_enabled": True,
            "comms.xpdr.allowed": True,
            "comms.xpdr.mode": "normal",
            "comms.latency_ms": 90.0,
            "comms.packet_loss_pct": 0.0,
            "comms.age_s": 0.0,
        },
        now_ts=1000.0,
    )
    index = {field.key: field for field in model.subsystems["comms"].fields}
    link = index["comms.link_state"]

    assert link.trust_status == "trusted"
    assert link.freshness == "fresh"
    assert link.reason_codes == ()


def test_compute_coverage_reports_filled_and_total_fields() -> None:
    collector = HardwareCollector()
    model = collector.update({"comms.latency_ms": 45.0}, now_ts=1000.0)
    coverage = collector.compute_coverage(model)

    assert coverage["comms"][1] >= 10
    assert coverage["comms"][0] >= 1


def test_comms_summary_formatting() -> None:
    collector = HardwareCollector()
    model = collector.update(
        {
            "comms.latency_ms": 320.0,
            "comms.packet_loss_pct": 6.0,
            "comms.age_s": 12.0,
        },
        now_ts=1000.0,
    )

    assert model.subsystems["comms"].summary == "Связь: КРИТИЧНО, 320мс, loss 6.0%, age 12с"
