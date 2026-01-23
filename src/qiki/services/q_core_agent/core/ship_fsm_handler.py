"""
Ship FSM Handler - конечный автомат для управления космическим кораблем.
Управляет состояниями корабля: загрузка, режим ожидания, полет, стыковка, аварийные состояния.
"""

import os
import sys

# NOTE: This module is part of the qiki package. Mutating sys.path at import-time is
# dangerous and can mask real import issues.
#
# Keep the legacy sys.path bootstrap only for direct execution
# (`python ship_fsm_handler.py`), not for normal package imports.
if not __package__:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
    generated_path = os.path.join(project_root, "generated")
    if project_root not in sys.path:
        sys.path.append(project_root)
    if generated_path not in sys.path:
        sys.path.append(generated_path)

from typing import Dict, Any, Optional
from enum import Enum

try:
    from .interfaces import IFSMHandler
    from .agent_logger import logger
    from .ship_core import ShipCore
    from .ship_actuators import ShipActuatorController, PropulsionMode
except ImportError:
    # For direct execution
    import interfaces
    import agent_logger
    import ship_core
    import ship_actuators

    IFSMHandler = interfaces.IFSMHandler
    logger = agent_logger.logger
    ShipCore = ship_core.ShipCore
    ShipActuatorController = ship_actuators.ShipActuatorController
    PropulsionMode = ship_actuators.PropulsionMode

from fsm_state_pb2 import (
    FsmStateSnapshot as FSMState,
    StateTransition,
    FSMStateEnum,
    FSMTransitionStatus,
)

_SHIP_STATE_CONTEXT_KEY = "ship_state_name"


class ShipState(Enum):
    """Состояния космического корабля."""

    SHIP_STARTUP = "SHIP_STARTUP"  # Запуск систем корабля
    SHIP_IDLE = "SHIP_IDLE"  # Готов к полету, системы в режиме ожидания
    FLIGHT_CRUISE = "FLIGHT_CRUISE"  # Крейсерский полет
    FLIGHT_MANEUVERING = "FLIGHT_MANEUVERING"  # Маневрирование
    DOCKING_APPROACH = "DOCKING_APPROACH"  # Подлет к станции
    DOCKING_ENGAGED = "DOCKING_ENGAGED"  # Стыковка выполнена
    EMERGENCY_STOP = "EMERGENCY_STOP"  # Аварийная остановка
    SYSTEMS_ERROR = "SYSTEMS_ERROR"  # Ошибка систем корабля


def _map_ship_state_to_fsm_state_enum(ship_state_name: str) -> int:
    if ship_state_name == ShipState.SHIP_STARTUP.value:
        return FSMStateEnum.BOOTING
    if ship_state_name == ShipState.SHIP_IDLE.value:
        return FSMStateEnum.IDLE
    if ship_state_name in {
        ShipState.EMERGENCY_STOP.value,
        ShipState.SYSTEMS_ERROR.value,
    }:
        return FSMStateEnum.ERROR_STATE
    return FSMStateEnum.ACTIVE


def _get_ship_state_name(snapshot: FSMState) -> str:
    try:
        name = snapshot.context_data.get(_SHIP_STATE_CONTEXT_KEY)
    except Exception:
        name = None
    if not name:
        return ShipState.SHIP_STARTUP.value
    return str(name)


