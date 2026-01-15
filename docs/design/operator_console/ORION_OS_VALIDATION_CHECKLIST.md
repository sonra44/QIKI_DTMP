# ORION Shell OS — Validation Checklist (Operator Console TUI)

**Purpose:** repeatable, operator-driven validation of ORION “Shell OS” UX without touching radar priorities.  
**Rule:** record results as ✅/❌ with a short note (what, where, how to reproduce).

---

## 0) Preflight (runtime)

- [ ] Run via Docker (Phase1 + operator console):
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
  - `docker attach qiki-operator-console` (detach: `Ctrl+P` then `Ctrl+Q`)
- [ ] Confirm health: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps` shows `healthy` for `nats`, `q-sim-service`, `operator-console`.
- [ ] If validating BIOS block: start `q-bios-service` and confirm it becomes `healthy` (otherwise BIOS will be `Not available/Нет данных` by design).

---

## 1) Global invariants (must always hold)

- [ ] Every visible label/value is bilingual `EN/RU` (no spaces around `/`).
- [ ] No abbreviations by default (see allowed exceptions + glossary requirements in `docs/design/operator_console/ABBREVIATIONS_POLICY.md`).
- [ ] Missing data is shown as `N/A/—` (no invented zeros).
- [ ] UI structure (chrome) is stable across screens: header + sidebar + inspector + bottom bar.

---

## 2) Input/Output dock (calm operator loop)

- [ ] `command/команда>` input shows typed text (visible color), does not overflow outside the input border.
- [ ] `Output/Вывод` always shows the latest command/system messages (no need to switch screens).
- [ ] Focus works:
  - `Ctrl+E` focuses input.
  - `Tab` cycles focus without “getting lost”.
- [ ] Input routing (no mode toggle):
  - Shell commands are the default (`help`, `screen events`, `reload rules`, etc.).
  - QIKI intents require a prefix: `q:` or `//`.
  - Placeholder hints prefixes and never suggests a “mode toggle”.

---

## 3) Events/События — incidents workflow (no endless log)

**Enter:** `F3`

- [ ] Events can be paused and resumed:
  - `Ctrl+Y` toggles live/pause (tmux-safe).
  - Commands also work: `events pause`, `events live`.
- [ ] While paused:
  - `Unread/Непрочитано` increases on new incidents (new/updated incident keys).
  - `R` marks read and clears unread counter.
- [ ] Incident actions:
  - Select a row (mouse or `↑/↓`).
  - `A` acknowledges selected incident.
  - `X` clears acknowledged incidents.
- [ ] Bounded buffer:
  - incidents count does not grow unbounded (caps apply).
  - table does not attempt to render thousands of rows (render cap applies).

---

## 4) Inspector/Инспектор contract (predictable details)

- [ ] Inspector structure is always:
  1) `Summary/Сводка`
  2) `Fields/Поля`
  3) `Raw data (JSON)/Сырые данные (JSON)`
  4) `Actions/Действия`
- [ ] Selection-driven:
  - selecting a row updates inspector deterministically.
- no selection shows `N/A/—`.

---

## 5) Chrome stability under tmux resizing

- [ ] Resize terminal narrower/wider:
  - sidebar/inspector/keybar do not break layout.
  - long lines truncate with `…` instead of wrapping into chaos.
- [ ] Bottom bar does not crush content on low terminal height.

---

## 6) Non-priority radar safety (do not invest)

- [ ] `F2` does not crash the app.
- [ ] No radar UX redesign is performed as part of validation.

---

## 7) Rules/Правила — quick enable/disable + reload

**Enter:** `Ctrl+R` (or command `screen rules`)

- [ ] Table shows rules from `config/incident_rules.yaml` (ID/Enabled/Severity/Match).
- [ ] `Reload rules/Перезагрузить правила` button refreshes rules without restart.
- [ ] Toggle enabled state:
  - Select a rule row (`↑/↓`).
  - Press `T` and confirm `Yes/Да` or `No/Нет`.
  - After saving, rules reload automatically and UI updates.
