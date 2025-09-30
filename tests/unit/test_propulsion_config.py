"""Тесты загрузки конфигов Step-A."""

from __future__ import annotations

from qiki.shared.config.loaders import (
    build_thruster_allocation_matrix,
    load_antenna_config,
    load_docking_ports,
    load_hess_config,
    load_sensor_mounts,
    load_thrusters_config,
    thruster_allocation_rank,
)


def test_thrusters_config_rank_full_control() -> None:
    thrusters = load_thrusters_config()
    assert len(thrusters) == 16
    assert len({thruster.index for thruster in thrusters}) == 16

    matrix = build_thruster_allocation_matrix(thrusters)
    assert len(matrix) == 6
    assert all(len(row) == 16 for row in matrix)
    assert thruster_allocation_rank(thrusters) == 6


def test_hess_config_values() -> None:
    hess = load_hess_config()
    assert hess.p_peak_kw > hess.p_avail_kw
    assert 0.0 < hess.soc_battery["initial"] <= hess.soc_battery["max"]
    assert 0.0 < hess.soc_supercap["initial"] <= hess.soc_supercap["max"]


def test_docking_and_comms_configs() -> None:
    ports = load_docking_ports()
    assert len(ports) == 2
    assert {port.id for port in ports} == {"forward_bayonet", "aft_bayonet"}

    antenna = load_antenna_config()
    assert antenna.transponder.default_mode == "ON"
    assert "SPOOF" in antenna.transponder.modes


def test_sensor_mounts_config() -> None:
    mounts = load_sensor_mounts()
    assert len(mounts) >= 2
    assert all(mount.los_mask_asset for mount in mounts)
