from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.widgets.action_bar import OrionVActionBar
from qiki.services.operator_console.orion_v.widgets.header import OrionVHeader
from qiki.services.operator_console.orion_v.widgets.status_bars import OrionVStatusBars
from textual.widgets import Button, Input, Static


async def main() -> None:
    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()

        header = app.query_one("#orionv-header", OrionVHeader)
        safety_strip = app.query_one("#orionv-safety-strip")
        actions = app.query_one("#orionv-actions", OrionVActionBar)
        bars = app.query_one("#orionv-bars", OrionVStatusBars)
        overlay = app.query_one("#orionv-overlay")
        command = app.query_one("#orionv-command", Input)
        command_strip = app.query_one("#orionv-command-strip")
        cockpit_actions = app.query_one("#orionv-cockpit-actions")

        print("OK: orion_v_top_zone_smoke")
        print(f"HEADER_TITLE={header.border_title}")
        print(f"HEADER_SUBTITLE={header.border_subtitle}")
        print(f"SAFETY_TITLE={safety_strip.border_title}")
        print(f"ACTIONS_TITLE={actions.border_title}")
        print(f"BARS_TITLE={bars.border_title or 'embedded'}")
        print(f"OVERLAY_TITLE={overlay.border_title or 'embedded'}")
        print(f"COMMAND_STRIP_ID={command_strip.id}")
        print(f"COMMAND_TITLE={command.border_title}")
        print(f"COCKPIT_ACTIONS_TITLE={cockpit_actions.border_title}")
        print(f"ACTION_F1={app.query_one('#orionv-action-f1', Button).label}")
        print(f"ACTION_F6={app.query_one('#orionv-action-f6', Button).label}")
        print(f"STATUS_TITLE={app.query_one('#orionv-status-title', Static).render().plain}")
        print(f"QIKI_CONFIRM={app.query_one('#orionv-cockpit-qiki-confirm', Button).label}")


if __name__ == '__main__':
    asyncio.run(main())
