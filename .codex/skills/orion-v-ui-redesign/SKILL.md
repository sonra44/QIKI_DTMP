---
name: orion-v-ui-redesign
description: >-
  Practical redesign workflow for ORION V TUI: reduce visual noise, improve information hierarchy,
  and keep mouse/keyboard actions unified with operator-safe behavior.
---

# ORION V UI Redesign Skill

Use when user says UI is unacceptable, hard to read, or not operator-friendly.

## Goal

Make ORION V visually clear and operationally useful without breaking:
- no-mocks policy,
- existing action/audit contracts,
- Docker-first validation flow.

## Design Rules

1. Keep one primary focus per screen:
- Header = global state.
- Action bar = navigation + core actions.
- Main panel = current level content.
- Overlay = only urgent incidents.

2. Prefer calm contrast over heavy decoration:
- Light borders (`round ... 20%` style intensity),
- compact titles,
- minimal filled backgrounds.

3. Mouse and keyboard parity:
- Every clickable action must route to existing `action_*`.
- Do not create alternative logic branches for click-only behavior.

4. Literal raw payload rendering:
- F4 raw stream must render literal text; never parse payload as markup.

5. Preserve product truth:
- ORION V is the primary operator surface, not a decorative dashboard.
- UI may interpret truth, but must not replace physical/runtime truth with invented values or convenience text.
- Keep the distinction visible between raw fact, derived/aggregated view, and operator guidance.

6. Keep product language disciplined:
- Prefer operator/sim-game wording over platform/demo wording.
- QIKI must remain visually distinct from subsystem health.
- Do not smuggle stale dossier/reference status into the UI as if it were current runtime truth.

## Execution Loop

1. Baseline capture:
- `tmux capture-pane` of current ORION V screen in target pane.

2. Minimal style slice:
- Edit `src/qiki/services/operator_console/orion_v/app.py` CSS only first.
- Keep geometry-safe defaults (`clean`), optional `dense` profile.

3. Behavior guard:
- Ensure click routes still call existing app actions.

4. Validation:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_deep_dive.py tests/unit/test_orion_v_systems_uses_hardware_model.py tests/unit/test_orion_v_raw.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/app.py src/qiki/services/operator_console/orion_v/screens/raw.py src/qiki/services/operator_console/orion_v/widgets/header.py`

5. Runtime proof:
- Rebuild operator-console and capture tmux evidence after restart.

## Reference use
- If you use `/home/sonra44/QIKI_DTMP/.codex/imp` or old redesign notes, treat them as reference only.
- Import durable rules from them, not old blocker/slice status.
- When a reference image or old design memo conflicts with current operator truth or active canon, current canon wins.

## Sources (primary)

- Textual actions: https://textual.textualize.io/guide/actions/
- Textual styling/CSS: https://textual.textualize.io/guide/CSS/
- Textual testing: https://textual.textualize.io/guide/testing/
