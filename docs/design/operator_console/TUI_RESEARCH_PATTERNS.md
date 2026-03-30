# TUI Research Notes — Patterns for ORION “Shell OS”

**Date:** 2025-12-30  
**Goal:** collect proven interaction patterns from mature TUIs and map them to ORION’s needs (operator cockpit, calm command bus, incident-centric events).

> This file intentionally includes external references (URLs) as design provenance.

---

## 1) Stable chrome + command line + keybar (MC pattern)

**Observation:** Midnight Commander demonstrates a long-lived “TUI OS” layout: most of the screen is panels, bottom has a command line, bottom-most line is function key labels, top has a menu bar. This yields a **predictable frame** where content changes but the structure doesn’t.

References:
- https://manpages.ubuntu.com/manpages/trusty/en/man1/mc.1.html
- https://www.linux.com/news/cli-magic-midnight-commander/
- https://source.midnight-commander.org/man/mc.html

Mapping to ORION:
- Keep ORION’s chrome stable (header/sidebar/inspector/bottom command).
- Treat the bottom area as an always-available “command bus”, and keep keybar labels consistent across screens.

---

## 2) Multi-pane selection + preview/inspector (Ranger + Lazygit pattern)

**Observation:** Ranger (Miller columns) and Lazygit both center the UI around:

- list/table navigation
- selection focus
- a “preview/inspector” pane that updates with the selection

This makes a TUI feel like a “desktop environment”, not a menu.

References:
- https://github.com/ranger/ranger (three columns + preview)
- https://en.wikipedia.org/wiki/Ranger_(file_manager) (Miller columns)
- https://git-how.com/ (Lazygit: multi-panel focus + filter `/`)
- https://www.freecodecamp.org/news/how-to-use-lazygit-to-improve-your-git-workflow/

Mapping to ORION:
- Standardize every ORION screen to: `table/list → selection → inspector`.
- Inspector becomes the consistent “detail view” for all objects (event/incident/track/mission item/console line).

---

## 3) High-rate streams must be controllable (K9s logs pattern)

**Observation:** K9s treats logs as a special view with:

- bounded buffer (“how many lines to keep”)
- tail size (“how many lines to fetch initially”)
- autoscroll toggles (follow vs pause)

This directly solves the “infinite dumb tail” problem and makes reading feasible.

References:
- https://k9scli.io/topics/config/ (logger.tail/logger.buffer/disableAutoscroll)
- https://deepwiki.com/derailed/k9s/5.4-logs-view (logs view UI elements)
- https://github.com/derailed/k9s/issues/155 (why autoscroll toggle matters)

Mapping to ORION:
- Events must have bounded memory.
- Add `LIVE/ЖИВОЕ` vs `PAUSED/ПАУЗА` for events and a visible unread counter while paused.

---

## 4) Operator “actions on selection” (btop pattern)

**Observation:** btop combines:

- global graphs/panels
- a selectable process list
- detailed stats for the selected item
- filtering and the ability to pause the list
- in-UI configuration changes

Reference:
- https://github.com/aristocratos/btop (features: filter, pause list, detailed stats)

Mapping to ORION:
- Apply the same idea to incidents/events: selection shows details, actions apply to selection (ack/export/navigate).

---

## 5) Follow mode as an explicit state (less/journalctl concept)

**Observation:** “follow mode” should be explicit and reversible (follow → stop following → navigate/search). This is a strong mental model for operators.

References:
- https://unix.stackexchange.com/questions/309403/breaking-out-of-follow-mode-with-less-and-journalctl
- https://betterstack.com/community/guides/logging/how-to-control-journald-with-journalctl/ (follow + line limit)

Mapping to ORION:
- Events view: explicit follow state + explicit exit to “read mode”.
- Default: follow on, but any manual scroll/selection should pause follow.

---

## 6) Textual-native capabilities worth using (command palette + bounded logs)

**Observation:** Textual provides:

- a built-in Command Palette system (discover/search, screen-scoped commands, fault-tolerant providers)
- RichLog max_lines + auto_scroll controls for bounded logs

References:
- https://textual.textualize.io/guide/command_palette/
- https://textual.textualize.io/widgets/rich_log/

Mapping to ORION:
- Consider adding Command Palette as the “OS launcher” later.
- For the calm command output channel, prefer a bounded log widget (or implement bounded DataTable behavior) with explicit follow control.

