from __future__ import annotations

from qiki.services.operator_console.main_orion import OrionApp


def test_build_qiki_chat_request_minimal() -> None:
    app = OrionApp()
    req = app._build_qiki_chat_request("ping")

    assert req.version == 1
    assert str(req.request_id)
    assert req.input.text == "ping"
    assert req.input.lang_hint in {"auto", "ru", "en"}
    assert isinstance(req.ts_epoch_ms, int)
    assert req.ts_epoch_ms > 0
    assert req.ui_context.selection.kind in {"event", "incident", "track", "snapshot", "none"}
