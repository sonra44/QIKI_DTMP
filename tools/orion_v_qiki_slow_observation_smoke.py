from __future__ import annotations

import asyncio
import time
from uuid import UUID

from textual.widgets import Static

from qiki.services.operator_console.orion_v.app import OrionVApp


def _slow_observation_payload() -> dict[str, object]:
    return {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=54321)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Slow observation ready", "ru": "Медленное наблюдение готово"},
                "body": {
                    "en": "QIKI prepared a cautious two-step observation procedure.",
                    "ru": "QIKI подготовила осторожную двухшаговую процедуру наблюдения.",
                },
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SLOW_OBSERVATION_PROCEDURE_READY",
                "reason": {
                    "en": "Existing simulation control path supports reduced-speed restart.",
                    "ru": "Существующий контур управления симуляцией поддерживает перезапуск на пониженной скорости.",
                },
                "allowed_when": {
                    "en": "Confirm the prepared ORION procedure to resume at x0.25.",
                    "ru": "Подтвердите подготовленную процедуру ORION, чтобы вернуть выполнение на скорости x0.25.",
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
                    "proposal_id": "qiki-slow-observation-live-proof",
                    "title": {"en": "Run slow observation", "ru": "Запустить медленное наблюдение"},
                    "justification": {
                        "en": "Pause and resume via existing procedure engine at x0.25.",
                        "ru": "Пауза и возврат через существующий движок процедур на скорости x0.25.",
                    },
                    "confidence": 1.0,
                    "priority": 82,
                    "suggested_questions": [],
                    "proposed_actions": [
                        {
                            "kind": "ORION_PROCEDURE",
                            "subject": "orionv.procedure",
                            "name": "safe_pause_slow_resume",
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

        await app._on_qiki_response(_slow_observation_payload())
        await pilot.pause()

        assert app._qiki_pending_action is not None
        assert app._qiki_pending_action["action_kind"] == "ORION_PROCEDURE"
        assert app._qiki_pending_action["name"] == "safe_pause_slow_resume"
        plan_lines = app._build_qiki_plan_preview_lines()
        assert len(plan_lines) == 2
        assert plan_lines[0].startswith("1. sim.pause")
        assert "speed=0.25" in plan_lines[1]

        body = _widget_text(app.query_one("#orionv-cockpit-body", Static))
        assert "План/Plan:" in body
        assert "sim.start speed=0.25 -> ack sim.start" in body

        await app._execute_qiki_pending_action()
        await _wait_until(
            lambda: (
                app._qiki_last_response is not None
                and app._qiki_last_response.consequence is not None
                and app._qiki_last_response.consequence.status == "confirmed"
            ),
            timeout_s=8.0,
            step_s=0.1,
            label="confirmed slow procedure consequence",
        )
        await _wait_until(
            lambda: (
                isinstance(app._telemetry.get("sim_state"), dict)
                and str((app._telemetry.get("sim_state") or {}).get("fsm_state") or "").strip().upper() == "RUNNING"
                and bool((app._telemetry.get("sim_state") or {}).get("paused")) is False
                and abs(float((app._telemetry.get("sim_state") or {}).get("speed") or 0.0) - 0.25) < 1e-6
            ),
            timeout_s=5.0,
            step_s=0.1,
            label="sim_state slow running after procedure",
        )
        await pilot.pause()

        sim_state = dict(app._telemetry.get("sim_state") or {})
        assert app._procedure_engine.state.status == "ok"

        print("OK: orion_v_qiki_slow_observation_smoke")
        print(f"PLAN_LINES={plan_lines}")
        print(f"PROCEDURE_STATUS={app._procedure_engine.state.status}")
        print(f"SIM_STATE={sim_state}")
        print(f"FINAL_QIKI_STATUS={app._qiki_last_response.consequence.status}")


if __name__ == "__main__":
    asyncio.run(_main())
