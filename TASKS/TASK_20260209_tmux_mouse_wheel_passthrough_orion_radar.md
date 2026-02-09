# TASK: tmux mouse wheel passthrough for ORION radar zoom

**ID:** TASK_20260209_TMUX_MOUSE_WHEEL_PASSTHROUGH_ORION_RADAR  
**Status:** done  
**Owner:** codex + user  
**Date created:** 2026-02-09  

## Goal

Make the operator procedure deterministic: ORION radar wheel zoom works in the canonical environment (SSH + tmux), and the fix is documented with a copy-paste tmux snippet.

## Operator Scenario (visible outcome)

- Operator runs ORION inside tmux.
- Mouse wheel over the Radar view zooms in/out (instead of tmux scrollback).
- Outside full-screen apps, wheel still scrolls tmux history.

## Reproduction Command

```bash
# 1) Start ORION stack
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
docker attach qiki-operator-console

# 2) In tmux, switch to Radar (F2) and try wheel zoom.
# If wheel scrolls tmux history instead: apply the snippet in docs below and reload tmux config.
```

## Before / After

- Before: in tmux with `mouse on`, wheel events may be captured by tmux scrollback; ORION does not receive zoom events.
- After: tmux forwards `WheelUpPane/WheelDownPane` to full-screen apps (`#{alternate_on}`), so ORION receives wheel events.

## Impact Metric

- Metric: operator time-to-fix for “wheel zoom doesn’t work in tmux”.
- Baseline: ad-hoc tribal knowledge.
- Actual: 1 copy/paste snippet + reload (`tmux source-file ~/.tmux.conf`).

## Evidence

- Doc snippet: `docs/design/operator_console/TMUX_MOUSE_WHEEL_PASSTHROUGH.md`
- RFC reference: `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`

