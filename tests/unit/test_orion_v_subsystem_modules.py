from __future__ import annotations

from qiki.services.operator_console.orion_v.modules import default_modules
from qiki.services.operator_console.orion_v.modules.comms import CommsSubsystemModule
from qiki.services.operator_console.orion_v.modules.docking import DockingSubsystemModule
from qiki.services.operator_console.orion_v.modules.power import PowerSubsystemModule
from qiki.services.operator_console.orion_v.modules.thermal import ThermalSubsystemModule
from qiki.services.operator_console.orion_v.i18n_ru import tr


def test_default_modules_autodiscovery_includes_core_modules() -> None:
    slugs = {module.slug for module in default_modules()}
    assert {"power", "thermal", "comms", "docking"}.issubset(slugs)


def test_power_module_summary_uses_status() -> None:
    module = PowerSubsystemModule()
    summary = module.render_summary({"telemetry": {"power": {"soc_pct": 82.0, "bus_v": 28.1, "limit_mode": "nominal"}}})
    assert summary.startswith("НОРМА | ")
    assert "Уровень заряда 82.0%" in summary
    assert "Причины сброса —" in summary


def test_power_module_details_show_shed_reasons_from_telemetry() -> None:
    module = PowerSubsystemModule()
    details = module.render_details(
        {
            "telemetry": {
                "power": {
                    "soc_pct": 12.0,
                    "bus_v": 21.5,
                    "bus_a": 2.8,
                    "load_shedding": True,
                    "shed_reasons": ["low_soc", "pdu_overcurrent"],
                }
            }
        }
    )
    assert "- Аварийное отключение нагрузки: да" in details
    assert "- Причины сброса: low_soc, pdu_overcurrent" in details


def test_power_module_marks_missing_reasons_as_degraded_when_shedding_active() -> None:
    module = PowerSubsystemModule()
    details = module.render_details(
        {
            "telemetry": {
                "power": {
                    "soc_pct": 12.0,
                    "bus_v": 21.5,
                    "bus_a": 2.8,
                    "load_shedding": True,
                }
            }
        }
    )
    assert "- Аварийное отключение нагрузки: да" in details
    assert "- Причины сброса: degraded: нет данных" in details


def test_thermal_module_warn_and_na_modes() -> None:
    module = ThermalSubsystemModule()
    warn_summary = module.render_summary({"telemetry": {"thermal": {"core_c": 81.0}}})
    na_summary = module.render_summary({"telemetry": {}})
    assert warn_summary.startswith("ПРЕДУПРЕЖДЕНИЕ | ")
    assert "Температура ядра degraded: нет данных" in na_summary


def test_comms_module_crit_when_link_down() -> None:
    module = CommsSubsystemModule()
    summary = module.render_summary({"telemetry": {"comms": {"link": "down", "latency_ms": 120.0}}})
    assert summary.startswith("КРИТИЧНО | ")
    details = module.render_details({"telemetry": {"comms": {"link": "down"}}})
    assert "Источники истины:" in details


def test_comms_module_uses_link_state_and_extended_metrics() -> None:
    module = CommsSubsystemModule()
    state = {
        "telemetry": {
            "comms": {
                "link_state": "online",
                "latency_ms": 90.0,
                "packet_loss_pct": 0.2,
                "rssi_dbm": -63.5,
                "snr_db": 21.0,
                "tx_power_w": 6.0,
                "data_rate_kbps": 192.0,
                "antenna_status": "lock",
                "age_s": 1.5,
            }
        }
    }
    summary = module.render_summary(state)
    details = module.render_details(state)
    assert f"Состояние канала {tr('online')}" in summary
    assert "- SNR: 21.0 dB" in details
    assert "- TX Power: 6.0 Вт" in details
    assert "- Data Rate: 192.0 kbps" in details
    assert "- Антенна: lock" in details
    assert "- Время с последнего приема: 1.5с" in details


def test_docking_module_summary_and_details() -> None:
    module = DockingSubsystemModule()
    summary = module.render_summary(
        {
            "telemetry": {
                "docking": {
                    "state": "approach",
                    "target_id": "port-a",
                    "distance_m": 12.3,
                    "rel_speed_mps": 0.35,
                }
            }
        }
    )
    assert summary.startswith("ПРЕДУПРЕЖДЕНИЕ | ")
    details = module.render_details({"telemetry": {"docking": {"state": "docked", "target_id": "port-a"}}})
    assert "- Состояние стыковки: docked" in details
