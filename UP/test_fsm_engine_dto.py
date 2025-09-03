import asyncio

from core.fsm.dto import FsmSnapshotDTO
from core.fsm.dto_handler import DTOFSMHandler
from core.fsm.enums import FSMState


def test_dto_transitions() -> None:
    handler = DTOFSMHandler()
    snapshot = FsmSnapshotDTO(state=FSMState.IDLE)

    snapshot = asyncio.run(handler.handle(snapshot))
    assert snapshot.state == FSMState.ACTIVE

    snapshot = asyncio.run(handler.handle(snapshot))
    assert snapshot.state == FSMState.SHUTDOWN
