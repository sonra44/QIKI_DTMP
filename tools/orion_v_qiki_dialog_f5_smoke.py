"""M1 live-proof: экран F5 QIKI/ДИАЛОГ монтируется, показывается и read-only.

Доказывает:
1) f5 переключает видимый уровень на orionv-qiki-dialog;
2) пустое состояние несёт каноничный текст границы (кандидат ≠ чат-бот);
3) реплика оператора (intent-лог) и голос QIKI попадают в ленту диалога;
4) переключение на F5 НЕ порождает pending_action (read-only).
"""

from __future__ import annotations

import asyncio
import time
from uuid import UUID

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.screens.qiki_dialog import OrionVQikiDialogScreen


async def _wait_until(predicate, *, timeout_s: float, step_s: float, label: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(step_s)
    raise AssertionError(f"timeout while waiting for {label}")


def _qiki_reply_payload(request_id: str) -> dict[str, object]:
    return {
        "data": {
            "version": 1,
            "request_id": request_id,
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Status", "ru": "Статус"},
                "body": {"en": "stable", "ru": "состояние стабильное, стыковка активна"},
            },
            "legality": None,
            "trust_signals": [],
            "consequence": None,
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }


async def _main() -> None:
    app = OrionVApp()
    async with app.run_test(size=(160, 48)) as pilot:
        await _wait_until(
            lambda: app._nats_client.connection_state == "connected",
            timeout_s=10.0,
            step_s=0.1,
            label="NATS connection",
        )
        screen = app.query_one("#orionv-qiki-dialog", OrionVQikiDialogScreen)

        # 1) переключение на F5
        await pilot.press("f5")
        await pilot.pause()
        assert app._current_level == "f5", f"F5 не активен: {app._current_level}"
        assert not screen.has_class("hidden"), "F5 скрыт после переключения"
        assert "QIKI — не внешний чат-бот" in screen.rendered_text()
        print("[smoke] F5 виден, пустое состояние с границей candidate≠бот OK")

        # 2) диалог: реплика оператора + ответ QIKI
        req_id = str(UUID(int=4242))
        app._qiki_dialog_operator_ledger.append(("06:00:12Z", "доложи состояние"))
        app._qiki_pending[req_id] = (time.time(), "доложи состояние")
        await app._on_qiki_response(_qiki_reply_payload(req_id))
        await pilot.pause()
        text = screen.rendered_text()
        assert "ОПЕРАТОР ▸ 06:00:12Z | доложи состояние" in text, text
        assert "состояние стабильное" in text, text
        print("[smoke] лента диалога: оператор + QIKI в кадре OK")

        # 3) read-only: переключение/ответ не создали pending_action
        assert app._qiki_pending_action is None, "F5-путь создал pending_action (не read-only!)"
        print("[smoke] read-only OK: pending_action не создан")

    print("[smoke] M1 PASS: F5 монтируется, лента живая, execute-путь не добавлен")


if __name__ == "__main__":
    asyncio.run(_main())
