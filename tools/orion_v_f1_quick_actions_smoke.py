from __future__ import annotations

import asyncio
import time
from uuid import UUID

from textual.widgets import Button, Static

from qiki.services.operator_console.orion_v.app import OrionVApp


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


def _release_dock_payload(port: str) -> dict[str, object]:
    return {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=999)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Release ready", "ru": "Отстыковка готова"},
                "body": {
                    "en": "QIKI can prepare a real undock command, but ORION must confirm it explicitly.",
                    "ru": (
                        "QIKI может подготовить реальную команду отстыковки, "
                        "но ORION должен подтвердить её отдельно."
                    ),
                },
            },
            "legality": {
                "status": "allowed",
                "domain": "physics",
                "reason_code": "DOCK_RELEASE_READY",
                "reason": {
                    "en": f"Docking telemetry confirms an attached state on port {port}.",
                    "ru": f"Телеметрия стыковки подтверждает пристыкованное состояние на порту {port}.",
                },
            },
            "trust_signals": [
                {
                    "label": {"en": "Docking telemetry", "ru": "Телеметрия стыковки"},
                    "state": "healthy",
                    "source": "sensor",
                    "confidence": 1.0,
                    "reason_code": "DOCK_RELEASE_READY",
                    "reason": {
                        "en": f"Docking telemetry confirms an attached state on port {port}.",
                        "ru": f"Телеметрия стыковки подтверждает пристыкованное состояние на порту {port}.",
                    },
                }
            ],
            "consequence": {
                "status": "pending",
                "summary": {
                    "en": "The undock command is prepared and waiting for explicit operator confirmation.",
                    "ru": "Команда отстыковки подготовлена и ждёт явного подтверждения оператора.",
                },
            },
            "proposals": [
                {
                    "proposal_id": "qiki-release-dock-quick-actions-proof",
                    "title": {"en": "Confirm undock", "ru": "Подтвердить отстыковку"},
                    "justification": {
                        "en": "Telemetry confirms a docked state and a valid release path.",
                        "ru": "Телеметрия подтверждает пристыкованное состояние и валидный путь отстыковки.",
                    },
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
            lambda: isinstance(app._snapshot.get("power"), dict),
            timeout_s=10.0,
            step_s=0.1,
            label="power telemetry",
        )
        await _wait_until(
            lambda: isinstance(app._snapshot.get("comms"), dict),
            timeout_s=10.0,
            step_s=0.1,
            label="comms telemetry",
        )
        await _wait_until(
            lambda: isinstance(app._snapshot.get("docking"), dict),
            timeout_s=10.0,
            step_s=0.1,
            label="docking telemetry",
        )
        await pilot.pause()

        intervention = _widget_text(app.query_one("#orionv-cockpit-intervention", Static))
        assert "Быстрые переходы/Quick actions" in intervention, intervention

        power_button = app.query_one("#orionv-cockpit-jump-power", Button)
        docking_button = app.query_one("#orionv-cockpit-jump-docking", Button)
        comms_button = app.query_one("#orionv-cockpit-jump-comms", Button)
        qiki_confirm = app.query_one("#orionv-cockpit-qiki-confirm", Button)
        qiki_cancel = app.query_one("#orionv-cockpit-qiki-cancel", Button)

        assert "Power Margin" in str(power_button.label)
        assert "Target/Docking" in str(docking_button.label)
        assert "Comms Link" in str(comms_button.label)
        assert str(qiki_confirm.label) == "QIKI: нет действия/No action"
        assert str(qiki_cancel.label) == "QIKI: нет действия/No action"
        assert qiki_confirm.disabled is True
        assert qiki_cancel.disabled is True

        await pilot.click("#orionv-cockpit-jump-docking")
        await pilot.pause()
        assert app._current_level == "f2"
        assert app._selected_system_module_slug == "docking"

        app.action_show_level("f1")
        await pilot.pause()

        docking = dict(app._snapshot.get("docking") or {})
        port = str(docking.get("port") or "A").strip() or "A"
        await app._on_qiki_response(_release_dock_payload(port))
        await pilot.pause()

        qiki_confirm = app.query_one("#orionv-cockpit-qiki-confirm", Button)
        qiki_cancel = app.query_one("#orionv-cockpit-qiki-cancel", Button)
        intervention = _widget_text(app.query_one("#orionv-cockpit-intervention", Static))

        assert str(qiki_confirm.label) == "QIKI подтвердить/Confirm"
        assert str(qiki_cancel.label) == "QIKI отменить/Cancel"
        assert qiki_confirm.disabled is False
        assert qiki_cancel.disabled is False
        assert "Подготовлено/Prepared: Подтвердить отстыковку" in intervention, intervention

        await pilot.click("#orionv-cockpit-qiki-cancel")
        await pilot.pause()

        assert app._qiki_pending_action is None
        assert app._qiki_last_response is not None
        assert app._qiki_last_response.consequence is not None
        assert app._qiki_last_response.consequence.status == "not_sent"

        print("OK: orion_v_f1_quick_actions_smoke")
        print(f"POWER_BUTTON={power_button.label}")
        print(f"DOCKING_BUTTON={docking_button.label}")
        print(f"COMMS_BUTTON={comms_button.label}")
        print(f"QIKI_CONFIRM_READY={qiki_confirm.label}")
        print("INTERVENTION_HAS_PREPARED=1")
        print(f"FINAL_LEVEL={app._current_level}")
        print(f"FINAL_SELECTED_MODULE={app._selected_system_module_slug}")
        print(f"FINAL_QIKI_STATUS={app._qiki_last_response.consequence.status}")


if __name__ == "__main__":
    asyncio.run(_main())
