"""Этап 7 live-smoke: строка идентичности QIKI на F1 против живого стека.

Живой NATS/телеметрия: статус-блок F1 начинается с «QIKI-<серийник>»
(серийник — первые 6 hex digest'а hardware_profile_hash реальной
телеметрии), несёт канонную идентичность «додекаэдр · 12 граней» и счёт
модулей; evidence-мета — в tooltip рамки. Плюс постоянная honesty-строка
панели QIKI (Z7). Лента QIKI ▸ требует реплики (LLM-контур) — она покрыта
юнитами test_orion_qiki_voice и живым F5-контуром, НЕ этим смоком
(аудит 0049: докстринг раньше заявлял её проверку — overclaim убран).
"""

from __future__ import annotations

import asyncio
import os
import re
import sys

from textual.widgets import Static

from qiki.services.operator_console.orion_v.app import OrionVApp

os.environ["RADAR_TRACKS_DURABLE"] = ""  # эфемерная подписка (без durable-конфликта)


async def _status_text(app: OrionVApp) -> str:
    return app.query_one("#orionv-mfd-status", Static).render().plain


async def main() -> int:
    app = OrionVApp()
    async with app.run_test(size=(180, 50)) as pilot:
        for _ in range(40):
            await pilot.pause()
            if app._nats_client.connection_state == "connected":
                break
            await asyncio.sleep(0.25)
        assert app._nats_client.connection_state == "connected", "нет NATS"

        deadline = asyncio.get_event_loop().time() + 20.0
        text = ""
        while asyncio.get_event_loop().time() < deadline:
            await pilot.pause()
            text = await _status_text(app)
            if re.match(r"^QIKI-[0-9A-F]{6} ", text):
                break
            await asyncio.sleep(0.5)
        first_line = text.splitlines()[0] if text else ""
        assert re.match(r"^QIKI-[0-9A-F]{6} ", first_line), (
            f"identity-строка без живого серийника: {first_line!r}"
        )
        assert "додекаэдр · 12 граней" in first_line
        assert re.search(r"модулей \d+/12", first_line)
        print(f"[smoke] identity живьём: {first_line.strip()}")

        tooltip = str(app.query_one("#orionv-mfd-status", Static).tooltip or "")
        assert "hardware_profile_hash" in tooltip and "суррогат" in tooltip
        print("[smoke] evidence-мета в tooltip рамки (источник серийника назван) ✓")

        qiki_panel = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "— граница:" in qiki_panel and "доверие:" in qiki_panel, (
            "honesty-строка панели QIKI (Z7) не найдена"
        )
        print("[smoke] панель QIKI: honesty-строка (граница | источник | доверие) на месте ✓")
    print("[smoke] Этап 7 PASS: идентичность QIKI честна на живом стеке")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
