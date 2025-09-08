from __future__ import annotations

from common.result import OperationResult
from .exceptions import ActuatorError


class ActuatorController:
    """Простой контроллер актуаторов."""

    def __init__(self) -> None:
        self._thrust = 0.0

    def set_thrust(self, value: float) -> OperationResult:
        """Устанавливает тягу основного двигателя.

        Параметры:
            value: значение от 0 до 1.
        """
        try:
            if not 0 <= value <= 1:
                raise ActuatorError("INVALID_THRUST", "Thrust must be between 0 and 1")
            self._thrust = value
            return OperationResult(
                success=True, message="Thrust updated", data={"value": value}
            )
        except ActuatorError as exc:
            return OperationResult(
                success=False, error_code=exc.error_code, message=exc.message
            )