class ShipContext:
    """Контекст состояния корабля для принятия решений FSM."""

    def __init__(self, ship_core: ShipCore, actuator_controller: ShipActuatorController):
        self.ship_core = ship_core
        self.actuator_controller = actuator_controller

    def is_ship_systems_ok(self) -> bool:
        """Проверяет, в порядке ли основные системы корабля."""
        try:
            hull = self.ship_core.get_hull_status()
            power = self.ship_core.get_power_status()
            life_support = self.ship_core.get_life_support_status()
            computing = self.ship_core.get_computing_status()

            # Критичные проверки для безопасности
            systems_ok = all(
                [
                    hull.integrity > 50.0,  # Корпус не критично поврежден
                    power.reactor_output_mw > 0,  # Реактор работает
                    power.battery_charge_mwh > 0,  # Есть аварийное питание
                    18 <= life_support.atmosphere.get("oxygen_percent", 0) <= 25,  # Кислород в норме
                    life_support.atmosphere.get("co2_ppm", 0) < 5000,  # CO2 не критичен
                    computing.qiki_core_status == "active",  # QIKI активен
                ]
            )

            if not systems_ok:
                logger.warning("Ship systems check failed - some critical systems degraded")

            return systems_ok

        except Exception as e:
            logger.error(f"Error checking ship systems: {e}")
            return False

    def has_navigation_capability(self) -> bool:
        """Проверяет способность к навигации."""
        try:
            sensors = self.ship_core.get_sensor_status()
            propulsion = self.ship_core.get_propulsion_status()

            # Нужны радар и навигационный компьютер + работающие двигатели
            navigation_ok = all(
                [
                    "long_range_radar" in sensors.active_sensors,
                    "navigation_computer" in sensors.active_sensors,
                    propulsion.main_drive_status in ["ready", "idle", "active"],
                    propulsion.main_drive_fuel_kg > 10,  # Минимум топлива
                ]
            )

            return navigation_ok

        except Exception as e:
            logger.error(f"Error checking navigation capability: {e}")
            return False

    def is_docking_target_in_range(self) -> bool:
        """Проверяет, есть ли цель для стыковки в радиусе действия."""
        track = self._get_best_station_track()
        if track is None:
            return False
        try:
            range_m = float(getattr(track, "range_m", 0.0) or 0.0)
        except Exception:
            return False
        if range_m <= 0.0:
            return False
        threshold_m = float(os.getenv("QIKI_DOCKING_TARGET_RANGE_M", "5000.0"))
        return range_m <= threshold_m

    def is_docking_engaged(self) -> bool:
        """Проверяет, выполнена ли стыковка (по данным сенсоров/радар трека)."""
        track = self._get_best_station_track()
        if track is None:
            return False
        try:
            range_m = float(getattr(track, "range_m", 0.0) or 0.0)
            vr_mps = float(getattr(track, "vr_mps", 0.0) or 0.0)
        except Exception:
            return False
        if range_m <= 0.0:
            return False
        engaged_range_m = float(os.getenv("QIKI_DOCKING_ENGAGED_RANGE_M", "20.0"))
        max_abs_vr_mps = float(os.getenv("QIKI_DOCKING_MAX_ABS_VR_MPS", "0.5"))
        if range_m > engaged_range_m:
            return False
        if abs(vr_mps) > max_abs_vr_mps:
            return False
        return True

    def _get_best_station_track(self) -> Optional[Any]:
        """Возвращает ближайший радар трек типа STATION, если доступен."""
        try:
            from radar.v1 import radar_pb2
        except Exception:
            return None

        best_track: Optional[Any] = None
        best_range_m: Optional[float] = None
        for reading in self.ship_core.iter_latest_sensor_readings():
            try:
                if not getattr(reading, "HasField", None):
                    continue
                if not reading.HasField("radar_track"):
                    continue
                track = reading.radar_track
            except Exception:
                continue
            try:
                if track.object_type != radar_pb2.ObjectType.STATION:
                    continue
                range_m = float(getattr(track, "range_m", 0.0) or 0.0)
            except Exception:
                continue
            if range_m <= 0.0:
                continue
            if best_range_m is None or range_m < best_range_m:
                best_track = track
                best_range_m = range_m
        return best_track

    def get_current_propulsion_mode(self) -> PropulsionMode:
        """Получает текущий режим двигательной системы."""
        return self.actuator_controller.current_mode


