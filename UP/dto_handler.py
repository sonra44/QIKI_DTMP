from __future__ import annotations

from .dto import FsmSnapshotDTO
from .enums import FSMState
from .fsm_engine import FSMEngine


class DTOFSMHandler(FSMEngine[FSMState, FsmSnapshotDTO]):
    """Обработчик FSM для DTO-версии протокола."""

    def __init__(self) -> None:
        super().__init__()
        self.register(FSMState.IDLE, self._on_idle)
        self.register(FSMState.ACTIVE, self._on_active)

    async def _on_idle(self, snapshot: FsmSnapshotDTO) -> FsmSnapshotDTO:
        snapshot.state = FSMState.ACTIVE
        return snapshot

    async def _on_active(self, snapshot: FsmSnapshotDTO) -> FsmSnapshotDTO:
        snapshot.state = FSMState.SHUTDOWN
        return snapshot

    async def handle(self, snapshot: FsmSnapshotDTO) -> FsmSnapshotDTO:
        return await self.process_transition(snapshot.state, snapshot)
