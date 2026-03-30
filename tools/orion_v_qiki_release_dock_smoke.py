from __future__ import annotations

import asyncio
import time
from uuid import uuid4

from textual.widgets import Static

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
            "request_id": str(uuid4()),
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
                "allowed_when": {
                    "en": "Use the explicit ORION confirmation step to send the undock command.",
                    "ru": "Используйте явный шаг подтверждения в ORION, чтобы отправить команду отстыковки.",
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
                "telemetry_confirmation": {
                    "en": (
                        "No control-bus command has been sent yet; "
                        "the craft remains docked until ORION confirms execution."
                    ),
                    "ru": (
                        "Команда на control bus ещё не отправлялась; "
                        "аппарат остаётся пристыкованным, пока ORION не подтвердит исполнение."
                    ),
                },
            },
            "proposals": [
                {
                    "proposal_id": "qiki-release-dock-live-proof",
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
    async with app.run_test(size=(140, 44)) as pilot:
        await _wait_until(
            lambda: app._nats_client.connection_state == "connected",
            timeout_s=10.0,
            step_s=0.1,
            label="NATS connection",
        )
        await _wait_until(
            lambda: isinstance(app._snapshot.get("docking"), dict),
            timeout_s=10.0,
            step_s=0.1,
            label="initial docking telemetry",
        )

        await app._publish_sim_command("sim.dock.engage", {"port": "A"})
        assert await app._wait_for_ack("sim.dock.engage", 3.0), "no ACK for sim.dock.engage"
        await _wait_until(
            lambda: (
                isinstance(app._snapshot.get("docking"), dict)
                and str((app._snapshot.get("docking") or {}).get("state") or "").strip().lower() == "docked"
                and bool((app._snapshot.get("docking") or {}).get("connected")) is True
            ),
            timeout_s=5.0,
            step_s=0.1,
            label="docked telemetry after engage",
        )
        await pilot.pause()

        docking = dict(app._snapshot.get("docking") or {})
        port = str(docking.get("port") or "A").strip() or "A"

        await app._on_qiki_response(_release_dock_payload(port))
        await pilot.pause()

        help_text = _widget_text(app.query_one("#orionv-help", Static))
        assert "q confirm" in help_text, help_text
        assert app._qiki_pending_action is not None, "QIKI pending action was not exposed"

        await app._execute_qiki_pending_action()
        await _wait_until(
            lambda: (
                app._qiki_last_response is not None
                and app._qiki_last_response.consequence is not None
                and app._qiki_last_response.consequence.status == "confirmed"
            ),
            timeout_s=5.0,
            step_s=0.1,
            label="confirmed consequence",
        )
        await _wait_until(
            lambda: (
                isinstance(app._snapshot.get("docking"), dict)
                and str((app._snapshot.get("docking") or {}).get("state") or "").strip().lower() == "undocked"
                and bool((app._snapshot.get("docking") or {}).get("connected")) is False
            ),
            timeout_s=5.0,
            step_s=0.1,
            label="undocked telemetry after release",
        )
        await pilot.pause()

        final_docking = dict(app._snapshot.get("docking") or {})
        consequence = app._qiki_last_response.consequence if app._qiki_last_response is not None else None
        assert consequence is not None
        print("OK: orion_v_qiki_release_dock_smoke")
        print(f"FINAL_DOCKING={final_docking}")
        print(f"CONSEQUENCE={consequence.status}")
        if consequence.telemetry_confirmation is not None:
            print(f"CONFIRMATION_RU={consequence.telemetry_confirmation.ru}")


if __name__ == "__main__":
    asyncio.run(_main())
