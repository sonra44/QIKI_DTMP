"""Registrar event codes and ranges."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict, Tuple


class RegistrarCode(IntEnum):
    """Registrar event codes by range.
    
    1xx: Boot and initialization events
    2xx: Sensor and input/output events
    3xx: Actuator and output events
    4xx: Communication events
    5xx: Navigation and positioning events
    6xx: Power and energy events
    7xx: System health and monitoring events
    8xx: Security and authentication events
    9xx: Critical and error events
    """

    # Boot and initialization events (100-199)
    BOOT_START = 100
    BOOT_OK = 101
    BOOT_FAILED = 102
    INIT_START = 110
    INIT_OK = 111
    INIT_FAILED = 112

    # Sensor and I/O events (200-299)
    SENSOR_IO_START = 200
    SENSOR_IO_OK = 201
    SENSOR_IO_FAILED = 202
    RADAR_FRAME_RECEIVED = 210
    RADAR_TRACK_GENERATED = 211

    # Actuator events (300-399)
    ACTUATOR_START = 300
    ACTUATOR_OK = 301
    ACTUATOR_FAILED = 302

    # Communication events (400-499)
    COMM_START = 400
    COMM_OK = 401
    COMM_FAILED = 402
    NATS_CONNECTED = 410
    NATS_DISCONNECTED = 411

    # Navigation events (500-599)
    NAV_START = 500
    NAV_OK = 501
    NAV_FAILED = 502

    # Power events (600-699)
    POWER_START = 600
    POWER_OK = 601
    POWER_LOW = 602
    POWER_CRITICAL = 603

    # System health events (700-799)
    HEALTH_CHECK_START = 700
    HEALTH_CHECK_OK = 701
    HEALTH_CHECK_FAILED = 702

    # Security events (800-899)
    SECURITY_START = 800
    SECURITY_OK = 801
    SECURITY_VIOLATION = 802

    # Critical and error events (900-999)
    CRITICAL_ERROR = 900
    SYSTEM_HALT = 901
    RECOVERY_START = 910
    RECOVERY_OK = 911


def get_code_range(code: RegistrarCode) -> Tuple[int, str]:
    """Get the range and description for a registrar code."""
    code_value = code.value
    ranges: Dict[Tuple[int, int], str] = {
        (100, 199): "Boot and initialization events",
        (200, 299): "Sensor and input/output events",
        (300, 399): "Actuator and output events",
        (400, 499): "Communication events",
        (500, 599): "Navigation and positioning events",
        (600, 699): "Power and energy events",
        (700, 799): "System health and monitoring events",
        (800, 899): "Security and authentication events",
        (900, 999): "Critical and error events",
    }
    
    for (start, end), description in ranges.items():
        if start <= code_value <= end:
            return (start, description)
    
    return (0, "Unknown range")