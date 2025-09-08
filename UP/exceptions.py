class ControllerError(Exception):
    """Базовое исключение для контроллеров."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class ActuatorError(ControllerError):
    """Ошибка исполнительного механизма."""


class FSMError(ControllerError):
    """Ошибка FSM обработчика."""
