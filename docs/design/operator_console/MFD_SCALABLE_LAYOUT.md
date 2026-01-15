# MFD Cockpit — Scalable Layout Spec (Textual)

## Goal
Make ORION’s cockpit/MFD UI *predictably readable* across:
- full-screen terminals,
- `tmux` vertical/horizontal splits,
- “small” panes during development.

The UI must keep a stable mental model: **Header (status)** → **Workspace (page content)** → **Bottom Bar (output + command + keybar)**, with optional **Sidebar** and **Inspector**.

## Design Principles
- **Consistency over density**: same meaning should appear in the same region across sizes.
- **“Label near value”**: short label adjacent to its value; prefer `Label Value` and stable ordering.
- **Graceful degradation**: as space shrinks, reduce *chrome* first (sidebar/inspector), then reflow panels, then reduce table columns.
- **Bilingual everywhere**: `EN/RU` with no spaces around `/`.
- **Abbreviations are allowed** only under the policy; every abbreviation must be discoverable via `F9` glossary.

## Density Modes (Breakpoints)
We treat scaling as *density modes*.

### `wide`
- Sidebar: visible
- Inspector: visible
- System dashboard: `2x2` grid
- Tables: full columns where possible

### `normal`
- Sidebar: visible
- Inspector: visible, narrower
- System dashboard: `2x2` grid

### `narrow`
- Sidebar: narrower; optional “icon+label” compact line format
- Inspector: **auto-hidden** (toggleable)
- System dashboard: **reflow to `1x4`** vertical stack
- Tables: compact widths; reduce “nice to have” columns

### `tiny`
- Sidebar: hidden
- Inspector: hidden
- System dashboard: single-column + optionally show only 2 panels (configurable)
- Bottom bar: smaller; output area preserved

## Reflow Rules (Priority)
1) Keep `#orion-header` always visible (2 rows max).
2) Keep `#bottom-bar` always visible (output + input + keybar).
3) Hide/compact **Inspector** before shrinking content tables.
4) Reflow **system dashboard** grid before truncating values.
5) For tables, prefer:
   - abbreviating headers,
   - reducing column widths,
   - switching to “compact table mode” (fewer columns) on narrow panes.

## Implementation Notes (Textual)
- Responsive logic lives in `OrionApp._apply_responsive_chrome()` and is called from `on_resize()`.
- Prefer runtime style changes (e.g. `styles.display`, `styles.width`) over hard-coded CSS when the decision depends on the live terminal size.
- For DataTable scalability, use either:
  - dynamic column widths, or
  - dual tables (full vs compact) with `display: none` switching per density mode.

## Checklist
- [ ] System dashboard grid reflows (`2x2` → `1x4`) based on width
- [ ] Inspector auto-hides on narrow, with a toggle hotkey
- [ ] Sidebar reduces safely on narrow, hides on tiny
- [ ] Tables have a compact mode (no horizontal “…” chaos)
- [ ] `F9` glossary includes all abbreviations introduced for compact modes

## Boot Screen (no-mocks)
ORION shows a cold-boot splash before the main UI to improve operator orientation.

**Hard rule:** the boot screen must not invent statuses. If a signal is not proven, show `N/A` / `WAITING`.

### Allowed on Boot Screen
- Cosmetic “typewriter” lines that are *purely visual* (no `[OK]`, no `%`, no `ETA`).
- Real connectivity status (e.g. NATS connect succeeded / failed).
- Real BIOS status once `qiki.events.v1.bios_status` arrives, including row-by-row POST results from the payload.

### Sizing / readability
- Boot container must fit `tmux` splits: use a max width and allow shrinking.
- Limit the number of printed POST rows; prioritize non-OK rows first.

### Tuning via env (for demos without fake data)
- `ORION_BOOT_COSMETIC_SEC` — cosmetic delay (default small; raise to 10–20s if you want the boot to be observable).
- `ORION_BOOT_NATS_TIMEOUT_SEC` — how long we wait for NATS init result.
- `ORION_BOOT_BIOS_TIMEOUT_SEC` — how long we wait for the first BIOS event.
- `ORION_BOOT_POST_MAX_ROWS` — max POST lines to print (non-OK first).
- `ORION_BOOT_POST_LINE_DELAY_SEC` — per-line delay for readable scrolling.
