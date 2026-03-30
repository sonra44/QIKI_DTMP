from __future__ import annotations

import asyncio
import time
from uuid import UUID

from textual.widgets import Button, Static

from qiki.services.operator_console.orion_v.app import OrionVApp


def _safe_observation_payload() -> dict[str, object]:
    return {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=223344)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Safe observation ready", "ru": "Безопасное наблюдение готово"},
                "body": {
                    "en": "QIKI prepared a short two-step observation procedure.",
                    "ru": "QIKI подготовила короткую двухшаговую процедуру наблюдения.",
                },
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SAFE_OBSERVATION_PROCEDURE_READY",
                "reason": {
                    "en": "Existing simulation control path is ready.",
                    "ru": "Существующий контур управления симуляцией готов.",
                },
                "allowed_when": {
                    "en": "Confirm the prepared ORION procedure.",
                    "ru": "Подтвердите подготовленную процедуру ORION.",
                },
            },
            "trust_signals": [
                {
                    "label": {"en": "Simulation control state", "ru": "Состояние управления симуляцией"},
                    "state": "healthy",
                    "source": "derived",
                    "confidence": 1.0,
                    "reason_code": "SIM_CONTROL_READY",
                    "reason": {
                        "en": "Simulation control is ready.",
                        "ru": "Управление симуляцией готово.",
                    },
                }
            ],
            "consequence": {
                "status": "pending",
                "summary": {
                    "en": "Procedure prepared.",
                    "ru": "Процедура подготовлена.",
                },
            },
            "proposals": [
                {
                    "proposal_id": "qiki-safe-observation-surface-proof",
                    "title": {"en": "Run safe observation", "ru": "Запустить безопасное наблюдение"},
                    "justification": {
                        "en": "Pause and resume via existing procedure engine.",
                        "ru": "Пауза и возврат к выполнению через существующий движок процедур.",
                    },
                    "confidence": 1.0,
                    "priority": 85,
                    "suggested_questions": [],
                    "proposed_actions": [
                        {
                            "kind": "ORION_PROCEDURE",
                            "subject": "orionv.procedure",
                            "name": "safe_pause_resume",
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


def _widget_text(widget: object) -> str:
    renderable = getattr(widget, "renderable", None)
    if hasattr(renderable, "plain"):
        return str(getattr(renderable, "plain"))
    if renderable is not None:
        return str(renderable)
    content = getattr(widget, "content", None)
    if hasattr(content, "plain"):
        return str(getattr(content, "plain"))
    if content is not None:
        return str(content)
    return str(widget)


async def _wait_until(predicate, *, timeout_s: float, step_s: float, label: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(step_s)
    raise AssertionError(f"timeout while waiting for {label}")


async def _main() -> None:
    app = OrionVApp()
    async with app.run_test(size=(160, 48)) as pilot:
        await _wait_until(
            lambda: app._nats_client.connection_state == "connected",
            timeout_s=10.0,
            step_s=0.1,
            label="NATS connection",
        )
        await _wait_until(
            lambda: isinstance(app._telemetry.get("sim_state"), dict),
            timeout_s=10.0,
            step_s=0.1,
            label="sim_state telemetry",
        )
        await pilot.pause()

        await app._on_qiki_response(_safe_observation_payload())
        await pilot.pause()

        body = _widget_text(app.query_one("#orionv-cockpit-body", Static))
        procedure_button = app.query_one("#orionv-cockpit-jump-procedures", Button)
        confirm_button = app.query_one("#orionv-cockpit-qiki-confirm", Button)

        assert "Процедура:" in body, body
        assert "Подготовлено/Prepared: Запустить безопасное наблюдение" in body, body
        assert "План/Plan:" in body, body
        assert "Время/Time: sim_state=" in body, body
        assert "Журнал/Journal: click Процедуры/Procedures -> F6 for procedure audit trail." in body, body
        assert "Процедуры/Procedures" in str(procedure_button.label)
        assert "QIKI подтвердить/Confirm" == str(confirm_button.label)
        assert confirm_button.disabled is False

        await app._execute_qiki_pending_action()
        await _wait_until(
            lambda: (
                app._qiki_last_response is not None
                and app._qiki_last_response.consequence is not None
                and app._qiki_last_response.consequence.status == "confirmed"
            ),
            timeout_s=8.0,
            step_s=0.1,
            label="confirmed procedure consequence",
        )
        await pilot.pause()

        body = _widget_text(app.query_one("#orionv-cockpit-body", Static))
        assert "Исполнение/Execution:" in body, body
        assert "Время/Time: sim_state=RUNNING" in body, body

        await pilot.click("#orionv-cockpit-jump-procedures")
        await pilot.pause()

        assert app._current_level == "f6"
        assert app._audit_filter_type == "procedures"

        summary = _widget_text(app.query_one("#orionv-audit", Static))
        print("OK: orion_v_qiki_procedure_surface_smoke")
        print(f"PROCEDURE_BUTTON={procedure_button.label}")
        print(f"CONFIRM_BUTTON={confirm_button.label}")
        print(f"FINAL_LEVEL={app._current_level}")
        print(f"AUDIT_FILTER={app._audit_filter_type}")
        print(f"AUDIT_SUMMARY={summary}")


if __name__ == "__main__":
    asyncio.run(_main())
