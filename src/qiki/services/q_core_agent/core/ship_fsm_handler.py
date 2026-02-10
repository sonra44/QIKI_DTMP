"""
Ship FSM Handler - конечный автомат для управления космическим кораблем.
Управляет состояниями корабля: загрузка, режим ожидания, полет, стыковка, аварийные состояния.
"""

import os
import sys
import time
import math

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

from typing import Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

try:
    from .interfaces import IFSMHandler
    from .agent_logger import logger
    from .ship_core import ShipCore
    from .ship_actuators import ActuationResult, ActuationStatus, ShipActuatorController, PropulsionMode
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
    ActuationResult = ship_actuators.ActuationResult
    ActuationStatus = ship_actuators.ActuationStatus

from fsm_state_pb2 import (
    FsmStateSnapshot as FSMState,
    StateTransition,
    FSMStateEnum,
    FSMTransitionStatus,
)

_SHIP_STATE_CONTEXT_KEY = "ship_state_name"
_DOCKING_CONFIRM_HITS_KEY = "docking_confirm_hits"
_SAFE_MODE_REASON_KEY = "safe_mode_reason"
_SAFE_MODE_REQUEST_REASON_KEY = "safe_mode_request_reason"
_SAFE_MODE_EXIT_HITS_KEY = "safe_mode_exit_hits"
_SAFE_MODE_BIOS_OK_KEY = "safe_bios_ok"
_SAFE_MODE_SENSORS_OK_KEY = "safe_sensors_ok"
_SAFE_MODE_PROVIDER_OK_KEY = "safe_provider_ok"
_LAST_ACTUATION_COMMAND_ID_KEY = "last_actuation_command_id"
_LAST_ACTUATION_STATUS_KEY = "last_actuation_status"
_LAST_ACTUATION_TIMESTAMP_KEY = "last_actuation_timestamp"
_LAST_ACTUATION_REASON_KEY = "last_actuation_reason"
_LAST_ACTUATION_IS_FALLBACK_KEY = "last_actuation_is_fallback"
_LAST_ACTUATION_ACTION_KEY = "last_actuation_action"


class SensorTrustReason(str, Enum):
    OK = "OK"
    NO_DATA = "NO_DATA"
    STALE = "STALE"
    LOW_QUALITY = "LOW_QUALITY"
    INVALID = "INVALID"
    MISSING_FIELDS = "MISSING_FIELDS"


@dataclass(frozen=True)
class TrustedSensorFrame:
    ok: bool
    reason: SensorTrustReason
    age_s: Optional[float] = None
    quality: Optional[float] = None
    data: Optional[Dict[str, float]] = None
    is_fallback: bool = False


@dataclass(frozen=True)
class LastActuation:
    command_id: str
    status: ActuationStatus
    timestamp: float
    reason: str
    is_fallback: bool = False
    action: str = ""


class ShipState(Enum):
    """Состояния космического корабля."""

    SHIP_STARTUP = "SHIP_STARTUP"  # Запуск систем корабля
    SHIP_IDLE = "SHIP_IDLE"  # Готов к полету, системы в режиме ожидания
    FLIGHT_CRUISE = "FLIGHT_CRUISE"  # Крейсерский полет
    FLIGHT_MANEUVERING = "FLIGHT_MANEUVERING"  # Маневрирование
    DOCKING_APPROACH = "DOCKING_APPROACH"  # Подлет к станции
    DOCKING_ENGAGED = "DOCKING_ENGAGED"  # Стыковка выполнена
    SAFE_MODE = "SAFE_MODE"  # Безопасный удерживающий режим
    EMERGENCY_STOP = "EMERGENCY_STOP"  # Аварийная остановка
    SYSTEMS_ERROR = "SYSTEMS_ERROR"  # Ошибка систем корабля


class SafeModeReason(Enum):
    BIOS_UNAVAILABLE = "BIOS_UNAVAILABLE"
    BIOS_INVALID = "BIOS_INVALID"
    SENSORS_UNAVAILABLE = "SENSORS_UNAVAILABLE"
    SENSORS_STALE = "SENSORS_STALE"
    ACTUATOR_UNAVAILABLE = "ACTUATOR_UNAVAILABLE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


