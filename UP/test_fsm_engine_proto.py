import asyncio

from core.fsm.enums import FSMState
from core.fsm.proto import FSMStateProto
from core.fsm.protobuf_handler import ProtoFSMHandler


def test_proto_transitions() -> None:
    handler = ProtoFSMHandler()
    proto = FSMStateProto(current_state=FSMState.IDLE)

    proto = asyncio.run(handler.handle(proto))
    assert proto.current_state == FSMState.ACTIVE

    proto = asyncio.run(handler.handle(proto))
    assert proto.current_state == FSMState.SHUTDOWN
