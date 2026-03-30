import logging

import pytest


@pytest.mark.asyncio
async def test_handle_qiki_response_broad_exception_logs_and_counts(monkeypatch, caplog) -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console import main_orion as mo

    async def _run() -> None:
        app = mo.OrionApp()

        def _boom(cls, payload):  # noqa: ANN001
            raise RuntimeError("decode boom")

        monkeypatch.setattr(mo.QikiChatResponseV1, "model_validate", classmethod(_boom))
        mo.ORION_CRITICAL_EXCEPTION_COUNT = 0

        with caplog.at_level(logging.ERROR, logger="orion"):
            await app.handle_qiki_response({"data": {"request_id": "req-1", "kind": "response"}})

        assert mo.ORION_CRITICAL_EXCEPTION_COUNT == 1
        assert any("component=qiki action=decode_response" in message for message in caplog.messages)

    await _run()


def test_safe_json_loads_logs_and_counts(caplog) -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console import main_orion as mo

    mo.ORION_CRITICAL_EXCEPTION_COUNT = 0
    with caplog.at_level(logging.ERROR, logger="orion"):
        result = mo._safe_json_loads(b"{broken_json", component="control", action="decode", subject="qiki.responses")

    assert result is None
    assert mo.ORION_CRITICAL_EXCEPTION_COUNT == 1
    assert any("component=control action=decode" in message for message in caplog.messages)
