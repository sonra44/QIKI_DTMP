# ORION Shell OS — Validation Checklist (Operator Console TUI)

**Purpose:** repeatable, operator-driven validation of ORION “Shell OS” UX without touching radar priorities.  
**Rule:** record results as ✅/❌ with a short note (what, where, how to reproduce).

---

## 0) Preflight (runtime)

- ✅ Run via Docker (Phase1 + operator console): — запущено через compose, TUI подключена
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
  - `docker attach qiki-operator-console` (detach: `Ctrl+P` then `Ctrl+Q`)
- ✅ Confirm health: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps` shows `healthy` for `nats`, `q-sim-service`, `operator-console`. — подтверждено
- ✅ If validating BIOS block: start `q-bios-service` and confirm it becomes `healthy` (otherwise BIOS will be `Not available/Нет данных` by design). — `q-bios-service` healthy

---

## 1) Global invariants (must always hold)

- ✅ Every visible label/value is bilingual `EN/RU` (no spaces around `/`). — наблюдалось на System/Events
- ❌ No abbreviations by default (see allowed exceptions + glossary requirements in `docs/design/operator_console/ABBREVIATIONS_POLICY.md`). — видны `Rad/Рад`, `Vr/Ско`; глоссарий не подтверждён
- ✅ Missing data is shown as `N/A/—` (no invented zeros). — Events таблица
- ✅ UI structure (chrome) is stable across screens: header + sidebar + inspector + bottom bar. — видно на Events при tmux 160x40

---

## 1.5) Screens quick map (for validation)

- `System/Система` (F1)
- `Radar/Радар` (F2) — non-goal; stability only
- `Events/События` (F3)
- `Console/Консоль` (F4)
- `Summary/Сводка` (F5)
- `Power systems/Система питания` (F6)
- `Diagnostics/Диагностика` (F7)
- `Mission control/Управление миссией` (F8)
- `QIKI` (F9)
- `Sensors/Сенсоры` (Ctrl+N)
- `Propulsion/Двигатели` (Ctrl+P)
- `Thermal/Тепло` (Ctrl+T)
- `Rules/Правила` (Ctrl+R)

---

## 2) Input/Output dock (calm operator loop)

- ✅ `command/команда>` input shows typed text (visible color), does not overflow outside the input border. — длинная строка видна, текст остаётся внутри рамки
- ✅ `Output/Вывод` always shows the latest command/system messages (no need to switch screens). — ранее наблюдалось `Events paused/live`
- ✅ Focus works:
  - `Ctrl+E` focuses input. — ок
  - `Tab` cycles focus without “getting lost”. — циклично: input ↔ таблица (Events)
- ✅ Input routing (no mode toggle): — `q: ping` и `// ping2` уходят в QIKI (Output: intent + Sent)
  - Shell commands are the default (`help`, `screen events`, `reload rules`, etc.).
  - QIKI intents require a prefix: `q:` or `//`.
  - Placeholder hints prefixes and never suggests a “mode toggle”.

---

## 3) Events/События — incidents workflow (no endless log)

**Enter:** `F3`

- ✅ Events can be paused and resumed: — `Ctrl+Y` и `events pause/live` отработали
  - `Ctrl+Y` toggles live/pause (tmux-safe).
  - Commands also work: `events pause`, `events live`.
- ✅ While paused: — unread видно в always-visible chrome (keybar), `R` очищает unread
  - `Unread/Непрочитано` increases on new incidents (new/updated incident keys).
  - `R` marks read and clears unread counter.
- ❌ Incident actions (UI): — нужно ручное подтверждение именно через UI-хоткеи
  - Select a row (mouse or `↑/↓`).
  - `A` acknowledges selected incident. (не подтверждено в этом прогоне; команды `ack <key>` работают)
  - `X` clears acknowledged incidents. (команда `clear` работает; хоткей `X`/`x` нужно подтвердить вручную в UI)
  - `R` marks events read when paused and clears unread counter.
  - (Dev check) Unit tests cover pause+unread and X-clear semantics:
    - `docker compose -f docker-compose.phase1.yml exec qiki-dev pytest -q src/qiki/services/operator_console/tests/test_events_pause_unread.py src/qiki/services/operator_console/tests/test_events_ack_clear.py`
- ✅ Bounded buffer: — подтверждено капами + тестом
  - incidents store is capped by `OPERATOR_CONSOLE_MAX_EVENT_INCIDENTS` (default: 500).
  - events table render is capped by `OPERATOR_CONSOLE_MAX_EVENTS_TABLE_ROWS` (default: 200).
  - (Dev check) Incident store cap is covered by:
    - `docker compose -f docker-compose.phase1.yml exec qiki-dev pytest -q src/qiki/services/operator_console/tests/test_incidents_store.py::test_max_incidents_caps_store_to_latest_by_last_seen`

---

## 4) Inspector/Инспектор contract (predictable details)

- ✅ Inspector structure is always: — на Events видны `Summary/Fields/Actions/Raw data (JSON)`
  1) `Summary/Сводка`
  2) `Fields/Поля`
  3) `Actions/Действия`
  4) `Raw data (JSON)/Сырые данные (JSON)`
- ✅ Selection-driven: — выбор строки меняет инспектор детерминированно (Events/Sensors)
  - selecting a row updates inspector deterministically.
- no selection shows `N/A/—`.
  - (Dev check) Selection mapping on Events row highlight is covered by:
    - `docker compose -f docker-compose.phase1.yml exec qiki-dev pytest -q src/qiki/services/operator_console/tests/test_events_rowkey_normalization.py`

---

## 5) Chrome stability under tmux resizing

- ✅ Resize terminal narrower/wider: — tmux split 60/120: вместо wrap применяется reflow (tiny hides sidebar/inspector) и строки не “ломают” chrome
  - sidebar/inspector/keybar do not break layout.
  - long lines truncate with `…` instead of wrapping into chaos.
- ✅ Bottom bar does not crush content on low terminal height. — tmux высота 8/12: панели видимы, наложения не заметил

---

## 6) Radar/Радар — scope guard

- ✅ No radar UX redesign is performed as part of validation. — изменений не вносилось
