from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.screens.deep_dive import OrionVDeepDiveScreen
from qiki.services.operator_console.orion_v.screens.systems import OrionVSystemsScreen


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


async def _main() -> None:
    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    OrionVApp._connect_and_subscribe = no_nats  # type: ignore[method-assign]

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()

        await app._on_event(
            {
                "subject": "qiki.events.v1.fsm",
                "data": {
                    "subsystem": "FSM",
                    "event_type": "FSM_TRANSITION",
                    "to_state": "SAFE_MODE",
                    "trigger_event": "SAFE_MODE_ENTER_SMOKE",
                },
            }
        )
        await pilot.pause()

        systems = app.query_one("#orionv-systems", OrionVSystemsScreen)
        deep = app.query_one("#orionv-deep", OrionVDeepDiveScreen)
        systems_text = _widget_text(systems)
        deep_text = _widget_text(deep)

        assert "Безопасность (Q-Core authority):" in systems_text
        assert "SAFE MODE: ВКЛЮЧЕН" in systems_text
        assert "SAFE_MODE_ENTER_SMOKE" in systems_text
        assert "Безопасность (Q-Core authority):" in deep_text
        assert "SAFE MODE: ВКЛЮЧЕН" in deep_text
        assert "SAFE_MODE_ENTER_SMOKE" in deep_text

        await app._on_event(
            {
                "subject": "qiki.events.v1.safe_mode",
                "data": {
                    "subsystem": "SAFE_MODE",
                    "event_type": "SAFE_MODE",
                    "action": "exit",
                    "reason": "SAFE_MODE_EXIT_SMOKE",
                },
            }
        )
        await pilot.pause()

        systems_text = _widget_text(systems)
        deep_text = _widget_text(deep)
        assert "SAFE MODE: выключен" in systems_text
        assert "SAFE MODE: выключен" in deep_text
        assert "SAFE_MODE_EXIT_SMOKE" in systems_text
        assert "SAFE_MODE_EXIT_SMOKE" in deep_text

    print("OK: orion_v_safe_mode_smoke")


if __name__ == "__main__":
    asyncio.run(_main())
