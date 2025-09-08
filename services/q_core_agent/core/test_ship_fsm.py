#!/usr/bin/env python3
"""
Тестирование Ship FSM Handler - логического слоя управления кораблем.
Проверяет переходы между состояниями корабля в различных ситуациях.
"""

import sys
import os

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from ship_core import ShipCore
from ship_actuators import ShipActuatorController, PropulsionMode, ThrusterAxis
from enum import Enum
from typing import Dict, Any


class ShipState(Enum):
    """Состояния космического корабля."""

    SHIP_STARTUP = "SHIP_STARTUP"
    SHIP_IDLE = "SHIP_IDLE"
    FLIGHT_CRUISE = "FLIGHT_CRUISE"
    FLIGHT_MANEUVERING = "FLIGHT_MANEUVERING"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SYSTEMS_ERROR = "SYSTEMS_ERROR"


class MockFSMState:
    """Mock класс для FSM состояния."""

    def __init__(self, state_name="SHIP_STARTUP"):
        self.current_state_name = state_name
        self.phase = "STARTUP"
        self.history = []


class ShipLogicController:
    """
    Упрощенный логический контроллер корабля.
    Реализует основную логику управления состояниями без protobuf зависимостей.
    """

    def __init__(
        self, ship_core: ShipCore, actuator_controller: ShipActuatorController
    ):
        self.ship_core = ship_core
        self.actuator_controller = actuator_controller
        self.current_state = ShipState.SHIP_STARTUP
        print(f"🚀 Ship Logic Controller initialized for {ship_core.get_id()}")

    def is_ship_systems_ok(self) -> bool:
        """Проверяет основные системы корабля."""
        try:
            hull = self.ship_core.get_hull_status()
            power = self.ship_core.get_power_status()
            life_support = self.ship_core.get_life_support_status()
            computing = self.ship_core.get_computing_status()

            systems_ok = all(
                [
                    hull.integrity > 50.0,
                    power.reactor_output_mw > 0,
                    power.battery_charge_mwh > 0,
                    18 <= life_support.atmosphere.get("oxygen_percent", 0) <= 25,
                    life_support.atmosphere.get("co2_ppm", 0) < 5000,
                    computing.qiki_core_status == "active",
                ]
            )

            return systems_ok

        except Exception as e:
            print(f"❌ Error checking ship systems: {e}")
            return False

    def has_navigation_capability(self) -> bool:
        """Проверяет способность к навигации."""
        try:
            sensors = self.ship_core.get_sensor_status()
            propulsion = self.ship_core.get_propulsion_status()

            navigation_ok = all(
                [
                    "long_range_radar" in sensors.active_sensors,
                    "navigation_computer" in sensors.active_sensors,
                    propulsion.main_drive_status in ["ready", "idle", "active"],
                    propulsion.main_drive_fuel_kg > 10,
                ]
            )

            return navigation_ok

        except Exception as e:
            print(f"❌ Error checking navigation: {e}")
            return False

    def process_logic_cycle(self) -> Dict[str, Any]:
        """Выполняет один цикл логического управления."""
        print(f"\n🔄 Logic cycle - Current state: {self.current_state.value}")

        # Анализ состояния систем
        systems_ok = self.is_ship_systems_ok()
        nav_capable = self.has_navigation_capability()
        propulsion_mode = self.actuator_controller.current_mode

        previous_state = self.current_state
        trigger_event = ""

        # Логика переходов состояний
        if self.current_state == ShipState.SHIP_STARTUP:
            if systems_ok and nav_capable:
                self.current_state = ShipState.SHIP_IDLE
                trigger_event = "SHIP_SYSTEMS_ONLINE"
                print("✅ Ship systems online - ready for operations")
            elif systems_ok:
                self.current_state = ShipState.SHIP_IDLE
                trigger_event = "SHIP_SYSTEMS_PARTIAL"
                print("⚠️ Ship systems partial - limited capability")
            else:
                self.current_state = ShipState.SYSTEMS_ERROR
                trigger_event = "CRITICAL_SYSTEMS_FAILURE"
                print("❌ Critical systems failure")

        elif self.current_state == ShipState.SHIP_IDLE:
            if not systems_ok:
                self.current_state = ShipState.SYSTEMS_ERROR
                trigger_event = "SYSTEMS_DEGRADED"
                print("🚨 Systems degraded - entering error state")
            elif propulsion_mode == PropulsionMode.CRUISE:
                self.current_state = ShipState.FLIGHT_CRUISE
                trigger_event = "MAIN_DRIVE_ENGAGED"
                print("🌟 Main drive engaged - entering cruise flight")
            elif propulsion_mode == PropulsionMode.MANEUVERING:
                self.current_state = ShipState.FLIGHT_MANEUVERING
                trigger_event = "RCS_MANEUVERING_ACTIVE"
                print("🎯 RCS active - entering maneuvering mode")

        elif self.current_state == ShipState.FLIGHT_CRUISE:
            if not systems_ok:
                self.current_state = ShipState.EMERGENCY_STOP
                trigger_event = "EMERGENCY_SYSTEMS_FAILURE"
                print("🚨 Emergency stop - systems failure during cruise")
                self._execute_emergency_stop()
            elif propulsion_mode == PropulsionMode.MANEUVERING:
                self.current_state = ShipState.FLIGHT_MANEUVERING
                trigger_event = "SWITCHING_TO_MANEUVERING"
                print("🎯 Switching to maneuvering mode")
            elif propulsion_mode == PropulsionMode.IDLE:
                self.current_state = ShipState.SHIP_IDLE
                trigger_event = "FLIGHT_COMPLETED"
                print("✅ Flight completed - returning to idle")

        elif self.current_state == ShipState.FLIGHT_MANEUVERING:
            if not systems_ok:
                self.current_state = ShipState.EMERGENCY_STOP
                trigger_event = "EMERGENCY_SYSTEMS_FAILURE"
                print("🚨 Emergency stop during maneuvering")
                self._execute_emergency_stop()
            elif propulsion_mode == PropulsionMode.CRUISE:
                self.current_state = ShipState.FLIGHT_CRUISE
                trigger_event = "SWITCHING_TO_CRUISE"
                print("🌟 Switching to cruise mode")
            elif propulsion_mode == PropulsionMode.IDLE:
                self.current_state = ShipState.SHIP_IDLE
                trigger_event = "MANEUVERING_COMPLETED"
                print("✅ Maneuvering completed")

        elif self.current_state == ShipState.EMERGENCY_STOP:
            if systems_ok and propulsion_mode == PropulsionMode.EMERGENCY:
                self.current_state = ShipState.SHIP_IDLE
                trigger_event = "EMERGENCY_CLEARED"
                print("✅ Emergency cleared - returning to normal operations")

        elif self.current_state == ShipState.SYSTEMS_ERROR:
            if systems_ok:
                self.current_state = ShipState.SHIP_IDLE
                trigger_event = "SYSTEMS_RECOVERED"
                print("✅ Systems recovered - returning to idle")

        # Результат цикла
        state_changed = previous_state != self.current_state

        return {
            "previous_state": previous_state.value,
            "current_state": self.current_state.value,
            "state_changed": state_changed,
            "trigger_event": trigger_event,
            "systems_ok": systems_ok,
            "navigation_capable": nav_capable,
            "propulsion_mode": propulsion_mode.value,
        }

    def _execute_emergency_stop(self):
        """Выполняет аварийную остановку."""
        try:
            success = self.actuator_controller.emergency_stop()
            if success:
                print("✅ Emergency stop executed successfully")
            else:
                print("❌ Emergency stop failed")
        except Exception as e:
            print(f"❌ Emergency stop error: {e}")

    def get_ship_status_summary(self) -> Dict[str, Any]:
        """Получает сводку состояния корабля."""
        try:
            systems_ok = self.is_ship_systems_ok()
            nav_capable = self.has_navigation_capability()

            return {
                "ship_id": self.ship_core.get_id(),
                "current_state": self.current_state.value,
                "systems_operational": systems_ok,
                "navigation_capable": nav_capable,
                "propulsion_mode": self.actuator_controller.current_mode.value,
                "ready_for_flight": systems_ok and nav_capable,
                "overall_status": "OPERATIONAL" if systems_ok else "DEGRADED",
            }
        except Exception as e:
            return {"error": str(e)}