class ShipFSMHandler(IFSMHandler):
    """
    FSM Handler для управления состояниями космического корабля.
    Управляет переходами между состояниями: запуск, ожидание, полет, стыковка, аварийные режимы.
    """

    def __init__(self, ship_core: ShipCore, actuator_controller: ShipActuatorController):
        self.ship_context = ShipContext(ship_core, actuator_controller)
        self.ship_core = ship_core
        self.actuator_controller = actuator_controller
        logger.info("ShipFSMHandler initialized for spacecraft operations.")

    def process_fsm_state(self, current_fsm_state: FSMState) -> FSMState:
        """Обрабатывает текущее состояние FSM корабля и определяет следующее состояние."""
        current_ship_state_name = _get_ship_state_name(current_fsm_state)
        logger.debug(f"Processing ship FSM state: {current_ship_state_name}")

        next_state = FSMState()
        next_state.CopyFrom(current_fsm_state)

        # Анализ текущего состояния систем корабля
        current_state = current_ship_state_name
        systems_ok = self.ship_context.is_ship_systems_ok()
        nav_capable = self.ship_context.has_navigation_capability()
        docking_target = self.ship_context.is_docking_target_in_range()
        propulsion_mode = self.ship_context.get_current_propulsion_mode()

        # Логика переходов состояний
        new_state_name = current_state
        trigger_event = ""

        # Состояние: ЗАПУСК КОРАБЛЯ
        if current_state == ShipState.SHIP_STARTUP.value:
            if systems_ok and nav_capable:
                new_state_name = ShipState.SHIP_IDLE.value
                trigger_event = "SHIP_SYSTEMS_ONLINE"
                logger.info("🚀 Ship startup complete - all systems online")
            elif systems_ok and not nav_capable:
                new_state_name = ShipState.SHIP_IDLE.value
                trigger_event = "SHIP_SYSTEMS_PARTIAL"
                logger.warning("⚠️ Ship startup with limited navigation capability")
            else:
                new_state_name = ShipState.SYSTEMS_ERROR.value
                trigger_event = "CRITICAL_SYSTEMS_FAILURE"
                logger.error("❌ Ship startup failed - critical systems offline")

        # Состояние: ГОТОВНОСТЬ
        elif current_state == ShipState.SHIP_IDLE.value:
            if not systems_ok:
                new_state_name = ShipState.SYSTEMS_ERROR.value
                trigger_event = "SYSTEMS_DEGRADED"
                logger.error("🚨 Systems failure detected - entering error state")
            elif propulsion_mode == PropulsionMode.CRUISE:
                new_state_name = ShipState.FLIGHT_CRUISE.value
                trigger_event = "MAIN_DRIVE_ENGAGED"
                logger.info("🌟 Entering cruise flight mode")
            elif propulsion_mode == PropulsionMode.MANEUVERING:
                new_state_name = ShipState.FLIGHT_MANEUVERING.value
                trigger_event = "RCS_MANEUVERING_ACTIVE"
                logger.info("🎯 Entering maneuvering mode")
            elif docking_target:
                new_state_name = ShipState.DOCKING_APPROACH.value
                trigger_event = "DOCKING_TARGET_ACQUIRED"
                logger.info("🎯 Docking target acquired - approaching")

        # Состояние: КРЕЙСЕРСКИЙ ПОЛЕТ
        elif current_state == ShipState.FLIGHT_CRUISE.value:
            if not systems_ok:
                new_state_name = ShipState.EMERGENCY_STOP.value
                trigger_event = "EMERGENCY_SYSTEMS_FAILURE"
                logger.error("🚨 Emergency stop - systems failure during cruise")
                self._execute_emergency_stop()
            elif propulsion_mode == PropulsionMode.MANEUVERING:
                new_state_name = ShipState.FLIGHT_MANEUVERING.value
                trigger_event = "SWITCHING_TO_MANEUVERING"
                logger.info("🎯 Switching from cruise to maneuvering")
            elif propulsion_mode == PropulsionMode.IDLE:
                new_state_name = ShipState.SHIP_IDLE.value
                trigger_event = "FLIGHT_COMPLETED"
                logger.info("✅ Flight completed - returning to idle")

        # Состояние: МАНЕВРИРОВАНИЕ
        elif current_state == ShipState.FLIGHT_MANEUVERING.value:
            if not systems_ok:
                new_state_name = ShipState.EMERGENCY_STOP.value
                trigger_event = "EMERGENCY_SYSTEMS_FAILURE"
                logger.error("🚨 Emergency stop during maneuvering")
                self._execute_emergency_stop()
            elif propulsion_mode == PropulsionMode.CRUISE:
                new_state_name = ShipState.FLIGHT_CRUISE.value
                trigger_event = "SWITCHING_TO_CRUISE"
                logger.info("🌟 Switching from maneuvering to cruise")
            elif propulsion_mode == PropulsionMode.IDLE:
                new_state_name = ShipState.SHIP_IDLE.value
                trigger_event = "MANEUVERING_COMPLETED"
                logger.info("✅ Maneuvering completed")
            elif docking_target:
                new_state_name = ShipState.DOCKING_APPROACH.value
                trigger_event = "DOCKING_TARGET_IN_RANGE"
                logger.info("🎯 Docking target in range - beginning approach")

        # Состояние: ПОДЛЕТ К СТЫКОВКЕ
        elif current_state == ShipState.DOCKING_APPROACH.value:
            if not systems_ok:
                new_state_name = ShipState.EMERGENCY_STOP.value
                trigger_event = "EMERGENCY_DURING_DOCKING"
                logger.error("🚨 Emergency during docking approach")
                self._execute_emergency_stop()
            elif self.ship_context.is_docking_engaged():
                new_state_name = ShipState.DOCKING_ENGAGED.value
                trigger_event = "DOCKING_COMPLETE"
                logger.info("✅ Docking complete - engaged")
            elif not docking_target:
                new_state_name = ShipState.FLIGHT_MANEUVERING.value
                trigger_event = "DOCKING_TARGET_LOST"
                logger.warning("⚠️ Docking target lost - returning to maneuvering")

        # Состояние: АВАРИЙНАЯ ОСТАНОВКА
        elif current_state == ShipState.EMERGENCY_STOP.value:
            if systems_ok and propulsion_mode == PropulsionMode.EMERGENCY:
                new_state_name = ShipState.SHIP_IDLE.value
                trigger_event = "EMERGENCY_CLEARED"
                logger.info("✅ Emergency cleared - returning to normal operations")

        # Состояние: ОШИБКА СИСТЕМ
        elif current_state == ShipState.SYSTEMS_ERROR.value:
            if systems_ok:
                new_state_name = ShipState.SHIP_IDLE.value
                trigger_event = "SYSTEMS_RECOVERED"
                logger.info("✅ Systems recovered - returning to idle")

        # Выполнение перехода состояния
        if new_state_name != current_state:
            logger.info(f"🔄 Ship FSM Transition: {current_state} -> {new_state_name} (Trigger: {trigger_event})")

            from_fsm_state = _map_ship_state_to_fsm_state_enum(current_state)
            to_fsm_state = _map_ship_state_to_fsm_state_enum(new_state_name)

            new_transition = StateTransition(
                from_state=from_fsm_state,
                to_state=to_fsm_state,
                trigger_event=trigger_event,
                status=FSMTransitionStatus.SUCCESS,
            )
            new_transition.timestamp.GetCurrentTime()

            next_state.history.append(new_transition)

        try:
            next_state.context_data[_SHIP_STATE_CONTEXT_KEY] = new_state_name
        except Exception:
            pass

        next_state.current_state = _map_ship_state_to_fsm_state_enum(new_state_name)

        next_state.timestamp.GetCurrentTime()

        logger.debug(f"Ship FSM new state: {_get_ship_state_name(next_state)}")
        return next_state

    async def process_fsm_dto(self, current_fsm_state: Any) -> Any:
        raise NotImplementedError(
            "ShipFSMHandler.process_fsm_dto is not implemented. "
            "Use qiki.services.q_core_agent.core.fsm_handler.FSMHandler for the canonical FSM DTO path."
        )

    def _execute_emergency_stop(self):
        """Выполняет аварийную остановку всех систем корабля."""
        try:
            logger.warning("🚨 Executing emergency stop procedures")
            success = self.actuator_controller.emergency_stop()
            if success:
                logger.info("✅ Emergency stop completed successfully")
            else:
                logger.error("❌ Emergency stop failed - manual intervention required")
        except Exception as e:
            logger.error(f"❌ Emergency stop execution failed: {e}")

    def get_ship_state_summary(self) -> Dict[str, Any]:
        """Получает краткую сводку состояния корабля для диагностики."""
        try:
            systems_ok = self.ship_context.is_ship_systems_ok()
            nav_capable = self.ship_context.has_navigation_capability()
            propulsion_mode = self.ship_context.get_current_propulsion_mode()

            return {
                "systems_operational": systems_ok,
                "navigation_capable": nav_capable,
                "propulsion_mode": propulsion_mode.value,
                "ship_id": self.ship_core.get_id(),
                "ready_for_flight": systems_ok and nav_capable,
            }
        except Exception as e:
            logger.error(f"Error getting ship state summary: {e}")
            return {"error": str(e)}


