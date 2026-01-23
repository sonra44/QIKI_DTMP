from __future__ import annotations

import pytest
import time
from uuid import uuid4

from qiki.services.operator_console.main_orion import OrionApp


@pytest.mark.asyncio
async def test_handle_qiki_response_invalid_payload_does_not_crash() -> None:
    app = OrionApp()
    logs: list[str] = []

    app._console_log = lambda msg, level="info": logs.append(f"{level}:{msg}")  # type: ignore[method-assign]
    app._calm_log = lambda msg: logs.append(f"calm:{msg}")  # type: ignore[method-assign]

    req_id = uuid4()
    await app.handle_qiki_response({"data": {"request_id": str(req_id), "version": 1}})
    assert any("QIKI: invalid" in line for line in logs)


@pytest.mark.asyncio
async def test_handle_qiki_response_error_logs_and_clears_pending() -> None:
    app = OrionApp()
    logs: list[str] = []

    app._console_log = lambda msg, level="info": logs.append(f"{level}:{msg}")  # type: ignore[method-assign]
    app._calm_log = lambda msg: logs.append(f"calm:{msg}")  # type: ignore[method-assign]

    req_id = uuid4()
    app._qiki_pending[str(req_id)] = (time.time(), "ping")

    payload = {
        "version": 1,
        "request_id": str(req_id),
        "ok": False,
        "mode": "FACTORY",
        "reply": None,
        "proposals": [],
        "warnings": [{"en": "INVALID REQUEST", "ru": "НЕВЕРНЫЙ ЗАПРОС"}],
        "error": {
            "code": "INVALID_REQUEST",
            "message": {"en": "Bad request", "ru": "Плохой запрос"},
        },
    }

    await app.handle_qiki_response({"data": payload})
    assert str(req_id) not in app._qiki_pending
    assert any("INVALID_REQUEST" in line for line in logs)


import pytest
