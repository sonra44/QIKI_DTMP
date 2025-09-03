from __future__ import annotations

from dataclasses import dataclass

from .enums import FSMState


@dataclass
class FSMStateProto:
    """Упрощённая protobuf-структура состояния FSM."""

    current_state: FSMState
