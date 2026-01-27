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
- ✅ BIOS “loaded” confirmation is visible inside ORION (not only in `docker logs`): open Console (`F4`) and confirm the console history contains `BIOS loaded/BIOS загрузился: ...` after cold boot. — подтверждено

---

## 1) Global invariants (must always hold)

- ✅ Every visible label/value is bilingual `EN/RU` (no spaces around `/`). — наблюдалось на System/Events
- ✅ No abbreviations by default (see allowed exceptions + glossary requirements in `docs/design/operator_console/ABBREVIATIONS_POLICY.md`). — labels expanded; tmux evidence 2026-01-27
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

- ✅ Active pause visibility: — состояние симуляции видно в хедере
  - Spec reference: `docs/design/operator_console/SIMULATION_CONTROL_CONTRACT.md`
  - Send `simulation.pause` and confirm header shows `Sim/Сим Paused/Пауза`.
  - Send `simulation.start` and confirm header shows `Sim/Сим Running/Работает`.
  - Optional: send `simulation.start 2` and confirm header shows `Sim/Сим Running/Работает x2`.
  - Send `simulation.stop` and confirm header shows `Sim/Сим Stopped/Остановлено`.
  - Send `simulation.reset` and confirm (reset implies stop):
    - ConfirmDialog appears -> press `y`.
    - `Sim/Сим` becomes `Stopped/Остановлено`
    - Roll/Pitch in Navigation reset to `0.0°`

---

## 3) Events/События — incidents workflow (no endless log)

**Enter:** `F3`

- ✅ Events can be paused and resumed: — `Ctrl+Y` и `events pause/live` отработали
  - `Ctrl+Y` toggles live/pause (tmux-safe).
  - Commands also work: `events pause`, `events live`.
- ✅ While paused: — unread видно в always-visible chrome (keybar), `R` очищает unread
  - `Unread/Непрочитано` increases on new incidents (new/updated incident keys).
  - `R` marks read and clears unread counter.
- ✅ Incident actions (UI): — подтверждено через UI-хоткеи на выбранной строке
  - Select a row (mouse or `↑/↓`).
  - `A` acknowledges selected incident.
  - `X` clears acknowledged incidents.
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

---

## 7) QIKI — proposals decision workflow (no auto-actions)

**Enter:** `F9`

- ✅ Generate proposals: — отправить intent и увидеть proposal list
  - `Ctrl+E` → `q: dock.on` → `Enter`
  - Output shows `Sent to QIKI/Отправлено в QIKI` + `QIKI: OK/ОК` and at least 1 proposal.
- ✅ Accept proposal from UI: — `v` → confirm `y`
  - Press `v` (accept) and confirm `y`.
  - Output shows `QIKI: Accepted/Принято` and proposals count becomes 0.
- ✅ Reject proposal from UI: — `b` → confirm `y`
  - Generate a new proposal again: `Ctrl+E` → `q: dock.on` → `Enter`.
  - Press `b` (reject) and confirm `y`.
  - Output shows `QIKI: Rejected/Отклонено` and proposals count becomes 0.
- ✅ Evidence in faststream-bridge logs: — видны follow-up intents на `qiki.intents`
  - `docker compose -f docker-compose.phase1.yml logs --tail=200 faststream-bridge | sed -r 's/\x1b\[[0-9;]*m//g' | rg -n "proposal (accept|reject)"`
