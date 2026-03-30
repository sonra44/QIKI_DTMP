import json

from qiki.services.operator_console.clients.nats_client import NATSClient


class _MsgStub:
    def __init__(self, *, data: bytes, subject: str) -> None:
        self.data = data
        self.subject = subject


def test_decode_control_response_malformed_payload_increments_counter() -> None:
    client = NATSClient(url="nats://test:4222")
    msg = _MsgStub(data=b"\xff\x00not-json", subject="qiki.responses.control")

    decoded = client._decode_response_message(msg=msg, kind="control_responses")

    assert decoded is None
    assert client.decode_errors_control_responses == 1
    assert client.decode_errors_qiki_responses == 0


def test_decode_qiki_response_malformed_payload_increments_counter() -> None:
    client = NATSClient(url="nats://test:4222")
    msg = _MsgStub(data=b"{broken_json", subject="qiki.responses.qiki")

    decoded = client._decode_response_message(msg=msg, kind="qiki_responses")

    assert decoded is None
    assert client.decode_errors_qiki_responses == 1
    assert client.decode_errors_control_responses == 0


def test_decode_response_message_success_path() -> None:
    client = NATSClient(url="nats://test:4222")
    msg = _MsgStub(data=json.dumps({"ok": True}).encode("utf-8"), subject="qiki.responses.control")

    decoded = client._decode_response_message(msg=msg, kind="control_responses")

    assert decoded is not None
    assert decoded["stream"] == "CONTROL_RESPONSES"
    assert decoded["subject"] == "qiki.responses.control"
    assert decoded["data"] == {"ok": True}
    assert client.decode_errors_control_responses == 0
