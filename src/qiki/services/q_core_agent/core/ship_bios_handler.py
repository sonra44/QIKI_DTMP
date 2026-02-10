import sys
import os
from dataclasses import dataclass
from enum import Enum

# NOTE: This module is part of the qiki package. Mutating sys.path at import-time is
# dangerous and can mask real import issues.
#
# Keep the legacy sys.path bootstrap only for direct execution
# (`python ship_bios_handler.py`), not for normal package imports.
if not __package__:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
    generated_path = os.path.join(project_root, "generated")
    if project_root not in sys.path:
        sys.path.append(project_root)
    if generated_path not in sys.path:
        sys.path.append(generated_path)

from typing import Dict, Any, List, Optional

try:
    from .interfaces import IBiosHandler
    from .agent_logger import logger
    from .ship_core import (
        ShipCore,
        HullStatus,
        PowerSystemStatus,
        PropulsionStatus,
        SensorStatus,
        LifeSupportStatus,
        ComputingStatus,
    )
except ImportError:
    # For direct execution - add current directory to path
    import interfaces
    import agent_logger
    import ship_core

    IBiosHandler = interfaces.IBiosHandler
    logger = agent_logger.logger
    ShipCore = ship_core.ShipCore
    HullStatus = ship_core.HullStatus
    PowerSystemStatus = ship_core.PowerSystemStatus
    PropulsionStatus = ship_core.PropulsionStatus
    SensorStatus = ship_core.SensorStatus
    LifeSupportStatus = ship_core.LifeSupportStatus
    ComputingStatus = ship_core.ComputingStatus

try:
    from generated.bios_status_pb2 import BiosStatusReport, DeviceStatus
    from generated.common_types_pb2 import UUID
    from google.protobuf.timestamp_pb2 import Timestamp
    BIOS_PROTO_FALLBACK_ACTIVE = False
