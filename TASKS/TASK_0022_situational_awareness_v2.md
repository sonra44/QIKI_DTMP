# TASK-0022 — Situational Awareness v2 (stable lifecycle, anti-flapping, operator controls)

## Why
v1 added core situation detection, but lifecycle behavior around threshold jitter and temporary data loss was not stable enough for operators.

## What changed

### 1) Lifecycle rules (deterministic)
- Added `SituationStatus`: `ACTIVE | LOST | RESOLVED`.
- Added env knobs:
  - `LOST_CONTACT_WINDOW_S` (default `2.0`)
  - `SITUATION_AUTO_RESOLVE_AFTER_LOST_S` (default `2.0`)
- Behavior:
  - `situation_lost_contact` emitted exactly once when active situation stays absent beyond lost window.
  - `situation_resolved` emitted after lost timeout if contact does not recover.
  - On recovery before auto-resolve, situation returns to `ACTIVE` with `situation_updated` and reason `CONTACT_RESTORED`.

### 2) Anti-flapping
- Added env knobs:
  - `SITUATION_CONFIRM_FRAMES` (default `3`)
  - `SITUATION_COOLDOWN_S` (default `5.0`)
- Behavior:
  - Situation is created only after `confirm_frames` consecutive hits.
  - After resolve, same situation ID is blocked from immediate re-open until cooldown expires.

### 3) Operator controls / UX
- Added hotkeys in controller:
  - `]` / `a` / `j` → next situation
  - `[` / `k` → previous situation
  - `F` → focus selected situation target
  - `A` → acknowledge selected situation (snooze)
- Added env knob:
  - `SITUATION_ACK_S` (default `10.0`)
- ACK behavior:
  - stored as per-situation timer (`acked_until_by_situation`), suppresses visual emphasis during active timer.

### 4) EventStore contract hardening
Situation events are now written with stable payload fields:
- `event_type`: `situation_created | situation_updated | situation_resolved | situation_lost_contact`
- payload required:
  - `timestamp` (float)
  - `session_id` (str)
  - `track_id` (str)
  - `situation_id` (str)
  - `severity` (`INFO|WARN|CRITICAL`)
  - `reason` via event `reason` field (human-readable code)
  - `metrics` (dict)

## Files
- `src/qiki/services/q_core_agent/core/radar_situation_engine.py`
- `src/qiki/services/q_core_agent/core/radar_pipeline.py`
- `src/qiki/services/q_core_agent/core/radar_controls.py`
- `src/qiki/services/q_core_agent/core/radar_view_state.py`
- `src/qiki/services/q_core_agent/core/radar_backends/unicode_backend.py`
- `src/qiki/services/q_core_agent/core/terminal_radar_renderer.py`
- `src/qiki/services/q_core_agent/core/terminal_input_backend.py`
- `src/qiki/services/q_core_agent/core/mission_control_terminal.py`
- `src/qiki/services/q_core_agent/tests/test_radar_situational_awareness.py`
- `src/qiki/services/q_core_agent/tests/test_radar_controls.py`

## Verification
Docker-first test run:

```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev pytest -q \
  src/qiki/services/q_core_agent/tests/test_radar_situational_awareness.py \
  src/qiki/services/q_core_agent/tests/test_radar_controls.py \
  src/qiki/services/q_core_agent/tests/test_radar_pipeline.py \
  src/qiki/services/q_core_agent/tests/test_terminal_renderer.py
```

Result: all tests passed.

## Notes
- No changes to UI/ORION mission logic.
- Existing unrelated local edits were not included in this task commit scope.