def _safe_set_context_data(context_data: Any, key: str, value: str) -> None:
    try:
        context_data[key] = value
    except Exception:
        logger.debug("ship_fsm_context_data_set_failed", exc_info=True)


def _safe_get_context_data(context_data: Any, key: str, default: str = "") -> str:
    try:
        value = context_data.get(key, default)
    except Exception:
        return default
    if value is None:
        return default
    return str(value)


def _safe_parse_bool(raw: str) -> Optional[bool]:
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _safe_parse_float(raw: str, *, default: float = 0.0) -> float:
    try:
        return float(raw)
    except Exception:
        return default


def _safe_parse_actuation_status(raw: str) -> Optional[ActuationStatus]:
    normalized = raw.strip().lower()
    for status in ActuationStatus:
        if normalized == status.value:
            return status
    return None


def _is_truthy(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _serialize_last_actuation(context_data: Any, actuation: LastActuation) -> None:
    _safe_set_context_data(context_data, _LAST_ACTUATION_COMMAND_ID_KEY, actuation.command_id)
    _safe_set_context_data(context_data, _LAST_ACTUATION_STATUS_KEY, actuation.status.value)
    _safe_set_context_data(context_data, _LAST_ACTUATION_TIMESTAMP_KEY, f"{actuation.timestamp:.6f}")
    _safe_set_context_data(context_data, _LAST_ACTUATION_REASON_KEY, actuation.reason)
    _safe_set_context_data(context_data, _LAST_ACTUATION_IS_FALLBACK_KEY, "1" if actuation.is_fallback else "0")
    _safe_set_context_data(context_data, _LAST_ACTUATION_ACTION_KEY, actuation.action)


def _deserialize_last_actuation(context_data: Any) -> Optional[LastActuation]:
    status = _safe_parse_actuation_status(_safe_get_context_data(context_data, _LAST_ACTUATION_STATUS_KEY))
    if status is None:
        return None
    return LastActuation(
        command_id=_safe_get_context_data(context_data, _LAST_ACTUATION_COMMAND_ID_KEY),
        status=status,
        timestamp=_safe_parse_float(_safe_get_context_data(context_data, _LAST_ACTUATION_TIMESTAMP_KEY), default=0.0),
        reason=_safe_get_context_data(context_data, _LAST_ACTUATION_REASON_KEY),
        is_fallback=_is_truthy(_safe_get_context_data(context_data, _LAST_ACTUATION_IS_FALLBACK_KEY)),
        action=_safe_get_context_data(context_data, _LAST_ACTUATION_ACTION_KEY),
    )


def _normalize_safe_mode_reason(raw_reason: str) -> str:
    normalized = raw_reason.strip().upper()
    valid_reasons = {reason.value for reason in SafeModeReason}
    if normalized in valid_reasons:
        return normalized
    return SafeModeReason.UNKNOWN.value


def _map_ship_state_to_fsm_state_enum(ship_state_name: str) -> int:
    if ship_state_name == ShipState.SHIP_STARTUP.value:
        return FSMStateEnum.BOOTING
    if ship_state_name == ShipState.SHIP_IDLE.value:
        return FSMStateEnum.IDLE
    if ship_state_name in {
        ShipState.EMERGENCY_STOP.value,
        ShipState.SYSTEMS_ERROR.value,
        ShipState.SAFE_MODE.value,
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
        trusted = self.get_trusted_station_track()
        if not trusted.ok or trusted.data is None:
            return False
        range_m = float(trusted.data["range_m"])
        threshold_m = float(os.getenv("QIKI_DOCKING_TARGET_RANGE_M", "5000.0"))
        return range_m <= threshold_m

    def evaluate_sensor_frame(self, raw_frame: Optional[Any]) -> TrustedSensorFrame:
        if raw_frame is None:
            return TrustedSensorFrame(ok=False, reason=SensorTrustReason.NO_DATA)
        if not hasattr(raw_frame, "range_m") or not hasattr(raw_frame, "vr_mps"):
            return TrustedSensorFrame(ok=False, reason=SensorTrustReason.MISSING_FIELDS)
        try:
            range_m = float(getattr(raw_frame, "range_m"))
            vr_mps = float(getattr(raw_frame, "vr_mps"))
        except Exception:
            return TrustedSensorFrame(ok=False, reason=SensorTrustReason.MISSING_FIELDS)
        if not math.isfinite(range_m) or not math.isfinite(vr_mps):
            return TrustedSensorFrame(ok=False, reason=SensorTrustReason.INVALID)
        if range_m <= 0.0:
            return TrustedSensorFrame(ok=False, reason=SensorTrustReason.INVALID)
        max_age_s = float(os.getenv("QIKI_SENSOR_MAX_AGE_S", "2.0"))
        age_s = self._get_track_age_seconds(raw_frame)
        if age_s is not None and age_s > max_age_s:
            return TrustedSensorFrame(ok=False, reason=SensorTrustReason.STALE, age_s=age_s)
        quality = self._get_track_quality(raw_frame)
        if quality is not None:
            min_quality = float(os.getenv("QIKI_SENSOR_MIN_QUALITY", "0.5"))
            if not math.isfinite(quality):
                return TrustedSensorFrame(ok=False, reason=SensorTrustReason.INVALID, age_s=age_s)
            if quality < min_quality:
                return TrustedSensorFrame(
                    ok=False,
                    reason=SensorTrustReason.LOW_QUALITY,
                    age_s=age_s,
                    quality=quality,
                )
        normalized: Dict[str, float] = {"range_m": range_m, "vr_mps": vr_mps}
        if quality is not None:
            normalized["quality"] = quality
        return TrustedSensorFrame(
            ok=True,
            reason=SensorTrustReason.OK,
            age_s=age_s,
            quality=quality,
            data=normalized,
        )

    def get_trusted_station_track(self) -> TrustedSensorFrame:
        track = self._get_best_station_track()
        return self.evaluate_sensor_frame(track)

    def validate_station_track(self, track: Optional[Any]) -> TrustedSensorFrame:
        # Backward-compatible wrapper used by legacy callers/tests.
        return self.evaluate_sensor_frame(track)

    def is_docking_engaged(self, current_confirm_hits: int = 0) -> Tuple[bool, str, int]:
        """Проверяет, выполнена ли стыковка (по валидным данным сенсоров/радар трека)."""
        trusted = self.get_trusted_station_track()
        if not trusted.ok or trusted.data is None:
            return False, trusted.reason.value, 0
        range_m = float(trusted.data["range_m"])
        vr_mps = float(trusted.data["vr_mps"])
        engaged_range_m = float(os.getenv("QIKI_DOCKING_ENGAGED_RANGE_M", "20.0"))
        max_abs_vr_mps = float(os.getenv("QIKI_DOCKING_MAX_ABS_VR_MPS", "0.5"))
        if range_m > engaged_range_m:
            return False, SensorTrustReason.INVALID.value, 0
        if abs(vr_mps) > max_abs_vr_mps:
            return False, SensorTrustReason.INVALID.value, 0
        required_confirmations = max(1, int(os.getenv("QIKI_DOCKING_CONFIRMATION_COUNT", "3")))
        if trusted.age_s is None or trusted.quality is None:
            required_confirmations += 1
        next_hits = current_confirm_hits + 1
        if next_hits < required_confirmations:
            return False, f"DOCKING_CONFIRMING_{next_hits}_OF_{required_confirmations}", next_hits
        return True, "DOCKING_CONFIRMED", next_hits

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

    @staticmethod
    def _track_has_timestamp(track: Any) -> bool:
        try:
            if hasattr(track, "HasField"):
                return bool(track.HasField("timestamp"))
        except Exception:
            return False
        return False

    @staticmethod
    def _track_has_quality(track: Any) -> bool:
        return hasattr(track, "quality")

    @staticmethod
    def _get_track_quality(track: Any) -> Optional[float]:
        if not hasattr(track, "quality"):
            return None
        try:
            return float(getattr(track, "quality"))
        except Exception:
            return None

    @staticmethod
    def _get_track_age_seconds(track: Any) -> Optional[float]:
        try:
            if hasattr(track, "HasField") and track.HasField("timestamp"):
                ts = track.timestamp
                published_s = float(ts.seconds) + (float(ts.nanos) / 1_000_000_000.0)
                return max(0.0, time.time() - published_s)
        except Exception:
            return None
        try:
            age_s = float(getattr(track, "age_s"))
            if math.isfinite(age_s) and age_s >= 0.0:
                return age_s
        except Exception:
            return None
        return None

    def get_current_propulsion_mode(self) -> PropulsionMode:
        """Получает текущий режим двигательной системы."""
        return self.actuator_controller.current_mode

    def get_last_actuation(self) -> Optional[LastActuation]:
        """Returns the latest actuator fact if controller exposes it."""
        try:
            getter = getattr(self.actuator_controller, "get_last_actuation", None)
            raw_result = getter() if callable(getter) else getattr(self.actuator_controller, "last_actuation", None)
        except Exception:
            logger.debug("ship_fsm_last_actuation_fetch_failed", exc_info=True)
            return None
        if raw_result is None:
            return None
        if not isinstance(raw_result, ActuationResult):
            return None
        return LastActuation(
            command_id=str(raw_result.command_id),
            status=raw_result.status,
            timestamp=float(getattr(raw_result, "timestamp", 0.0) or 0.0),
            reason=str(raw_result.reason or ""),
            is_fallback=bool(raw_result.is_fallback),
            action=str(getattr(raw_result, "action", "") or ""),
        )


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
        safe_mode_request_reason = _normalize_safe_mode_reason(
            _safe_get_context_data(current_fsm_state.context_data, _SAFE_MODE_REQUEST_REASON_KEY)
        )
        safe_mode_reason = _normalize_safe_mode_reason(
            _safe_get_context_data(current_fsm_state.context_data, _SAFE_MODE_REASON_KEY)
        )
        bios_ok_hint = _safe_parse_bool(_safe_get_context_data(current_fsm_state.context_data, _SAFE_MODE_BIOS_OK_KEY))
        sensors_ok_hint = _safe_parse_bool(
            _safe_get_context_data(current_fsm_state.context_data, _SAFE_MODE_SENSORS_OK_KEY)
        )
        provider_ok_hint = _safe_parse_bool(
            _safe_get_context_data(current_fsm_state.context_data, _SAFE_MODE_PROVIDER_OK_KEY)
        )
        last_actuation = self.ship_context.get_last_actuation() or _deserialize_last_actuation(current_fsm_state.context_data)
        if last_actuation is not None:
            _serialize_last_actuation(next_state.context_data, last_actuation)

        def _matches_action(expected_prefix: str) -> bool:
            if last_actuation is None:
                return False
            return last_actuation.action.startswith(expected_prefix)

        def _actuation_gate(expected_prefix: str, pending_trigger: str, missing_trigger: str, rejected_trigger: str) -> tuple[bool, str]:
            if last_actuation is None or not _matches_action(expected_prefix):
                return False, missing_trigger
            if last_actuation.status == ActuationStatus.EXECUTED:
                return True, ""
            if last_actuation.status == ActuationStatus.ACCEPTED:
                return False, pending_trigger
            if last_actuation.status == ActuationStatus.REJECTED:
                return False, rejected_trigger
            return False, f"{pending_trigger}_{last_actuation.status.name}"

        force_safe_mode = safe_mode_request_reason != SafeModeReason.UNKNOWN.value
        if not force_safe_mode and bios_ok_hint is False:
            force_safe_mode = True
            safe_mode_reason = SafeModeReason.BIOS_UNAVAILABLE.value
        if not force_safe_mode and sensors_ok_hint is False:
            force_safe_mode = True
            safe_mode_reason = SafeModeReason.SENSORS_UNAVAILABLE.value
        if not force_safe_mode and provider_ok_hint is False:
            force_safe_mode = True
            safe_mode_reason = SafeModeReason.PROVIDER_UNAVAILABLE.value
        if (
            not force_safe_mode
            and last_actuation is not None
            and last_actuation.status in {ActuationStatus.TIMEOUT, ActuationStatus.UNAVAILABLE, ActuationStatus.FAILED}
            and (
                last_actuation.action.startswith("set_main_drive_thrust")
                or last_actuation.action.startswith("fire_rcs_thruster:")
            )
        ):
            force_safe_mode = True
            safe_mode_reason = SafeModeReason.ACTUATOR_UNAVAILABLE.value

        # Логика переходов состояний
        new_state_name = current_state
        trigger_event = ""
        if safe_mode_reason == SafeModeReason.UNKNOWN.value and safe_mode_request_reason != SafeModeReason.UNKNOWN.value:
            safe_mode_reason = safe_mode_request_reason
        if current_state != ShipState.SAFE_MODE.value and force_safe_mode:
            new_state_name = ShipState.SAFE_MODE.value
            trigger_event = f"SAFE_MODE_ENTER_{safe_mode_reason}"
            _safe_set_context_data(next_state.context_data, _SAFE_MODE_REASON_KEY, safe_mode_reason)
            _safe_set_context_data(next_state.context_data, _SAFE_MODE_EXIT_HITS_KEY, "0")
            _safe_set_context_data(next_state.context_data, _SAFE_MODE_REQUEST_REASON_KEY, "")
            self._execute_emergency_stop()
        elif current_state == ShipState.SAFE_MODE.value:
            required_safe_exit_hits = max(1, int(os.getenv("QIKI_SAFE_EXIT_CONFIRMATION_COUNT", "3")))
            try:
                current_safe_exit_hits = int(
                    _safe_get_context_data(current_fsm_state.context_data, _SAFE_MODE_EXIT_HITS_KEY, "0")
                )
            except Exception:
                current_safe_exit_hits = 0
            bios_ok = bios_ok_hint if bios_ok_hint is not None else systems_ok
            sensors_ok = sensors_ok_hint if sensors_ok_hint is not None else nav_capable
            provider_ok = provider_ok_hint if provider_ok_hint is not None else True
            if bios_ok and sensors_ok and provider_ok:
                next_safe_exit_hits = current_safe_exit_hits + 1
                _safe_set_context_data(next_state.context_data, _SAFE_MODE_EXIT_HITS_KEY, str(next_safe_exit_hits))
                _safe_set_context_data(next_state.context_data, _SAFE_MODE_REASON_KEY, safe_mode_reason)
                _safe_set_context_data(next_state.context_data, _SAFE_MODE_REQUEST_REASON_KEY, "")
                if next_safe_exit_hits >= required_safe_exit_hits:
                    new_state_name = ShipState.SHIP_IDLE.value
                    trigger_event = "SAFE_MODE_EXIT_CONFIRMED"
                else:
                    trigger_event = f"SAFE_MODE_RECOVERING_{next_safe_exit_hits}_OF_{required_safe_exit_hits}"
            else:
                if not bios_ok:
                    safe_mode_reason = SafeModeReason.BIOS_UNAVAILABLE.value
                elif not sensors_ok:
                    safe_mode_reason = SafeModeReason.SENSORS_UNAVAILABLE.value
                elif not provider_ok:
                    safe_mode_reason = SafeModeReason.PROVIDER_UNAVAILABLE.value
                _safe_set_context_data(next_state.context_data, _SAFE_MODE_EXIT_HITS_KEY, "0")
                _safe_set_context_data(next_state.context_data, _SAFE_MODE_REASON_KEY, safe_mode_reason)
                _safe_set_context_data(next_state.context_data, _SAFE_MODE_REQUEST_REASON_KEY, "")
                trigger_event = f"SAFE_MODE_HOLD_{safe_mode_reason}"

        # Состояние: ЗАПУСК КОРАБЛЯ
        if new_state_name != current_state:
            pass
        elif current_state == ShipState.SHIP_STARTUP.value:
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
                can_transition, gate_trigger = _actuation_gate(
                    expected_prefix="set_main_drive_thrust",
                    pending_trigger="MAIN_DRIVE_ACCEPTED_PENDING_EXECUTION",
                    missing_trigger="MAIN_DRIVE_NO_ACTUATION_FACT",
                    rejected_trigger="MAIN_DRIVE_REJECTED",
                )
                if can_transition:
                    new_state_name = ShipState.FLIGHT_CRUISE.value
                    trigger_event = "MAIN_DRIVE_EXECUTED"
                    logger.info("🌟 Entering cruise flight mode")
                else:
                    trigger_event = gate_trigger
            elif propulsion_mode == PropulsionMode.MANEUVERING:
                can_transition, gate_trigger = _actuation_gate(
                    expected_prefix="fire_rcs_thruster:",
                    pending_trigger="RCS_ACCEPTED_PENDING_EXECUTION",
                    missing_trigger="RCS_NO_ACTUATION_FACT",
                    rejected_trigger="RCS_COMMAND_REJECTED",
                )
                if can_transition:
                    new_state_name = ShipState.FLIGHT_MANEUVERING.value
                    trigger_event = "RCS_EXECUTED_MANEUVERING_ACTIVE"
                    logger.info("🎯 Entering maneuvering mode")
                else:
                    trigger_event = gate_trigger
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
                can_transition, gate_trigger = _actuation_gate(
                    expected_prefix="fire_rcs_thruster:",
                    pending_trigger="RCS_ACCEPTED_PENDING_EXECUTION",
                    missing_trigger="RCS_NO_ACTUATION_FACT",
                    rejected_trigger="RCS_COMMAND_REJECTED",
                )
                if can_transition:
                    new_state_name = ShipState.FLIGHT_MANEUVERING.value
                    trigger_event = "SWITCHING_TO_MANEUVERING_EXECUTED"
                    logger.info("🎯 Switching from cruise to maneuvering")
                else:
                    trigger_event = gate_trigger
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
                can_transition, gate_trigger = _actuation_gate(
                    expected_prefix="set_main_drive_thrust",
                    pending_trigger="MAIN_DRIVE_ACCEPTED_PENDING_EXECUTION",
                    missing_trigger="MAIN_DRIVE_NO_ACTUATION_FACT",
                    rejected_trigger="MAIN_DRIVE_REJECTED",
                )
                if can_transition:
                    new_state_name = ShipState.FLIGHT_CRUISE.value
                    trigger_event = "SWITCHING_TO_CRUISE_EXECUTED"
                    logger.info("🌟 Switching from maneuvering to cruise")
                else:
                    trigger_event = gate_trigger
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
            current_confirm_hits = 0
            try:
                current_confirm_hits = int(current_fsm_state.context_data.get(_DOCKING_CONFIRM_HITS_KEY, "0"))
            except Exception:
                current_confirm_hits = 0
            if not systems_ok:
                new_state_name = ShipState.EMERGENCY_STOP.value
                trigger_event = "EMERGENCY_DURING_DOCKING"
                logger.error("🚨 Emergency during docking approach")
                self._execute_emergency_stop()
                _safe_set_context_data(next_state.context_data, _DOCKING_CONFIRM_HITS_KEY, "0")
            else:
                engaged, reason, next_confirm_hits = self.ship_context.is_docking_engaged(
                    current_confirm_hits=current_confirm_hits
                )
                if engaged:
                    new_state_name = ShipState.DOCKING_ENGAGED.value
                    trigger_event = "DOCKING_CONFIRMED"
                    logger.info("✅ Docking confirmed - engaged")
                    _safe_set_context_data(next_state.context_data, _DOCKING_CONFIRM_HITS_KEY, str(next_confirm_hits))
                elif not docking_target:
                    new_state_name = ShipState.FLIGHT_MANEUVERING.value
                    trigger_event = "DOCKING_TARGET_LOST"
                    logger.warning("⚠️ Docking target lost - returning to maneuvering")
                    _safe_set_context_data(next_state.context_data, _DOCKING_CONFIRM_HITS_KEY, "0")
                elif reason.startswith("DOCKING_CONFIRMING_"):
                    trigger_event = reason
                    _safe_set_context_data(next_state.context_data, _DOCKING_CONFIRM_HITS_KEY, str(next_confirm_hits))
                else:
                    trigger_event = "DOCKING_SENSOR_VALIDATION_FAILED"
                    _safe_set_context_data(next_state.context_data, _DOCKING_CONFIRM_HITS_KEY, "0")
            if trigger_event == "":
                _safe_set_context_data(next_state.context_data, _DOCKING_CONFIRM_HITS_KEY, str(current_confirm_hits))

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
        elif trigger_event:
            from_fsm_state = _map_ship_state_to_fsm_state_enum(current_state)
            observation_transition = StateTransition(
                from_state=from_fsm_state,
                to_state=from_fsm_state,
                trigger_event=trigger_event,
                status=FSMTransitionStatus.PENDING,
            )
            observation_transition.timestamp.GetCurrentTime()
            next_state.history.append(observation_transition)

        _safe_set_context_data(next_state.context_data, _SHIP_STATE_CONTEXT_KEY, new_state_name)

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
