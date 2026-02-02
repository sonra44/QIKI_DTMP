from __future__ import annotations

from qiki.services.operator_console.main_orion import OrionApp


def test_radar_status_code_mapping() -> None:
    assert OrionApp._radar_status_code({"status": 0}) == "—"
    assert OrionApp._radar_status_code({"status": 1}) == "NEW"
    assert OrionApp._radar_status_code({"status": 2}) == "TRK"
    assert OrionApp._radar_status_code({"status": 3}) == "LOST"
    assert OrionApp._radar_status_code({"status": 4}) == "CST"


def test_radar_range_band_code_mapping() -> None:
    assert OrionApp._radar_range_band_code({"range_band": 0}) == "—"
    assert OrionApp._radar_range_band_code({"range_band": 1}) == "LR"
    assert OrionApp._radar_range_band_code({"range_band": 2}) == "SR"