def test_ship_logic_controller():
    """Тестирует логический контроллер корабля."""
    print("=== SHIP LOGIC CONTROLLER TEST ===")

    try:
        # Инициализация корабельных систем
        q_core_agent_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        ship = ShipCore(base_path=q_core_agent_root)
        actuator_controller = ShipActuatorController(ship)

        # Инициализация логического контроллера
        logic_controller = ShipLogicController(ship, actuator_controller)

        print(f"Ship: {ship.get_id()}")
        print()

        # Симуляция нескольких циклов логического управления
        for cycle in range(8):
            print(f"\n{'=' * 50}")
            print(f"LOGIC CYCLE {cycle + 1}")
            print("=" * 50)

            # Выполнение логического цикла
            result = logic_controller.process_logic_cycle()

            # Отображение результатов
            print("\n📊 Cycle Results:")
            for key, value in result.items():
                print(f"   {key}: {value}")

            # Получение сводки состояния
            summary = logic_controller.get_ship_status_summary()
            print("\n📋 Ship Status Summary:")
            for key, value in summary.items():
                print(f"   {key}: {value}")

            # Симуляция различных активностей в разных циклах
            if cycle == 1:
                print("\n🎮 Simulation: Activating main drive (25% thrust)")
                actuator_controller.set_main_drive_thrust(25.0)

            elif cycle == 3:
                print("\n🎮 Simulation: Switching to RCS maneuvering")
                actuator_controller.fire_rcs_thruster(ThrusterAxis.PORT, 30.0, 2.0)

            elif cycle == 5:
                print("\n🎮 Simulation: Increasing main drive thrust")
                actuator_controller.set_main_drive_thrust(75.0)

            elif cycle == 6:
                print("\n🎮 Simulation: Stopping all propulsion")
                actuator_controller.set_main_drive_thrust(0.0)

            # Прерывание если состояние стабилизировалось
            if cycle > 2 and not result["state_changed"]:
                consecutive_stable = (
                    getattr(test_ship_logic_controller, "stable_count", 0) + 1
                )
                test_ship_logic_controller.stable_count = consecutive_stable

                if consecutive_stable >= 2:
                    print(f"\n✅ State stabilized after {cycle + 1} cycles")
                    break
            else:
                test_ship_logic_controller.stable_count = 0

        print(f"\n🎯 Final State: {logic_controller.current_state.value}")
        print("✅ Ship Logic Controller test completed successfully")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_ship_logic_controller()
    exit(0 if success else 1)
