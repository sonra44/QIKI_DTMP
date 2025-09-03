from __future__ import annotations

from .enums import FSMState
from .fsm_engine import FSMEngine
from .proto import FSMStateProto


class ProtoFSMHandler(FSMEngine[FSMState, FSMStateProto]):
    """Обработчик FSM для protobuf-версии протокола."""

    def __init__(self) -> None:
        super().__init__()
        self.register(FSMState.IDLE, self._on_idle)
        self.register(FSMState.ACTIVE, self._on_active)

    async def _on_idle(self, proto: FSMStateProto) -> FSMStateProto:
        proto.current_state = FSMState.ACTIVE
        return proto

    async def _on_active(self, proto: FSMStateProto) -> FSMStateProto:
        proto.current_state = FSMState.SHUTDOWN
        return proto

    async def handle(self, proto: FSMStateProto) -> FSMStateProto:
        return await self.process_transition(proto.current_state, proto)
