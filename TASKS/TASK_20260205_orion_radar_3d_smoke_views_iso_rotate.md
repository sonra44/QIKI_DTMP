**ID:** TASK_20260205_orion_radar_3d_smoke_views_iso_rotate  
**Status:** done  
**Owner:** codex  
**Date created:** 2026-02-05  

## Goal

Prove (Docker-first, no mouse/TTY dependency) that ORION operator-console can render **3D radar views** (`side/front/iso`) and that ISO rotate changes output deterministically.

## Canon references

- Coordinate contract + real-data proof: `TASKS/TASK_20260205_radar_3d_readiness_inputs_contract.md`
- Sim-truth non-zero Z/elev: `TASKS/TASK_20260205_radar_3d_sim_truth_nonzero_z.md` (HEAD `85de439`)
- ISO yaw alignment: `tests/unit/test_orion_radar_projection_contract.py` (HEAD `4cfda64`)

## Evidence (commands → output)

Rebuild + recreate operator-console (Docker-first):

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build --force-recreate operator-console
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console
```

Expected: `operator-console` is `healthy`.

Headless in-container smoke (Textual `run_test`) proving 3D views + ISO rotate:

```bash
docker exec -i qiki-operator-console python - <<'PY'
import asyncio
import time

import qiki.services.operator_console.main_orion as main_orion


async def _main() -> None:
    async def no_nats(self) -> None:  # noqa: ANN001
        self._boot_nats_init_done = True
        self._boot_nats_error = ""
        self.nats_client = None
        self.nats_connected = False

    main_orion.OrionApp._init_nats = no_nats  # type: ignore[method-assign]

    app = main_orion.OrionApp()
    now = time.time()
    app._tracks_by_id = {
        "Z001": ({"position": {"x": 0.0, "y": 100.0, "z": 0.0}, "iff": 1}, now),
        "Z050": ({"position": {"x": 0.0, "y": 100.0, "z": 50.0}, "iff": 2}, now),
    }

    async with app.run_test(size=(140, 44)) as pilot:
        app.action_show_screen("radar")
        await pilot.pause()

        for view in ("side", "front", "iso"):
            app._radar_view = view
            app._refresh_radar()
            await pilot.pause()
            ppi = app.query_one("#radar-ppi")
            content = getattr(ppi, "content", "")
            plain = content.plain if hasattr(content, "plain") else str(content)
            assert plain.strip(), f"empty ppi for view={view}"

        app._radar_view = "iso"
        app._radar_iso_yaw_deg = 45.0
        app._radar_iso_pitch_deg = 35.0
        app._refresh_radar()
        await pilot.pause()
        ppi = app.query_one("#radar-ppi")
        c1 = getattr(ppi, "content", "")
        s1 = c1.plain if hasattr(c1, "plain") else str(c1)

        app._radar_iso_yaw_deg = 65.0
        app._refresh_radar()
        await pilot.pause()
        c2 = getattr(ppi, "content", "")
        s2 = c2.plain if hasattr(c2, "plain") else str(c2)

        assert s1 != s2, "ISO rotate did not change PPI output"


asyncio.run(_main())
print("OK: orion radar 3D smoke (views + iso rotate)")
PY
```

Observed output:

```
OK: orion radar 3D smoke (views + iso rotate)
```
