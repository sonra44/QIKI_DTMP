#!/usr/bin/env python3
"""
Simple test for ship diagnostics without protobuf dependencies.
Tests the core logic of ship system analysis.
"""

import sys
import os

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import ship components
from ship_core import ShipCore


def test_ship_diagnostics():
    """Test ship diagnostic capabilities."""
    print("=== SHIP DIAGNOSTICS TEST ===")

    try:
        # Initialize ship
        q_core_agent_root = os.path.abspath(os.path.join(current_dir, ".."))
        ship = ShipCore(base_path=q_core_agent_root)

        print(f"Ship initialized: {ship.get_id()} ({ship.get_ship_class()})")
        print()

        # Test all system status methods
        print("1. HULL STATUS:")
        hull = ship.get_hull_status()
        print(f"   Integrity: {hull.integrity:.1f}%")
        print(f"   Mass: {hull.mass_kg:,} kg")
        print(f"   Compartments: {len(hull.compartments)}")
        for comp_name, comp_data in hull.compartments.items():
            print(
                f"     {comp_name}: {comp_data['pressure']:.1f} atm, {comp_data['temperature']:.0f}K"
            )
        print()

        print("2. POWER SYSTEMS:")
        power = ship.get_power_status()
        print(
            f"   Reactor: {power.reactor_output_mw:.1f}/{power.reactor_max_output_mw:.1f} MW ({power.reactor_output_mw / power.reactor_max_output_mw * 100:.1f}%)"
        )
        print(f"   Fuel: {power.reactor_fuel_hours:.1f} hours remaining")
        print(f"   Temperature: {power.reactor_temperature_k:.0f}K")
        print(
            f"   Battery: {power.battery_charge_mwh:.1f}/{power.battery_capacity_mwh:.1f} MWh ({power.battery_charge_mwh / power.battery_capacity_mwh * 100:.1f}%)"
        )
        print("   Power Distribution:")
        for system, allocation in power.power_distribution.items():
            print(
                f"     {system}: {allocation['allocated_mw']:.1f} MW (priority {allocation['priority']})"
            )
        print()

        print("3. PROPULSION:")
        propulsion = ship.get_propulsion_status()
        print(f"   Main Drive: {propulsion.main_drive_status}")
        print(
            f"   Thrust: {propulsion.main_drive_thrust_n:,}/{propulsion.main_drive_max_thrust_n:,} N"
        )
        print(f"   Fuel: {propulsion.main_drive_fuel_kg:.1f} kg")
        print(f"   RCS Thrusters: {len(propulsion.rcs_status)}")
        for thruster_id, thruster_data in propulsion.rcs_status.items():
            print(
                f"     {thruster_id}: {thruster_data['status']}, {thruster_data['fuel_kg']}kg, {thruster_data['thrust_n']}N"
            )
        print()

        print("4. SENSORS:")
        sensors = ship.get_sensor_status()
        print(
            f"   Active Sensors: {len(sensors.active_sensors)} / {len(sensors.sensor_data)}"
        )
        print(f"   Total Power: {sensors.total_power_consumption_kw:.0f} kW")
        for sensor_id, sensor_data in sensors.sensor_data.items():
            status_indicator = "●" if sensor_data["status"] == "active" else "○"
            print(
                f"     {status_indicator} {sensor_id}: {sensor_data['type']}, {sensor_data['status']}, {sensor_data['range_km']}km range"
            )
        print()

        print("5. LIFE SUPPORT:")
        life_support = ship.get_life_support_status()
        atm = life_support.atmosphere
        print(
            f"   Atmosphere: {atm['oxygen_percent']:.1f}% O2, {atm['nitrogen_percent']:.1f}% N2, {atm['co2_ppm']} ppm CO2"
        )
        print(
            f"   Pressure: {atm['pressure_kpa']:.1f} kPa, Temperature: {atm['temperature_k']:.0f}K, Humidity: {atm['humidity_percent']:.1f}%"
        )
        water = life_support.water_recycling
        print(
            f"   Water: {water['clean_water_liters']} L clean, {water['waste_water_liters']} L waste, {water['recycling_efficiency']:.1%} efficiency"
        )
        air = life_support.air_recycling
        print(
            f"   Air Recycling: {air['active_scrubbers']}/{air['co2_scrubbers']} CO2 scrubbers, {air['oxygen_generators']} O2 generators"
        )
        print()

        print("6. COMPUTING:")
        computing = ship.get_computing_status()
        print(f"   QIKI Core: {computing.qiki_core_status}")
        print(f"   Temperature: {computing.qiki_temperature_k:.0f}K")
        print(f"   Power Draw: {computing.qiki_power_consumption_kw:,} kW")
        print("   Backup Systems:")
        for backup_id, backup_status in computing.backup_systems.items():
            print(f"     {backup_id}: {backup_status}")
        print()

        print("7. SHIP SUMMARY:")
        summary = ship.get_ship_summary()
        for key, value in summary.items():
            print(f"   {key}: {value}")
        print()

        # Manual diagnostics logic (without protobuf)
        print("8. DIAGNOSTIC ANALYSIS:")
        issues = []

        # Hull checks
        if hull.integrity < 90:
            issues.append(f"Hull integrity low: {hull.integrity:.1f}%")

        # Power checks
        reactor_efficiency = power.reactor_output_mw / power.reactor_max_output_mw
        if reactor_efficiency < 0.7:
            issues.append(f"Reactor efficiency low: {reactor_efficiency:.1%}")

        if power.reactor_fuel_hours < 48:
            issues.append(f"Low fuel: {power.reactor_fuel_hours:.1f} hours remaining")

        if power.reactor_temperature_k > 3000:
            issues.append(f"Reactor overheating: {power.reactor_temperature_k:.0f}K")

        battery_charge = power.battery_charge_mwh / power.battery_capacity_mwh
        if battery_charge < 0.3:
            issues.append(f"Low battery: {battery_charge:.1%}")

        # Propulsion checks
        if propulsion.main_drive_status not in ["ready", "idle"]:
            issues.append(f"Main drive issue: {propulsion.main_drive_status}")

        if propulsion.main_drive_fuel_kg < 100:
            issues.append(f"Low propellant: {propulsion.main_drive_fuel_kg:.1f}kg")

        # Sensor checks
        critical_sensors = ["long_range_radar", "navigation_computer"]
        for sensor in critical_sensors:
            if sensor not in sensors.active_sensors:
                issues.append(f"Critical sensor offline: {sensor}")

        # Life support checks
        if not (18 <= atm["oxygen_percent"] <= 25):
            issues.append(f"Oxygen level critical: {atm['oxygen_percent']:.1f}%")

        if atm["co2_ppm"] > 1000:
            issues.append(f"High CO2: {atm['co2_ppm']} ppm")

        if not (80 <= atm["pressure_kpa"] <= 120):
            issues.append(f"Pressure warning: {atm['pressure_kpa']:.1f} kPa")

        # Computing checks
        if computing.qiki_core_status != "active":
            issues.append(f"QIKI core issue: {computing.qiki_core_status}")

        if computing.qiki_temperature_k > 300:
            issues.append(f"QIKI overheating: {computing.qiki_temperature_k:.0f}K")

        # Summary
        if issues:
            print(f"   ⚠️  {len(issues)} ISSUES DETECTED:")
            for i, issue in enumerate(issues, 1):
                print(f"      {i}. {issue}")
        else:
            print("   ✅ ALL SYSTEMS NOMINAL")

        print(f"\n   Overall Status: {'🟡 DEGRADED' if issues else '🟢 OPERATIONAL'}")

        return len(issues) == 0

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_ship_diagnostics()
    exit(0 if success else 1)
