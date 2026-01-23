from qiki.services.operator_console.main_orion import SCREEN_BY_ALIAS


def test_sensors_screen_aliases_present() -> None:
    assert SCREEN_BY_ALIAS.get("sensors") == "sensors"
    assert SCREEN_BY_ALIAS.get("сенсоры") == "sensors"
    assert SCREEN_BY_ALIAS.get("imu") == "sensors"
    assert SCREEN_BY_ALIAS.get("иму") == "sensors"

