# ORION V Profiles Acceptance Artifact — 2026-03-05

Status: pass
Date: 2026-03-05
Scope: profile parity for `ORIONV_UI_PROFILE=clean|dense` and alignment with clickable status-bars design.

## Goal

Prove that profile-driven UI (`clean` default, `dense` optional) stays operable and visually consistent with the new status-bars pattern.

## Evidence Sources

1. Runtime evidence (clean profile):
- historical tmux session `0`, pane `%7`, geometry `311x90`.
- Captured `SKELETON/СКЕЛЕТ` with unicode bars and click hints (`click→F2` / `click→F3`).

2. Automated profile evidence (dense profile):
- Headless Textual test confirms `ui-dense` class on app mount when `ORIONV_UI_PROFILE=dense`.
- Header rendering test confirms profile marker in chrome (`UI: dense`).

## Commands

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_header.py \
  tests/unit/test_orion_v_app_incidents.py::test_app_uses_dense_profile_class_from_env \
  tests/unit/test_orion_v_status_bars.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/operator_console/orion_v/widgets/header.py \
  src/qiki/services/operator_console/orion_v/app.py \
  tests/unit/test_orion_v_header.py \
  tests/unit/test_orion_v_app_incidents.py

PANE_ID="$(tmux list-panes -a -F '#{pane_id} #{pane_current_path} #{pane_current_command}' | rg '/home/sonra44/QIKI_DTMP .*python|/home/sonra44/QIKI_DTMP .*bash' | head -n1 | cut -d' ' -f1)"
tmux capture-pane -p -t "$PANE_ID" -S -240 | rg -n "SKELETON/СКЕЛЕТ|click→F2|click→F3|UI:"
```

## Result Matrix

- Clean profile runtime readability: PASS
- Dense profile activation (`ui-dense`): PASS
- Header profile marker (`UI: clean|dense`): PASS
- Status-bars click discoverability hints: PASS
- No-mocks semantics preserved: PASS

## Verdict

Profile parity acceptance is PASS for this scope.
