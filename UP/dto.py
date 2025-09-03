from __future__ import annotations

from dataclasses import dataclass

from .enums import FSMState


@dataclass
class FsmSnapshotDTO:
    """Простое DTO с текущим состоянием FSM."""

    state: FSMState
