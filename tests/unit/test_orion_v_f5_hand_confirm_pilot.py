"""Срез 1 (F5-рука) — ЖИВОЙ app-pilot: кнопка [✓ Выполнить] на F5.

Гоняет настоящий OrionVApp в Textual-pilot: реальный путь _on_qiki_response
создаёт кандидата → на F5 в рельсе появляется [✓ Выполнить] → клик уходит в
канонический _confirm_qiki_pending_action. Без кандидата (LLM-состояние, CaMeL)
кнопки нет.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from textual.widgets import Button

from qiki.services.operator_console.orion_v.app import OrionVApp


def _confirmable_candidate_payload() -> dict:
    """Реальный ответ QIKI с proposed_action → app._qiki_pending_action (policy-кандидат)."""
    return {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=42)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Release ready", "ru": "Отстыковка готова"},
                "body": {
                    "en": "QIKI can prepare a real undock command, ORION must confirm it.",
                    "ru": "QIKI может подготовить команду отстыковки, ORION должен подтвердить.",
                },
            },
            "legality": {
                "status": "allowed",
                "domain": "physics",
                "reason_code": "DOCK_RELEASE_READY",
                "reason": {"en": "docked on port A", "ru": "пристыкован на порту A"},
                "allowed_when": {"en": "explicit confirm", "ru": "явное подтверждение"},
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "prepared, waiting confirm", "ru": "подготовлено, ждёт подтверждения"},
            },
            "proposals": [
                {
                    "proposal_id": "qiki-release-dock",
                    "title": {"en": "Confirm undock", "ru": "Подтвердить отстыковку"},
                    "justification": {"en": "telemetry ok", "ru": "телеметрия ок"},
                    "confidence": 1.0,
                    "priority": 90,
                    "suggested_questions": [],
                    "proposed_actions": [
                        {
                            "kind": "NATS_COMMAND",
                            "subject": "qiki.commands.control",
                            "name": "sim.dock.release",
                            "parameters": {},
                            "dry_run": False,
                        }
                    ],
                }
            ],
            "warnings": [],
            "error": None,
        }
    }


@pytest.mark.asyncio
async def test_f5_hand_confirm_button_live_pilot(monkeypatch) -> None:
    pytest.importorskip("textual")

    async def _no_nats(self) -> None:  # unit env без брокера: глушим mount-time connect/hydrate
        return None

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", _no_nats)
    monkeypatch.setattr(OrionVApp, "_hydrate_last_observation_objective_from_jetstream", _no_nats)

    app = OrionVApp()
    async with app.run_test(size=(220, 44)) as pilot:
        await pilot.pause()

        # На F5, кандидата ещё нет (LLM-состояние / CaMeL) → кнопок подтверждения нет.
        app._current_level = "f5"
        app._refresh_ui()
        await pilot.pause()
        confirm = app.query_one("#orionv-action-qiki_confirm", Button)
        cancel = app.query_one("#orionv-action-qiki_cancel", Button)
        assert confirm.display is False
        assert cancel.display is False

        # Реальный путь: ответ QIKI с proposed_action → _qiki_pending_action (policy-кандидат).
        payload = _confirmable_candidate_payload()
        app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ на свой запрос
        await app._on_qiki_response(payload)
        app._refresh_ui()
        await pilot.pause()

        assert app._qiki_pending_action is not None
        assert confirm.display is True  # рука появилась ПРЯМО на F5
        assert cancel.display is True
        assert confirm.disabled is False

        # Клик по [✓ Выполнить] уходит в КАНОНИЧЕСКИЙ _confirm (не второй execute-путь).
        routed: list[str] = []
        app._confirm_qiki_pending_action = lambda: routed.append("confirm")  # type: ignore[method-assign]
        await pilot.click("#orionv-action-qiki_confirm")
        await pilot.pause()
        assert routed == ["confirm"]
