# TASK (2026-02-02): Thermal panel renders real nodes (no N/A from mismatched IDs)

## Goal

Eliminate confusing `N/A/—` values in ORION System screen Thermal panel that were caused by UI expecting non-existent thermal node IDs.

## Root cause (facts)

- SoT config `src/qiki/services/q_core_agent/config/bot_config.json` defines Thermal Plane nodes: `core`, `pdu`, `supercap`, `battery`, `dock_bridge`, `hull`.
- ORION System thermal panel previously hard-coded node IDs `bus` and `radiator`, which are not present in telemetry `thermal.nodes[]`.
- Result: operator saw `Bus/Шина = N/A/—` and `Radiator/Радиатор = N/A/—` even though thermal telemetry was healthy.

## Fix (no new contracts)

- ORION now builds a `thermal.nodes[]` map by `id` and renders the most important real nodes (up to 4) + external/core temps.
- Telemetry Dictionary extended to include `power.sources_w.*` and `power.loads_w.*` keys so audit tools and Inspector semantics remain aligned.

Files:
- `src/qiki/services/operator_console/main_orion.py`
- `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml`

## Evidence (runtime)

After rebuilding `operator-console`, the Thermal panel shows real nodes and no longer shows `Bus/Шина` or `Radiator/Радиатор`.

Captured via tmux:
- `tmux capture-pane -pt %19 -S -80`

Excerpt:
- `Core/Ядро 19.6°C`
- `PDU/ПДУ 21.3°C`
- `Battery/Батарея 18.7°C`
- `Supercap/Суперкап 13.5°C`

Telemetry dictionary audit:
- `python tools/telemetry_smoke.py --audit-dictionary ...` no longer reports `NOT_IN_DICTIONARY` entries for `power.sources_w.*` / `power.loads_w.*`.

