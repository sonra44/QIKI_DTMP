from __future__ import annotations

import asyncio

from textual.widgets import Static

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.screens.cockpit import OrionVCockpitScreen


async def main() -> None:
    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()

        cockpit = app.query_one("#orionv-cockpit", OrionVCockpitScreen)
        cockpit.set_state(
            telemetry={
                "power": {"soc_pct": 18.0, "bus_v": 27.8, "bus_a": 2.3},
                "sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0},
            },
            nats_connected=True,
            active_incidents=1,
            incidents=[{"severity": "C", "id": "INC-1", "description": "Перегрев"}],
        )
        await pilot.pause()

        body = app.query_one("#orionv-cockpit-body", Static)
        intervention = app.query_one("#orionv-cockpit-intervention", Static)
        text = body.render().plain.splitlines()
        right_text = intervention.render().plain.splitlines()
        print("OK: orion_v_f1_body_smoke")
        print(f"BODY_TITLE={body.border_title}")
        print(f"BODY_SUBTITLE={body.border_subtitle}")
        print(f"INTERVENTION_TITLE={intervention.border_title}")
        print(f"INTERVENTION_SUBTITLE={intervention.border_subtitle}")
        print(f"LINE_1={text[0] if len(text) > 0 else ''}")
        print(f"LINE_2={text[1] if len(text) > 1 else ''}")
        print(f"LINE_3={text[2] if len(text) > 2 else ''}")
        print(f"RIGHT_LINE_1={right_text[0] if len(right_text) > 0 else ''}")
        print(f"RIGHT_LINE_2={right_text[1] if len(right_text) > 1 else ''}")


if __name__ == '__main__':
    asyncio.run(main())