# Пример использования и тестирования
if __name__ == "__main__":
    try:
        # Инициализация корабельных систем
        q_core_agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ship = ShipCore(base_path=q_core_agent_root)
        controller = ShipActuatorController(ship)

        # Инициализация FSM handler
        fsm_handler = ShipFSMHandler(ship, controller)

        print("=== SHIP FSM HANDLER TEST ===")
        print(f"Ship: {ship.get_id()}")
        print()

        # Создание начального состояния
        initial_state = FSMState()
        initial_state.current_state = FSMStateEnum.BOOTING
        initial_state.context_data[_SHIP_STATE_CONTEXT_KEY] = ShipState.SHIP_STARTUP.value

        print(f"Initial state: {_get_ship_state_name(initial_state)}")

        # Симуляция нескольких циклов FSM
        current_state = initial_state
        for i in range(5):
            print(f"\n--- FSM Cycle {i + 1} ---")
            next_state = fsm_handler.process_fsm_state(current_state)
            print(f"State: {_get_ship_state_name(next_state)}")

            # Получение сводки состояния
            summary = fsm_handler.get_ship_state_summary()
            print(f"Summary: {summary}")

            # Симуляция активности (включение главного двигателя на 3-м цикле)
            if i == 2:
                print("Simulating main drive activation...")
                controller.set_main_drive_thrust(50.0)

            current_state = next_state

            # Прерывание если состояние не меняется
            if i > 0 and _get_ship_state_name(current_state) == _get_ship_state_name(next_state):
                print("State stabilized.")
                break

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