except ImportError as exc:
    if os.getenv("QIKI_ALLOW_BIOS_FALLBACK", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise ImportError(
            "BIOS protobuf imports failed. "
            "Set QIKI_ALLOW_BIOS_FALLBACK=true only for explicit stand/dev fallback."
        ) from exc
    BIOS_PROTO_FALLBACK_ACTIVE = True
    # Mock classes for explicit development fallback
    class MockDeviceStatus:
        def __init__(self, device_id="", status="OK", **kwargs):
            self.device_id = device_id
            self.status = status

        class Status:
            OK = "OK"
            WARNING = "WARNING"
            ERROR = "ERROR"
            NOT_FOUND = "NOT_FOUND"

        class StatusCode:
            COMPONENT_NOT_FOUND = 1
            UNSTABLE_READINGS = 2
            TIMEOUT_RESPONSE = 3
            CRITICAL_BOOT_FAILURE = 4

    class MockBiosStatusReport:
        def __init__(self):
            self.post_results = []
            self.all_systems_go = False
            self.health_score = 0.0
            self.timestamp = None

        def CopyFrom(self, other):
            pass

    class MockUUID:
        def __init__(self, value=""):
            self.value = value

    class MockTimestamp:
        def GetCurrentTime(self):
            pass

    DeviceStatus = MockDeviceStatus
    BiosStatusReport = MockBiosStatusReport
    UUID = MockUUID
    Timestamp = MockTimestamp


class BiosReason(Enum):
    """Explicit BIOS data availability reasons."""

    OK = "OK"
    UNAVAILABLE = "BIOS_UNAVAILABLE"
    TIMEOUT = "BIOS_TIMEOUT"
    INVALID_REPORT = "BIOS_INVALID_REPORT"
    SIMULATED = "SIMULATED_BIOS"


@dataclass
class BiosFetchResult:
    """Explicit result for BIOS report fetch/diagnostics."""

    ok: bool
    report: Optional[BiosStatusReport]
    reason: str
    is_fallback: bool = False


class ShipBiosHandler(IBiosHandler):
    """
    Handles BIOS status for ship systems.
    Performs comprehensive diagnostics of all ship subsystems:
    hull, power, propulsion, sensors, life support, computing.
    """

    def __init__(self, ship_core: ShipCore):
        self.ship_core = ship_core
        logger.info("ShipBiosHandler initialized for ship diagnostics.")

    @staticmethod
    def _allow_bios_fallback() -> bool:
        return os.getenv("QIKI_ALLOW_BIOS_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"}

    def _validate_bios_report(self, report: Optional[BiosStatusReport]) -> Optional[str]:
        if report is None:
            return "report_is_none"
        if not hasattr(report, "timestamp"):
            return "missing_timestamp"
        if getattr(report, "timestamp", None) is None:
            return "timestamp_is_none"
        if not hasattr(report, "post_results"):
            return "missing_post_results"
        if not hasattr(report, "all_systems_go"):
            return "missing_all_systems_go"

        valid_statuses = {
            getattr(DeviceStatus.Status, "OK", None),
            getattr(DeviceStatus.Status, "WARNING", None),
            getattr(DeviceStatus.Status, "ERROR", None),
            getattr(DeviceStatus.Status, "NOT_FOUND", None),
        }
        valid_statuses.discard(None)
        for index, device_status in enumerate(getattr(report, "post_results", [])):
            if not hasattr(device_status, "status"):
                return f"device_status_missing_status_at_{index}"
            if valid_statuses and getattr(device_status, "status") not in valid_statuses:
                return f"device_status_invalid_status_at_{index}"
        return None

    def process_bios_status_result(self, bios_status: BiosStatusReport) -> BiosFetchResult:
        """Process comprehensive ship system diagnostics with explicit truth status."""
        if bios_status is None:
            logger.error("BIOS report unavailable: input bios_status is None")
            return BiosFetchResult(ok=False, report=None, reason=BiosReason.UNAVAILABLE.value, is_fallback=False)

        try:
            report = self._build_bios_report(bios_status)
        except TimeoutError as exc:
            logger.error(f"BIOS diagnostics timeout: {exc}")
            return BiosFetchResult(ok=False, report=None, reason=BiosReason.TIMEOUT.value, is_fallback=False)
        except ConnectionError as exc:
            logger.error(f"BIOS diagnostics unavailable: {exc}")
            return BiosFetchResult(ok=False, report=None, reason=BiosReason.UNAVAILABLE.value, is_fallback=False)
        except Exception as exc:
            logger.error(f"BIOS diagnostics failed: {exc}")
            return BiosFetchResult(ok=False, report=None, reason=BiosReason.UNAVAILABLE.value, is_fallback=False)

        invalid_reason = self._validate_bios_report(report)
        if invalid_reason is not None:
            logger.error(f"Invalid BIOS report detected: {invalid_reason}")
            return BiosFetchResult(
                ok=False,
                report=None,
                reason=f"{BiosReason.INVALID_REPORT.value}:{invalid_reason}",
                is_fallback=False,
            )

        is_fallback = BIOS_PROTO_FALLBACK_ACTIVE and self._allow_bios_fallback()
        if is_fallback:
            logger.warning("BIOS fallback enabled; marking report as simulated and non-green")
            if hasattr(report, "all_systems_go"):
                report.all_systems_go = False
            return BiosFetchResult(ok=True, report=report, reason=BiosReason.SIMULATED.value, is_fallback=True)

        return BiosFetchResult(ok=True, report=report, reason=BiosReason.OK.value, is_fallback=False)

    def process_bios_status(self, bios_status: BiosStatusReport) -> BiosStatusReport:
        """Legacy wrapper: returns report only for explicit OK/simulated fallback, else fail-fast."""
        result = self.process_bios_status_result(bios_status)
        if result.ok and result.report is not None:
            return result.report
        raise RuntimeError(f"BIOS data unavailable: {result.reason}")

    def _build_bios_report(self, bios_status: BiosStatusReport) -> BiosStatusReport:
        """Builds a BIOS report from live diagnostics."""
        logger.debug("Processing ship BIOS status - running full diagnostics.")

        # Create updated status report
        updated_bios_status = BiosStatusReport()
        if hasattr(updated_bios_status, "CopyFrom"):
            updated_bios_status.CopyFrom(bios_status)
        if hasattr(updated_bios_status, "timestamp"):
            timestamp_field = getattr(updated_bios_status, "timestamp")
            if hasattr(timestamp_field, "GetCurrentTime"):
                timestamp_field.GetCurrentTime()
            else:
                now = Timestamp()
                if hasattr(now, "GetCurrentTime"):
                    now.GetCurrentTime()
                updated_bios_status.timestamp = now

        # Clear previous results for fresh diagnostics
        post_results_field = getattr(updated_bios_status, "post_results", None)
        if hasattr(post_results_field, "clear"):
            post_results_field.clear()
        else:
            updated_bios_status.post_results = []

        # Run comprehensive ship diagnostics
        all_systems_go = True
        health_score = 1.0
        system_issues = []

        # 1. Hull Diagnostics
        hull_status, hull_issues = self._diagnose_hull()
        if hull_issues:
            all_systems_go = False
            system_issues.extend(hull_issues)
            health_score *= 0.9

        # 2. Power System Diagnostics
        power_status, power_issues = self._diagnose_power_systems()
        if power_issues:
            all_systems_go = False
            system_issues.extend(power_issues)
            health_score *= 0.8

        # 3. Propulsion Diagnostics
        propulsion_status, propulsion_issues = self._diagnose_propulsion()
        if propulsion_issues:
            all_systems_go = False
            system_issues.extend(propulsion_issues)
            health_score *= 0.7

        # 4. Sensor Diagnostics
        sensor_status, sensor_issues = self._diagnose_sensors()
        if sensor_issues:
            system_issues.extend(sensor_issues)
            health_score *= 0.95

        # 5. Life Support Diagnostics
        life_support_status, life_support_issues = self._diagnose_life_support()
        if life_support_issues:
            all_systems_go = False
            system_issues.extend(life_support_issues)
            health_score *= 0.6  # Critical for crew survival

        # 6. Computing Diagnostics
        computing_status, computing_issues = self._diagnose_computing()
        if computing_issues:
            system_issues.extend(computing_issues)
            health_score *= 0.85

        # Add all device statuses to BIOS report
        for issue in system_issues:
            device_status = DeviceStatus()
            if hasattr(device_status, "device_id") and hasattr(UUID, "__call__"):
                device_status.device_id = UUID(value=issue["device_id"])
            device_status.status = getattr(DeviceStatus.Status, issue["status"], "ERROR")
            device_status.error_message = issue["message"]
            device_status.status_code = getattr(DeviceStatus.StatusCode, issue.get("code", "UNSTABLE_READINGS"), 2)
            updated_bios_status.post_results.append(device_status)

        # Update overall status
        updated_bios_status.all_systems_go = all_systems_go
        if hasattr(updated_bios_status, "health_score"):
            updated_bios_status.health_score = max(0.0, health_score)

        # Log diagnostics summary
        logger.info(
            f"Ship diagnostics complete. Systems: {'NOMINAL' if all_systems_go else 'DEGRADED'}, "
            f"Health: {health_score:.1%}, Issues: {len(system_issues)}"
        )

        if system_issues:
            for issue in system_issues[:5]:  # Log first 5 issues
                logger.warning(f"System issue: {issue['device_id']} - {issue['message']}")

        return updated_bios_status

    def _diagnose_hull(self) -> tuple[HullStatus, List[Dict[str, str]]]:
        """Diagnose hull integrity and compartments."""
        hull_status = self.ship_core.get_hull_status()
        issues = []

        # Check hull integrity
        if hull_status.integrity < 90.0:
            issues.append(
                {
                    "device_id": "hull_structure",
                    "status": "WARNING" if hull_status.integrity > 50.0 else "ERROR",
                    "message": f"Hull integrity at {hull_status.integrity:.1f}%",
                    "code": "UNSTABLE_READINGS",
                }
            )

        # Check compartment pressures
        for compartment, params in hull_status.compartments.items():
            pressure = params.get("pressure", 0.0)
            temp = params.get("temperature", 0.0)

            if pressure < 0.8 and compartment != "cargo_bay":  # cargo_bay can be depressurized
                issues.append(
                    {
                        "device_id": f"compartment_{compartment}",
                        "status": "ERROR",
                        "message": f"Low pressure in {compartment}: {pressure:.2f} atm",
                        "code": "CRITICAL_BOOT_FAILURE",
                    }
                )

            if temp < 250 or temp > 350:  # Extreme temperatures
                issues.append(
                    {
                        "device_id": f"thermal_{compartment}",
                        "status": "WARNING",
                        "message": f"Temperature warning in {compartment}: {temp:.1f}K",
                        "code": "UNSTABLE_READINGS",
                    }
                )

        return hull_status, issues

    def _diagnose_power_systems(self) -> tuple[PowerSystemStatus, List[Dict[str, str]]]:
        """Diagnose reactor, batteries, and power distribution."""
        power_status = self.ship_core.get_power_status()
        issues = []

        # Check reactor
        reactor_efficiency = (
            power_status.reactor_output_mw / power_status.reactor_max_output_mw
            if power_status.reactor_max_output_mw > 0
            else 0
        )
        if reactor_efficiency < 0.5:
            issues.append(
                {
                    "device_id": "fusion_reactor",
                    "status": "WARNING",
                    "message": f"Reactor operating at {reactor_efficiency:.1%} efficiency",
                    "code": "UNSTABLE_READINGS",
                }
            )

        if power_status.reactor_fuel_hours < 24:
            issues.append(
                {
                    "device_id": "reactor_fuel",
                    "status": "WARNING" if power_status.reactor_fuel_hours > 8 else "ERROR",
                    "message": f"Low fuel: {power_status.reactor_fuel_hours:.1f} hours remaining",
                    "code": "UNSTABLE_READINGS",
                }
            )

        if power_status.reactor_temperature_k > 3000:
            issues.append(
                {
                    "device_id": "reactor_cooling",
                    "status": "ERROR",
                    "message": f"Reactor overheating: {power_status.reactor_temperature_k:.0f}K",
                    "code": "CRITICAL_BOOT_FAILURE",
                }
            )

        # Check batteries
        battery_charge = (
            power_status.battery_charge_mwh / power_status.battery_capacity_mwh
            if power_status.battery_capacity_mwh > 0
            else 0
        )
        if battery_charge < 0.2:
            issues.append(
                {
                    "device_id": "battery_bank",
                    "status": "WARNING" if battery_charge > 0.1 else "ERROR",
                    "message": f"Low battery: {battery_charge:.1%} charge",
                    "code": "UNSTABLE_READINGS",
                }
            )

        return power_status, issues

    def _diagnose_propulsion(self) -> tuple[PropulsionStatus, List[Dict[str, str]]]:
        """Diagnose main drive and RCS thrusters."""
        propulsion_status = self.ship_core.get_propulsion_status()
        issues = []

        # Check main drive
        if propulsion_status.main_drive_status not in ["ready", "idle", "active"]:
            issues.append(
                {
                    "device_id": "main_drive",
                    "status": "ERROR",
                    "message": f"Main drive status: {propulsion_status.main_drive_status}",
                    "code": "COMPONENT_NOT_FOUND",
                }
            )

        if propulsion_status.main_drive_fuel_kg < 50:
            issues.append(
                {
                    "device_id": "main_drive_fuel",
                    "status": "WARNING" if propulsion_status.main_drive_fuel_kg > 20 else "ERROR",
                    "message": f"Low propellant: {propulsion_status.main_drive_fuel_kg:.1f}kg remaining",
                    "code": "UNSTABLE_READINGS",
                }
            )

        # Check RCS thrusters
        for thruster_id, thruster_data in propulsion_status.rcs_status.items():
            if thruster_data["status"] not in ["ready", "active"]:
                issues.append(
                    {
                        "device_id": thruster_id,
                        "status": "WARNING",
                        "message": f"RCS thruster {thruster_id}: {thruster_data['status']}",
                        "code": "COMPONENT_NOT_FOUND",
                    }
                )

            if thruster_data["fuel_kg"] < 5:
                issues.append(
                    {
                        "device_id": f"{thruster_id}_fuel",
                        "status": "WARNING",
                        "message": f"Low RCS fuel in {thruster_id}: {thruster_data['fuel_kg']}kg",
                        "code": "UNSTABLE_READINGS",
                    }
                )

        return propulsion_status, issues

    def _diagnose_sensors(self) -> tuple[SensorStatus, List[Dict[str, str]]]:
        """Diagnose sensor systems."""
        sensor_status = self.ship_core.get_sensor_status()
        issues = []

        # Check critical sensors
        critical_sensors = ["long_range_radar", "navigation_computer"]
        for sensor_id in critical_sensors:
            if sensor_id not in sensor_status.active_sensors:
                sensor_data = sensor_status.sensor_data.get(sensor_id, {})
                issues.append(
                    {
                        "device_id": sensor_id,
                        "status": "ERROR",
                        "message": f"Critical sensor offline: {sensor_id} ({sensor_data.get('status', 'unknown')})",
                        "code": "COMPONENT_NOT_FOUND",
                    }
                )

        # Check power consumption
        if sensor_status.total_power_consumption_kw > 2000:  # Arbitrary threshold
            issues.append(
                {
                    "device_id": "sensor_power",
                    "status": "WARNING",
                    "message": f"High sensor power draw: {sensor_status.total_power_consumption_kw:.0f}kW",
                    "code": "UNSTABLE_READINGS",
                }
            )

        return sensor_status, issues

    def _diagnose_life_support(self) -> tuple[LifeSupportStatus, List[Dict[str, str]]]:
        """Diagnose life support systems."""
        life_support_status = self.ship_core.get_life_support_status()
        issues = []

        # Check atmosphere
        atmosphere = life_support_status.atmosphere
        oxygen = atmosphere.get("oxygen_percent", 0)
        co2 = atmosphere.get("co2_ppm", 0)
        pressure = atmosphere.get("pressure_kpa", 0)

        if oxygen < 18 or oxygen > 25:
            issues.append(
                {
                    "device_id": "atmosphere_oxygen",
                    "status": "ERROR" if oxygen < 16 or oxygen > 30 else "WARNING",
                    "message": f"Oxygen level: {oxygen:.1f}%",
                    "code": "CRITICAL_BOOT_FAILURE",
                }
            )

        if co2 > 1000:
            issues.append(
                {
                    "device_id": "co2_scrubbers",
                    "status": "ERROR" if co2 > 5000 else "WARNING",
                    "message": f"High CO2 level: {co2}ppm",
                    "code": "UNSTABLE_READINGS",
                }
            )

        if pressure < 80 or pressure > 120:
            issues.append(
                {
                    "device_id": "atmospheric_pressure",
                    "status": "ERROR",
                    "message": f"Pressure outside safe range: {pressure:.1f}kPa",
                    "code": "CRITICAL_BOOT_FAILURE",
                }
            )

        # Check water recycling
        water_recycling = life_support_status.water_recycling
        efficiency = water_recycling.get("recycling_efficiency", 0)
        if efficiency < 0.9:
            issues.append(
                {
                    "device_id": "water_recycling",
                    "status": "WARNING",
                    "message": f"Water recycling efficiency: {efficiency:.1%}",
                    "code": "UNSTABLE_READINGS",
                }
            )

        return life_support_status, issues

    def _diagnose_computing(self) -> tuple[ComputingStatus, List[Dict[str, str]]]:
        """Diagnose computing systems."""
        computing_status = self.ship_core.get_computing_status()
        issues = []

        # Check QIKI core
        if computing_status.qiki_core_status != "active":
            issues.append(
                {
                    "device_id": "qiki_core",
                    "status": "ERROR",
                    "message": f"QIKI core status: {computing_status.qiki_core_status}",
                    "code": "CRITICAL_BOOT_FAILURE",
                }
            )

        if computing_status.qiki_temperature_k > 300:
            issues.append(
                {
                    "device_id": "qiki_cooling",
                    "status": "WARNING" if computing_status.qiki_temperature_k < 320 else "ERROR",
                    "message": f"QIKI core temperature: {computing_status.qiki_temperature_k:.1f}K",
                    "code": "UNSTABLE_READINGS",
                }
            )

        # Check backup systems
        critical_backups = ["life_support_backup"]
        for backup_id in critical_backups:
            status = computing_status.backup_systems.get(backup_id, "unknown")
            if status not in ["active", "standby"]:
                issues.append(
                    {
                        "device_id": backup_id,
                        "status": "WARNING",
                        "message": f"Backup system {backup_id}: {status}",
                        "code": "COMPONENT_NOT_FOUND",
                    }
                )

        return computing_status, issues

    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get a quick health summary of all ship systems."""
        try:
            hull = self.ship_core.get_hull_status()
            power = self.ship_core.get_power_status()
            propulsion = self.ship_core.get_propulsion_status()
            sensors = self.ship_core.get_sensor_status()
            life_support = self.ship_core.get_life_support_status()
            computing = self.ship_core.get_computing_status()

            return {
                "hull_integrity": hull.integrity,
                "reactor_output_percent": (power.reactor_output_mw / power.reactor_max_output_mw * 100)
                if power.reactor_max_output_mw > 0
                else 0,
                "battery_charge_percent": (power.battery_charge_mwh / power.battery_capacity_mwh * 100)
                if power.battery_capacity_mwh > 0
                else 0,
                "main_drive": propulsion.main_drive_status,
                "active_sensors": len(sensors.active_sensors),
                "oxygen_percent": life_support.atmosphere.get("oxygen_percent", 0),
                "qiki_status": computing.qiki_core_status,
                "overall_status": "NOMINAL"
                if all(
                    [
                        hull.integrity > 80,
                        power.reactor_output_mw > 0,
                        propulsion.main_drive_status in ["ready", "idle"],
                        len(sensors.active_sensors) >= 2,
                        18 <= life_support.atmosphere.get("oxygen_percent", 0) <= 25,
                        computing.qiki_core_status == "active",
                    ]
                )
                else "DEGRADED",
            }
        except Exception as e:
            logger.error(f"Error generating health summary: {e}")
            return {"overall_status": "ERROR", "error": str(e)}


# Example usage
if __name__ == "__main__":
    try:
        # Test with ShipCore
        q_core_agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ship = ShipCore(base_path=q_core_agent_root)
        bios_handler = ShipBiosHandler(ship)

        # Run diagnostics
        mock_bios_status = BiosStatusReport()
        result = bios_handler.process_bios_status(mock_bios_status)

        print("Ship BIOS Diagnostics completed!")
        print(f"Systems status: {'NOMINAL' if result.all_systems_go else 'ISSUES DETECTED'}")
        print(f"Issues found: {len(result.post_results)}")

        # Health summary
        health = bios_handler.get_system_health_summary()
        print(f"System Health Summary: {health}")

    except Exception as e:
        print(f"Error during diagnostics test: {e}")
