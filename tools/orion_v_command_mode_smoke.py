from __future__ import annotations

import asyncio

from textual.widgets import Button, Input, Static

from qiki.services.operator_console.orion_v.app import OrionVApp


async def _main() -> None:
    app = OrionVApp()
    async with app.run_test(size=(160, 44)) as pilot:
        await pilot.pause()

        command = app.query_one("#orionv-command", Input)
        shell = app.query_one("#orionv-command-shell", Static)
        open_button = app.query_one("#orionv-command-open", Button)

        assert command.has_class("hidden") is True
        assert shell.has_class("hidden") is False
        assert open_button.has_class("hidden") is False

        app.action_open_command_mode()
        await pilot.pause()

        assert command.has_class("hidden") is False
        assert shell.has_class("hidden") is True
        assert open_button.has_class("hidden") is True

        app.action_close_command_mode()
        await pilot.pause()

        assert command.has_class("hidden") is True
        assert shell.has_class("hidden") is False
        assert open_button.has_class("hidden") is False

        print("OK: orion_v_command_mode_smoke")
        print("DEFAULT_MODE=no_persistent_input")
        print("COMMAND_MODE=open_on_demand")
        print(f"BUTTON_LABEL={open_button.label.plain}")


if __name__ == "__main__":
    asyncio.run(_main())
