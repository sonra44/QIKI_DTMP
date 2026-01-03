# ORION Shell OS — Validation Run (2026-01-02)

**Scope:** UX validation for ORION Operator Console (“Shell OS” TUI).  
**Rule:** mark ✅/❌ and add a short reproduction note.  
**Non-goal:** radar UX/design (radar is stability-only).

---

## 0) Preflight (runtime)

- ✅ Run via Docker (Phase1 + operator console): `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
- ✅ Confirm health: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps` shows `healthy` for `nats`, `q-sim-service`, `operator-console`.
- ✅ ORION launched in tmux split pane via `docker attach qiki-operator-console` (detach: `Ctrl+P` then `Ctrl+Q`).

---

## 1) Global invariants (must always hold)

- [ ] Every visible label/value is bilingual `EN/RU` (no spaces around `/`).
- [ ] Abbreviations are controlled (no random shortenings):
  - allowed only in header blocks + table columns,
  - must be expanded via tooltip + Help glossary (`docs/design/operator_console/ABBREVIATIONS_POLICY.md`).
- ✅ Missing data is shown as `Not available/Нет данных` (e.g. Inspector raw data when nothing selected, CPU usage when absent).
- ✅ UI structure (chrome) is stable across screens: header + sidebar + inspector + bottom bar (fixed header overlap with Inspector under narrow splits).

---

## 2) Input/Output dock (calm operator loop)

- ✅ `command/команда>` input shows typed text (operator confirmed).
- ✅ Typed text does not overflow outside the input border (hard cap via `OPERATOR_CONSOLE_COMMAND_MAX_CHARS`, default 256).
- ✅ `Output/Вывод` always shows the latest command/system messages (e.g. Events paused/live notices).
- [ ] Focus works:
  - ✅ `Ctrl+E` focuses input (used to run `events pause` / `events live`).
  - ✅ `Tab` cycles focus (verified by typing not going into input after `Tab`).
- [ ] Mode toggle:
  - ✅ `Ctrl+G` toggles Shell ↔ QIKI mode.
  - ✅ Placeholder clearly indicates current mode (`command/команда>` vs `QIKI input/Ввод QIKI>`).

---

## 3) Events/События — incidents workflow (no endless log)

**Enter:** `F3`

- [ ] Events can be paused and resumed:
  - ✅ `Ctrl+Y` toggles live/pause (tmux-safe; table stops updating while paused).
  - ✅ Commands also work: `events pause`, `events live`.
- [ ] While paused:
  - ✅ `Unread/Непрочитано` increases on new events (visible in Inspector Actions as e.g. `31 Unread/Непрочитано`; updated while paused).
  - ✅ `R` marks read and clears unread counter (log: `Unread cleared/Непрочитано очищено`; counter may start rising again if events keep arriving).
- [ ] Incident actions:
  - ✅ Select a row (mouse or `↑/↓`).
  - ✅ `A` acknowledges selected incident (Inspector shows `Acknowledged/Подтверждено: yes/да`, log prints `Acknowledged/Подтверждено: <key>`).
  - ✅ `X` clears acknowledged incidents (log prints `Cleared acknowledged incidents/Очищено подтвержденных инцидентов: N`).
- [ ] Bounded buffer:
  - ✅ incidents count does not grow unbounded (caps apply via `OPERATOR_CONSOLE_MAX_EVENT_INCIDENTS`, default 500).
  - ✅ table does not attempt to render thousands of rows (render cap applies via `OPERATOR_CONSOLE_MAX_EVENTS_TABLE_ROWS`, default 200; burst publish sanity-tested without UI crash).

---

## 4) Inspector/Инспектор contract (predictable details)

- ✅ Inspector structure is always:
  1) `Summary/Сводка`
  2) `Fields/Поля`
  3) `Raw data (JSON)/Сырые данные (JSON)`
  4) `Actions/Действия`
- [ ] Selection-driven:
  - [ ] selecting a row updates inspector deterministically.
  - ✅ no selection shows `Not available/Нет данных`.

---

## 5) Chrome stability under tmux resizing

- [ ] Resize terminal narrower/wider:
  - [ ] sidebar/inspector/keybar do not break layout.
  - ✅ long lines truncate with `…` instead of wrapping into chaos (manual `tmux resize-pane -x 80` check).
- [ ] Bottom bar does not crush content on low terminal height.

---

## 6) Non-priority radar safety (do not invest)

- ✅ `F2` does not crash the app.
- [ ] No radar UX redesign is performed as part of validation.

---

## 7) Addendum (2026-01-03)

- ✅ The “long header bar everywhere” issue was confirmed to be DataTable column headers and reduced:
  - Events now uses compact columns: `Time/Время`, `Level/Уровень`, `Type/Тип`, `Age/Возраст`, `Count/Счётчик`, `Ack/Подтв`.
  - Radar uses compact columns including `Vr/Скорость` (expanded in Help glossary).
- ✅ `F9` prints/refreshes the glossary section (keyboard-first fallback for tooltips).
- ✅ Header (“orange rows”) moved to compact labels + compact units where needed (e.g. `Rad/Рад … µSv/h/мкЗв/ч`, `Age/Возраст 0.1s/0.1с`), with expansions available via Help glossary + tooltips.
