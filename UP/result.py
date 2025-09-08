from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class OperationResult:
    """Результат операции контроллеров.

    Attributes:
        success: Флаг успешного выполнения.
        error_code: Код ошибки при неуспешном выполнении.
        message: Человеко-читаемое сообщение.
        data: Дополнительные данные результата.
    """

    success: bool
    error_code: Optional[str] = None
    message: str | None = None
    data: Any | None = None
