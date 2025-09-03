from __future__ import annotations
from enum import Enum


class FSMState(Enum):
    """Перечисление состояний FSM."""

    IDLE = "idle"
    ACTIVE = "active"
    SHUTDOWN = "shutdown"
