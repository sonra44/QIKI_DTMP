---
name: orion-operator-smoke
description: Deterministic ORION operator-console smoke (Docker-first) without relying on mouse/TTY visuals. Proves container health + key radar invariants via Textual run_test inside the running container.
---

# ORION Operator Console — Smoke (Docker-first, proof-oriented)

## Goal
Generate evidence that `operator-console` is healthy and that the radar UX invariants hold, **without** relying on mouse wheel or terminal rendering.

This smoke is intentionally **non-interactive**: it runs a headless Textual `run_test` inside the running container and asserts on widget content/state.

## Procedure

1) Ensure the stack is up (rebuild if needed):

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build --force-recreate operator-console
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console
```

Expected: `operator-console` is `healthy`.

2) Run the in-container smoke (requires `-i` to feed stdin):

```bash
docker exec -i qiki-operator-console python - <<'PY'
import asyncio
import time

import qiki.services.operator_console.main_orion as main_orion
from qiki.services.operator_console.radar.unicode_ppi import pick_nearest_track_id


async def _main() -> None:
    async def no_nats(self) -> None:  # noqa: ANN001
        self._boot_nats_init_done = True
        self._boot_nats_error = ""
        self.nats_client = None
        self.nats_connected = False

    main_orion.OrionApp._init_nats = no_nats  # type: ignore[method-assign]

    app = main_orion.OrionApp()
    now = time.time()
    app._tracks_by_id = {"AAAA": ({"range_m": 100.0, "bearing_deg": 0.0}, now)}

    async with app.run_test(size=(140, 44)) as pilot:
        app.action_show_screen("radar")
        await pilot.pause()

        app._radar_overlay_labels = True
        app._radar_zoom = 1.0
        app._refresh_radar()
        await pilot.pause()

        legend = app.query_one("#radar-legend")
        content = getattr(legend, "content", "")
        plain = content.plain if hasattr(content, "plain") else str(content)
        assert "AAAA" in plain
        assert ("Sel:" in plain) or ("Выбор:" in plain)
        assert "LBL:req" in plain

        app._radar_zoom = 3.0
        app._refresh_radar()
        await pilot.pause()
        content2 = getattr(legend, "content", "")
        plain2 = content2.plain if hasattr(content2, "plain") else str(content2)
        assert "LBL:req" not in plain2
        assert "LBL" in plain2

    width_cells, height_cells = 20, 10
    click_center_x, click_center_y = width_cells // 2, height_cells // 2
    tracks = [("A", {"position": {"x": 0.0, "y": 0.0, "z": 0.0}})]

    picked_low = pick_nearest_track_id(
        tracks,
        click_cell_x=click_center_x + 2,
        click_cell_y=click_center_y,
        width_cells=width_cells,
        height_cells=height_cells,
        max_range_m=1000.0,
        view="top",
        zoom=1.0,
    )
    assert picked_low == "A"

    picked_high = pick_nearest_track_id(
        tracks,
        click_cell_x=click_center_x + 2,
        click_cell_y=click_center_y,
        width_cells=width_cells,
        height_cells=height_cells,
        max_range_m=1000.0,
        view="top",
        zoom=9.0,
    )
    assert picked_high is None


asyncio.run(_main())
print("OK: orion operator-console smoke")
PY
```

Expected output: `OK: orion operator-console smoke`.

## Notes
- This smoke is compatible with SSH+tmux and Termius limitations: it does not require mouse wheel.
- Do not modify the running container state beyond these checks.

