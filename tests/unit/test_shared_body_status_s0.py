"""Срез 0 (SelfModel): единый владелец порогов/статусов/таксономии — qiki/shared.

Находка атаки [MED-5]: пороги warn/alarm жили только в консоли → любой второй
потребитель (SelfModel мозга) родил бы «второй вывод правды». Теперь:
- пороги и compare-функции — qiki.shared.body_status (один владелец);
- консольный thresholds.py — тонкая обёртка (импорт-сайты живут как жили);
- таксономия систем «Я» (14 узлов) и per-domain словари состояний — там же.
"""

from __future__ import annotations


def test_shared_module_owns_thresholds() -> None:
    from qiki.shared import body_status as bs
    assert bs.POWER_SOC_WARN_PCT == 20.0
    assert bs.THERMAL_CORE_CRIT_C == 95.0
    assert bs.COMMS_LAT_WARN_MS == 200.0
    assert bs.HULL_INTEGRITY_CRIT_PCT == 40.0


def test_console_thresholds_reexport_same_values() -> None:
    """Консоль берёт пороги из shared — не копия, а тот же владелец."""
    from qiki.shared import body_status as bs
    from qiki.services.operator_console.orion_v.hardware_view_model import thresholds as th
    assert th.POWER_SOC_WARN_PCT is bs.POWER_SOC_WARN_PCT or th.POWER_SOC_WARN_PCT == bs.POWER_SOC_WARN_PCT
    assert th.PROPULSION_FUEL_CRIT_PCT == bs.PROPULSION_FUEL_CRIT_PCT
    assert th.COMPUTE_CPU_WARN_PCT == bs.COMPUTE_CPU_WARN_PCT


def test_shared_status_functions_neutral_vocabulary() -> None:
    """Shared-функции говорят нейтральным словарём (ok/warn/crit/no_data)."""
    from qiki.shared.body_status import status_by_max, status_by_min
    assert status_by_min(50.0, warn_min=20.0, crit_min=15.0) == "ok"
    assert status_by_min(18.0, warn_min=20.0, crit_min=15.0) == "warn"
    assert status_by_min(10.0, warn_min=20.0, crit_min=15.0) == "crit"
    assert status_by_min(None, warn_min=20.0, crit_min=15.0) == "no_data"
    assert status_by_max(96.0, warn_max=80.0, crit_max=95.0) == "crit"


def test_console_status_functions_unchanged_contract() -> None:
    """Консольные функции по-прежнему возвращают ViewStatus (контракт цел)."""
    from qiki.services.operator_console.orion_v.hardware_view_model.thresholds import status_by_min
    from qiki.services.operator_console.orion_v.hardware_view_model.types import ViewStatus
    assert status_by_min(50.0, 20.0, 15.0) is ViewStatus.OK
    assert status_by_min(None, 20.0, 15.0) is ViewStatus.NO_DATA


def test_self_taxonomy_fourteen_nodes() -> None:
    """Таксономия «Я»: 14 канонических узлов со стабильными id."""
    from qiki.shared.body_status import SELF_SYSTEM_IDS
    assert len(SELF_SYSTEM_IDS) == 14
    for key in ("power", "thermal", "propulsion", "hull", "compute", "comms",
                "docking", "sensors", "radar", "navigation", "environment",
                "body_structure", "cargo", "safe_gating"):
        assert key in SELF_SYSTEM_IDS, f"нет узла {key}"
        assert SELF_SYSTEM_IDS[key]  # русская подпись непуста


def test_per_domain_state_vocabularies() -> None:
    """Per-domain словари состояний — один владелец (для note и SelfModel)."""
    from qiki.shared.body_status import (
        DOCKING_STATES, FSM_STATES, LINK_STATES, SENSOR_STATUSES,
    )
    assert "docked" in DOCKING_STATES and "undocked" in DOCKING_STATES
    assert "RUNNING" in FSM_STATES and "PAUSED" in FSM_STATES
    assert "online" in LINK_STATES and "degraded" in LINK_STATES
    assert "ok" in SENSOR_STATUSES and "degraded" in SENSOR_STATUSES
