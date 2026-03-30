# ORION Shell OS — Header (“orange top bar”) Redesign Plan

## Goal

Make the top status area scalable and readable under tmux splits, while still allowing a high information density:

- **Compact** in the header (short labels ok).
- **Complete** on demand (full bilingual naming + units + meaning via tooltip and/or Inspector/Help).

## Constraints / Policy

- UI remains bilingual `EN/RU` (no spaces around `/`).
- If we allow abbreviations, they are **header-only** and must have a **canonical expansion**:
  - Tooltip shows full `EN/RU` wording + units.
  - Help/Glossary lists the same expansions.
- No “invented” values: missing data stays `Not available/Нет данных`.

## Implementation Steps (linear)

1) **Define “header fields” contract**
   - Create a small schema for header items: `key`, `short_label_en/ru`, `full_label_en/ru`, `unit_en/ru`, `value`.
   - Decide a fixed ordering and grouping (e.g. Link/Power/Structure/Environment).

2) **Render as blocks (not a single string)**
   - Replace the current string-based header with a 2-row (or adaptive) grid of widgets:
     - each block renders `short_label + value` and truncates with `…`.
   - Keep grid stable across resize; no wrapping chaos.

3) **Tooltips for full context**
   - For each block, set `tooltip` to a full bilingual description:
     - `Full label (EN/RU) + value + unit + 1-line meaning`.
   - Use the same source text for all tooltip content (single source of truth).

4) **Keyboard-first fallback (no mouse required)**
   - Add `F9 Help/Помощь` section: “Header glossary / Глоссарий хедера”.
   - Optionally add a command: `header.details/детали.хедера` that prints the full set into `Output/Вывод` or Inspector.

5) **Validation**
   - Under narrow pane widths (e.g. 80 columns) header stays inside its region and truncates with `…`.
   - Tooltip shows correct full text for several representative fields.
   - Help shows glossary lines that match the tooltip text exactly.
   - Update `docs/design/operator_console/ORION_OS_VALIDATION_RUN_2026-01-02.md` with ✅/❌ notes.

## Commands (runtime)

- Start ORION: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
- Attach TUI: `docker attach qiki-operator-console` (detach: `Ctrl+P` then `Ctrl+Q`)

