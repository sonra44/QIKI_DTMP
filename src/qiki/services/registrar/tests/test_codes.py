"""Tests for Registrar event codes."""

from qiki.services.registrar.core.codes import RegistrarCode, get_code_range


def test_registrar_codes_have_correct_values():
    """Test that registrar codes have correct values."""
    # Boot events
    assert RegistrarCode.BOOT_START == 100
    assert RegistrarCode.BOOT_OK == 101
    assert RegistrarCode.BOOT_FAILED == 102
    
    # Sensor events
    assert RegistrarCode.SENSOR_IO_START == 200
    assert RegistrarCode.SENSOR_IO_OK == 201
    assert RegistrarCode.SENSOR_IO_FAILED == 202
    assert RegistrarCode.RADAR_FRAME_RECEIVED == 210
    assert RegistrarCode.RADAR_TRACK_GENERATED == 211
    
    # Communication events
    assert RegistrarCode.NATS_CONNECTED == 410
    assert RegistrarCode.NATS_DISCONNECTED == 411
    
    # Critical events
    assert RegistrarCode.CRITICAL_ERROR == 900
    assert RegistrarCode.SYSTEM_HALT == 901


def test_get_code_range():
    """Test that code ranges are correctly identified."""
    # Test boot events
    range_info = get_code_range(RegistrarCode.BOOT_OK)
    assert range_info[0] == 100
    assert "Boot and initialization events" in range_info[1]
    
    # Test sensor events
    range_info = get_code_range(RegistrarCode.RADAR_FRAME_RECEIVED)
    assert range_info[0] == 200
    assert "Sensor and input/output events" in range_info[1]
    
    # Test communication events
    range_info = get_code_range(RegistrarCode.NATS_CONNECTED)
    assert range_info[0] == 400
    assert "Communication events" in range_info[1]
    
    # Test critical events
    range_info = get_code_range(RegistrarCode.CRITICAL_ERROR)
    assert range_info[0] == 900
    assert "Critical and error events" in range_info[1]


def test_all_codes_have_ranges():
    """Test that all codes have valid ranges."""
    # Test a sample of codes from each range
    test_codes = [
        RegistrarCode.BOOT_OK,
        RegistrarCode.SENSOR_IO_OK,
        RegistrarCode.ACTUATOR_OK,
        RegistrarCode.COMM_OK,
        RegistrarCode.NAV_OK,
        RegistrarCode.POWER_OK,
        RegistrarCode.HEALTH_CHECK_OK,
        RegistrarCode.SECURITY_OK,
        RegistrarCode.CRITICAL_ERROR
    ]
    
    for code in test_codes:
        range_info = get_code_range(code)
        assert range_info[0] > 0, f"Code {code} should have a valid range"
        assert range_info[1] != "Unknown range", f"Code {code} should have a known range"