# ORION V Clickable UX Acceptance Checklist

Status: active  
Date: 2026-03-01  
Scope: ORION V operator UI (Textual, terminal-first)

## Goal

Validate that ORION V remains truly clickable and operable in real terminal conditions, with keyboard parity and honest fallbacks.

## Preconditions

- Stack is running from `docker-compose.phase1.yml` + `docker-compose.operator.yml`.
- Live telemetry is present on `qiki.telemetry`.
- Test environment is recorded: terminal emulator, local/SSH, tmux on/off.

## Acceptance checks (must pass)

1. Mouse selection:
- Click on interactive list/table items changes focused/selected entity.
- Selection state is reflected in detail/inspector region without stale values.
- Click on `F1` cockpit quick-action buttons jumps to the intended detailed screen or triggers the intended QIKI pending-action path.

2. Mouse scroll:
- Wheel scroll changes scrollable context or zoom where applicable.
- No accidental tmux copy-mode capture in validated profile (or profile explicitly marked unsupported with keyboard fallback proof).

3. Mouse drag:
- Drag interactions (if implemented on target screen) produce deterministic UI change.
- Drag operation never blocks keyboard control after completion.

4. Keyboard parity:
- Every mouse-only critical action has keyboard alternative documented and working.
- Core parity set includes: move selection, confirm/select, back/cancel, panel/tab navigation.
- `F1` cockpit quick actions must keep keyboard parity with existing shell commands and hotkeys (`F2`, `F3`, `q confirm`, `q cancel`).

5. Degraded environments:
- Under SSH+tmux where mouse events are degraded, ORION V remains fully operable via keyboard.
- UI reports honest state (no fake "mouse active" hints).

6. No-mocks truth:
- Clicked data panels show live payload-backed values only.
- Missing data is rendered as semantic state/reason, not fabricated numbers.

7. Status bars readability (SKELETON/СКЕЛЕТ):
- At `311x90` and `140x44` window sizes, metric labels stay readable (`Power/EPS`, `Thermal`, `Comms`, `Hull`, `Incidents/Инциденты`).
- Bars are visually distinguishable by status (`OK/WARN/CRIT/NODATA`) and remain clickable to target level/subsystem.
- Before first telemetry sample, status-bars area is hidden (no layout overflow, no off-screen click targets).

## Evidence format (required)

- Command list used for run/repro.
- Environment header (`terminal`, `tmux`, `transport`, `window size`).
- Per-check result: `PASS/FAIL` + short note.
- If `FAIL`: exact failure path + expected behavior + next fix task link.
