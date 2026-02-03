import pytest


def test_orion_radar_enum_labels_are_human_readable() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    assert OrionApp._radar_iff_code({"iff": 0}) == "—"
    assert OrionApp._radar_iff_code({"iff": 1}) == "FRND"
    assert OrionApp._radar_iff_code({"iff_class": "2"}) == "FOE"
    assert OrionApp._radar_iff_code({"iff": "UNKNOWN"}) == "UNK"

    assert OrionApp._radar_object_type_code({"object_type": 0}) == "—"
    assert OrionApp._radar_object_type_code({"object_type": 1}) == "DRONE"
    assert OrionApp._radar_object_type_code({"objectType": "2"}) == "SHIP"
    assert OrionApp._radar_object_type_code({"type": "station"}) == "STN"

    assert OrionApp._radar_transponder_mode_code({"transponder_mode": 0}) == "OFF"
    assert OrionApp._radar_transponder_mode_code({"transponderMode": "1"}) == "ON"
    assert OrionApp._radar_transponder_mode_code({"mode": "silent"}) == "SILENT"


def test_orion_sensor_status_labels_explain_disabled_sensors() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp
    from qiki.services.operator_console.ui import i18n as I18N

    assert OrionApp._sensor_status_label({"enabled": False}, I18N.NA) == I18N.bidi("Disabled", "Отключено")
    assert OrionApp._sensor_status_label(None, I18N.NA, status_kind="na") == I18N.bidi("Disabled", "Отключено")
    assert OrionApp._sensor_status_label(1.0, "1.0") == I18N.bidi("Normal", "Норма")
