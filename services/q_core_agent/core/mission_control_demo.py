#!/usr/bin/env python3
"""
QIKI Mission Control Terminal Demo
Демонстрация интерфейса оператора для удаленного управления космическим аппаратом
в стиле NASA Mission Control / военного кокпита.
"""

import sys
import os
import time
from datetime import datetime

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from ship_core import ShipCore
from ship_actuators import ShipActuatorController, ThrusterAxis
from test_ship_fsm import ShipLogicController


class MissionControlDemo:
    """
    Демонстрация интерфейса Mission Control в текстовом формате.
    Показывает как выглядел бы полный интерфейс с реальными данными.
    """

    def __init__(self):
        # Инициализация корабельных систем
        q_core_agent_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        self.ship_core = ShipCore(base_path=q_core_agent_root)
        self.actuator_controller = ShipActuatorController(self.ship_core)
        self.logic_controller = ShipLogicController(
            self.ship_core, self.actuator_controller
        )

        self.mission_time_start = time.time()
        print(f"🚀 QIKI Mission Control Demo initialized for {self.ship_core.get_id()}")

    def get_mission_time(self) -> str:
        """Получает время миссии в формате T+HH:MM:SS."""
        elapsed = int(time.time() - self.mission_time_start)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        return f"T+{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_telemetry(self):
        """Получает текущие телеметрические данные."""
        hull = self.ship_core.get_hull_status()
        power = self.ship_core.get_power_status()
        propulsion = self.ship_core.get_propulsion_status()
        sensors = self.ship_core.get_sensor_status()
        life_support = self.ship_core.get_life_support_status()
        computing = self.ship_core.get_computing_status()

        return {
            "hull_integrity": hull.integrity,
            "reactor_output": power.reactor_output_mw,
            "reactor_max": power.reactor_max_output_mw,
            "battery_charge": power.battery_charge_mwh,
            "battery_capacity": power.battery_capacity_mwh,
            "reactor_temp": power.reactor_temperature_k,
            "main_drive_status": propulsion.main_drive_status,
            "main_drive_fuel": propulsion.main_drive_fuel_kg,
            "oxygen_level": life_support.atmosphere.get("oxygen_percent", 0),
            "co2_level": life_support.atmosphere.get("co2_ppm", 0),
            "pressure": life_support.atmosphere.get("pressure_kpa", 0),
            "qiki_status": computing.qiki_core_status,
            "qiki_temp": computing.qiki_temperature_k,
            "active_sensors": len(sensors.active_sensors),
            "propulsion_mode": self.actuator_controller.current_mode.value,
            "ship_state": self.logic_controller.current_state.value,
        }

    def format_bar(self, value: float, max_val: float = 100, width: int = 20) -> str:
        """Форматирует значение как progress bar."""
        pct = min(100, max(0, (value / max_val) * 100))
        filled = int(pct * width / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {value:6.1f}"

    def get_alert_level(self, telemetry):
        """Определяет уровень тревоги."""
        if (
            telemetry["hull_integrity"] < 30
            or telemetry["oxygen_level"] < 16
            or telemetry["reactor_temp"] > 3500
        ):
            return "🚨 EMERGENCY"
        elif (
            telemetry["hull_integrity"] < 60
            or telemetry["battery_charge"] / max(telemetry["battery_capacity"], 1) < 0.2
            or telemetry["main_drive_fuel"] < 50
        ):
            return "⚠️  WARNING"
        elif (
            telemetry["hull_integrity"] < 80
            or telemetry["co2_level"] > 1000
            or telemetry["reactor_temp"] > 3000
        ):
            return "⚡ CAUTION"
        else:
            return "✅ NOMINAL"

    def render_interface(self):
        """Отображает полный интерфейс Mission Control."""
        os.system("clear" if os.name == "posix" else "cls")

        telemetry = self.get_telemetry()
        mission_time = self.get_mission_time()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        alert_level = self.get_alert_level(telemetry)

        # Заголовок
        print(
            "╔══════════════════════════════════════════════════════════════════════════════════════════╗"
        )
        print(
            f"║ 🚀 QIKI MISSION CONTROL TERMINAL                    MISSION TIME: {mission_time} ║"
        )
        print(f"║ 🛰️  SPACECRAFT: {self.ship_core.get_id()}  UTC: {current_time} ║")
        print(
            f"║ 📊 SYSTEM STATUS: {alert_level:<20} MODE: {'AUTO' if False else 'MANUAL':<6} ║"
        )
        print(
            "╚══════════════════════════════════════════════════════════════════════════════════════════╝"
        )
        print()

        # Основная панель (две колонки)
        print(
            "┌─ SPACECRAFT TELEMETRY ──────────────────────────┐ ┌─ MISSION LOG ─────────────────────────────────────────────────────┐"
        )

        # Телеметрия
        hull_bar = self.format_bar(telemetry["hull_integrity"])
        reactor_pct = (
            telemetry["reactor_output"] / max(telemetry["reactor_max"], 1)
        ) * 100
        reactor_bar = self.format_bar(reactor_pct)
        battery_pct = (
            telemetry["battery_charge"] / max(telemetry["battery_capacity"], 1)
        ) * 100
        battery_bar = self.format_bar(battery_pct)

        log_entries = [
            f"[{datetime.now().strftime('%H:%M:%S')}] [{mission_time}] SPACECRAFT: 🛰️ Connected to {self.ship_core.get_id()}",
            f"[{datetime.now().strftime('%H:%M:%S')}] [{mission_time}] SYSTEMS: ✅ All primary systems online",
            f"[{datetime.now().strftime('%H:%M:%S')}] [{mission_time}] TELEMETRY: 📊 Data stream nominal",
            f"[{datetime.now().strftime('%H:%M:%S')}] [{mission_time}] PROPULSION: 🚀 {telemetry['propulsion_mode'].upper()} mode active",
            f"[{datetime.now().strftime('%H:%M:%S')}] [{mission_time}] NAVIGATION: 🧭 Long range sensors active",
            f"[{datetime.now().strftime('%H:%M:%S')}] [{mission_time}] LIFE SUPPORT: 💨 Atmospheric pressure nominal",
            f"[{datetime.now().strftime('%H:%M:%S')}] [{mission_time}] POWER: ⚡ Reactor operating at {reactor_pct:.0f}%",
            f"[{datetime.now().strftime('%H:%M:%S')}] [{mission_time}] QIKI: 🤖 AI system {telemetry['qiki_status']}",
        ]

        telemetry_lines = [
            f"│ 🛡️  HULL INTEGRITY : {hull_bar} % │",
            f"│ ⚡ REACTOR OUTPUT : {reactor_bar} % │",
            f"│ 🔋 BATTERY CHARGE : {battery_bar} % │",
            f"│ 🌡️  REACTOR TEMP   : {telemetry['reactor_temp']:8.0f} K              │",
            f"│ 💨 OXYGEN LEVEL   : {telemetry['oxygen_level']:8.1f} %              │",
            f"│ 🫁 CO2 LEVEL      : {telemetry['co2_level']:8.0f} ppm             │",
            f"│ 🤖 QIKI STATUS    : {telemetry['qiki_status']:>8}                │",
            "│                                                   │",
            "└─────────────────────────────────────────────────┘",
        ]

        # Отображение двух колонок
        for i in range(max(len(telemetry_lines), len(log_entries))):
            left = (
                telemetry_lines[i]
                if i < len(telemetry_lines)
                else "│                                                   │"
            )
            right = ""
            if i < len(log_entries):
                log_entry = log_entries[i]
                if len(log_entry) > 65:
                    log_entry = log_entry[:62] + "..."
                right = f"│ {log_entry:<65} │"
            else:
                right = "│                                                                 │"

            print(f"{left} {right}")

        # Если лог длиннее телеметрии, продолжаем показывать лог
        if len(log_entries) > len(telemetry_lines):
            for i in range(len(telemetry_lines), len(log_entries)):
                log_entry = log_entries[i]
                if len(log_entry) > 65:
                    log_entry = log_entry[:62] + "..."
                print(
                    f"                                                     │ {log_entry:<65} │"
                )

        print(
            "                                                     └───────────────────────────────────────────────────────────────────┘"
        )
        print()

        # Панель двигательной системы
        print("┌─ PROPULSION SYSTEMS ────────────────────────────┐")

        main_fuel_bar = self.format_bar(
            telemetry["main_drive_fuel"], 500
        )  # Макс 500 кг

        drive_status_color = (
            "🟢"
            if telemetry["main_drive_status"] in ["ready", "idle", "active"]
            else "🔴"
        )
        mode_color = {
            "idle": "🟢",
            "maneuvering": "🟡",
            "cruise": "🔵",
            "emergency": "🔴",
        }.get(telemetry["propulsion_mode"], "⚪")

        print(
            f"│ 🚀 MAIN DRIVE     : {drive_status_color} {telemetry['main_drive_status']:>8}                │"
        )
        print(
            f"│ 🎯 PROPULSION MODE: {mode_color} {telemetry['propulsion_mode'].upper():>8}               │"
        )
        print(f"│ ⛽ MAIN FUEL      : {main_fuel_bar} kg │")
        print(
            f"│ 📡 ACTIVE SENSORS : {telemetry['active_sensors']:8d}                │"
        )
        print(f"│ 🛰️  SHIP STATE     : {telemetry['ship_state']:>8}   │")
        print("└─────────────────────────────────────────────────┘")
        print()

        # Командная строка
        print(
            "┌─ COMMAND INTERFACE ──────────────────────────────────────────────────────────────────────┐"
        )
        print(
            "│ MISSION CONTROL> _                                                                       │"
        )
        print(
            "│                                                                                          │"
        )
        print(
            "└──────────────────────────────────────────────────────────────────────────────────────────┘"
        )
        print()

        # Hotkeys
        print(
            "💡 HOTKEYS: F1=Autopilot | F2=Emergency Stop | F3=Diagnostics | Ctrl+C=Exit"
        )
        print(
            "💡 COMMANDS: thrust <0-100> | rcs <dir> <0-100> | power status | sensor activate <id> | status | help"
        )

    def simulate_mission_scenario(self):
        """Симулирует сценарий миссии с различными событиями."""
        scenarios = [
            ("Initial State", "status", 3),
            ("Engine Test", "thrust 25", 4),
            ("Maneuvering", "rcs port 30", 3),
            ("Cruise Flight", "thrust 75", 4),
            ("Sensor Activation", "sensor activate thermal_scanner", 3),
            ("Power Check", "power status", 3),
            ("Mission Complete", "thrust 0", 3),
        ]

        print("\n🚀 Starting Mission Scenario Demonstration...")
        print("   This will show various stages of spacecraft operation")
        input("   Press Enter to begin...")

        for scenario_name, command, duration in scenarios:
            print(f"\n{'=' * 60}")
            print(f"🎯 SCENARIO: {scenario_name}")
            print(f"🎮 EXECUTING: {command}")
            print("=" * 60)

            # Выполнение команды (симуляция)
            self.execute_demo_command(command)

            # Отображение интерфейса
            self.render_interface()

            print(f"\n⏱️  Scenario duration: {duration} seconds")
            print("   Press Ctrl+C to skip or wait...")

            try:
                time.sleep(duration)
            except KeyboardInterrupt:
                print("\n⏭️  Skipping to next scenario...")
                time.sleep(0.5)

        print("\n✅ Mission scenario complete!")
        print("👨‍🚀 This demonstrates the full Mission Control Terminal interface.")

    def execute_demo_command(self, command: str):
        """Выполняет команду для демонстрации."""
        cmd_parts = command.split()
        if not cmd_parts:
            return

        cmd = cmd_parts[0]

        try:
            if cmd == "thrust" and len(cmd_parts) >= 2:
                thrust_pct = float(cmd_parts[1])
                self.actuator_controller.set_main_drive_thrust(thrust_pct)
                print(f"🚀 Main drive thrust set to {thrust_pct}%")

            elif cmd == "rcs" and len(cmd_parts) >= 3:
                direction = cmd_parts[1].upper()
                thrust_pct = float(cmd_parts[2])

                axis_map = {
                    "FORWARD": ThrusterAxis.FORWARD,
                    "BACKWARD": ThrusterAxis.BACKWARD,
                    "PORT": ThrusterAxis.PORT,
                    "STARBOARD": ThrusterAxis.STARBOARD,
                }

                if direction in axis_map:
                    self.actuator_controller.fire_rcs_thruster(
                        axis_map[direction], thrust_pct, 2.0
                    )
                    print(f"🎯 {direction} RCS thruster fired at {thrust_pct}%")

            elif cmd == "sensor" and len(cmd_parts) >= 3:
                action = cmd_parts[1]
                sensor_id = cmd_parts[2]
                if action == "activate":
                    self.actuator_controller.activate_sensor(sensor_id)
                    print(f"📡 Sensor {sensor_id} activated")

            elif cmd == "power" and len(cmd_parts) >= 2:
                if cmd_parts[1] == "status":
                    power_status = self.ship_core.get_power_status()
                    print(f"⚡ Reactor: {power_status.reactor_output_mw:.1f}MW")
                    print(f"⚡ Battery: {power_status.battery_charge_mwh:.1f}MWh")

            elif cmd == "status":
                summary = self.logic_controller.get_ship_status_summary()
                print(f"🛰️ Ship State: {summary.get('current_state', 'UNKNOWN')}")
                print(f"🛰️ Systems: {summary.get('overall_status', 'UNKNOWN')}")

            # Обновление логики после команды
            self.logic_controller.process_logic_cycle()

        except Exception as e:
            print(f"❌ Command execution error: {e}")

    def interactive_demo(self):
        """Интерактивная демонстрация."""
        print("\n🎮 Interactive Mission Control Demo")
        print("   Type commands to control the spacecraft")
        print("   Type 'help' for available commands, 'exit' to quit")

        while True:
            try:
                # Отображение интерфейса
                self.render_interface()

                # Ввод команды
                command = input("\nMISSION CONTROL> ").strip()

                if command.lower() in ["exit", "quit"]:
                    break
                elif command.lower() == "help":
                    print("\n💡 Available commands:")
                    print("  thrust <0-100>        - Set main drive thrust")
                    print(
                        "  rcs <dir> <0-100>     - Fire RCS thruster (forward/backward/port/starboard)"
                    )
                    print("  power status          - Show power status")
                    print("  sensor activate <id>  - Activate sensor")
                    print("  status                - Show ship status")
                    print("  exit                  - Exit demo")
                    input("\nPress Enter to continue...")
                elif command:
                    self.execute_demo_command(command)
                    input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                input("Press Enter to continue...")

        print("\n👨‍🚀 Demo terminated. Thank you for testing Mission Control!")


def main():
    """Главная функция демонстрации."""
    try:
        demo = MissionControlDemo()

        print("\n" + "=" * 80)
        print("🚀 QIKI MISSION CONTROL TERMINAL DEMONSTRATION")
        print("=" * 80)
        print()
        print("This demo shows the NASA/Military style cockpit interface")
        print("for remote spacecraft operation.")
        print()
        print("Choose demo mode:")
        print("1. Automated Mission Scenario")
        print("2. Interactive Command Demo")
        print("3. Single Interface View")

        choice = input("\nEnter choice (1-3): ").strip()

        if choice == "1":
            demo.simulate_mission_scenario()
        elif choice == "2":
            demo.interactive_demo()
        elif choice == "3":
            demo.render_interface()
            input("\nPress Enter to exit...")
        else:
            print("Invalid choice. Showing single interface view...")
            demo.render_interface()
            input("\nPress Enter to exit...")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
