from common.result import OperationResult
from .exceptions import FSMError


class FSMHandler:
    """Минималистичный обработчик состояний."""

    allowed_states = {"IDLE", "RUNNING", "ERROR"}

    def __init__(self) -> None:
        self.state = "IDLE"

    def transition(self, new_state: str) -> OperationResult:
        """Переходит в новое состояние FSM."""
        try:
            if new_state not in self.allowed_states:
                raise FSMError("INVALID_STATE", f"Unknown state: {new_state}")
            self.state = new_state
            return OperationResult(
                success=True,
                message=f"State changed to {new_state}",
                data={"state": new_state},
            )
        except FSMError as exc:
            return OperationResult(
                success=False, error_code=exc.error_code, message=exc.message
            )
