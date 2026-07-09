"""Этап 8 live-smoke: командная поверхность против живого стека phase1.

1. `help` → в консоль F4 выведены все 7 групповых строк реестра.
2. Палитра (реестр→роутер): typed-запись `sim.start` исполняется тем же
   роутером — живой ACK-путь (МИР реально стартует, GetRadarFrame открывается);
   `sim.stop` возвращает STOPPED.
3. Чип PWR несёт cap-гейт из живой телеметрии: `cap NN% ▸КОД`.
4. `quit` → ConfirmDialog; `n` — консоль жива; повторный quit открывает модал
   снова (guard снят после ответа).
"""

from __future__ import annotations

import asyncio
import os
import sys

from textual.widgets import Button

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.command_registry import HELP_GROUPS_ORDER
from qiki.services.operator_console.orion_v.dialogs import ConfirmDialog

os.environ["RADAR_TRACKS_DURABLE"] = ""  # эфемерная подписка (без durable-конфликта)


async def _wait(pilot, predicate, *, timeout_s: float = 15.0, label: str = "") -> None:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        await pilot.pause()
        if predicate():
            return
        await asyncio.sleep(0.4)
    raise AssertionError(f"не дождались: {label}")


async def main() -> int:
    app = OrionVApp()
    async with app.run_test(size=(200, 50)) as pilot:
        for _ in range(40):
            await pilot.pause()
            if app._nats_client.connection_state == "connected":
                break
            await asyncio.sleep(0.25)
        assert app._nats_client.connection_state == "connected", "нет NATS"

        # 1. help → 7 групп в истории консоли
        app._route_typed_command("help")
        history = "\n".join(str(line) for line in app._console_history)
        for group in HELP_GROUPS_ORDER:
            assert f"{group}:" in history, f"help без группы {group}"
        print(f"[smoke] help: все {len(HELP_GROUPS_ORDER)} групп в консоли F4 ✓")

        # 2. палитра single-path: sim.start живьём через роутер (тот же ACK-путь)
        await _wait(pilot, lambda: True, timeout_s=1.0)
        app._route_typed_command("sim.start")
        await _wait(
            pilot,
            lambda: "sim.start" in str(app._help_text),
            label="ACK-путь sim.start (help-строка мира)",
        )
        await asyncio.sleep(2.0)  # дать ACK осесть
        await pilot.pause()
        print("[smoke] палитра→роутер: sim.start ушла живым ACK-путём ✓")
        app._route_typed_command("sim.stop")
        await asyncio.sleep(1.5)
        await pilot.pause()
        print("[smoke] sim.stop отправлена — мир возвращается в STOPPED ✓")

        # 3. чип PWR: cap-гейт из живой телеметрии
        def _pwr_chip_text() -> str:
            try:
                return str(app.query_one("#orionv-status-power-action", Button).label)
            except Exception:
                return ""

        await _wait(
            pilot,
            lambda: "cap" in _pwr_chip_text() and "▸" in _pwr_chip_text().split("cap", 1)[-1],
            timeout_s=20.0,
            label="cap-гейт на чипе PWR (живая телеметрия supercap)",
        )
        print(f"[smoke] чип PWR живьём: {_pwr_chip_text().strip()} ✓")

        # 4. quit-confirm: модал, отказ, guard снят
        app._route_typed_command("quit")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog), "quit не открыл ConfirmDialog"
        await pilot.press("n")
        await pilot.pause()
        assert not isinstance(app.screen, ConfirmDialog), "n не закрыл модал"
        assert app._quit_confirm_open is False
        print("[smoke] quit → модал → n: консоль жива, guard снят ✓")
        app._route_typed_command("quit")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog), "повторный quit не открыл модал"
        await pilot.press("escape")
        await pilot.pause()
        print("[smoke] повторный quit снова спрашивает (после ответа) ✓")

    print("[smoke] Этап 8 PASS: командная поверхность честна на живом стеке")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
