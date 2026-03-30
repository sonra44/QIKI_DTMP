# WORKLOG — ORION UI layout pass (tmux-friendly) — 2026-01-18

## Цель

Сделать ORION Operator Console **читабельной и устойчивой** в tmux-сплитах (узкие терминалы), с учётом того, что
дальше будет добавляться больше виртуализируемых переменных (Power / Thermal / Propulsion / Sensors / BIOS и т.д.).

## Инварианты (жёсткие правила проекта)

- **Docker-first (Rule B)**: проверки/тесты/запуск — в Docker.
- **Serena-first**: чтение/поиск/правки по репо — через Serena.
- **no-mocks**: если данных нет → честное `N/A`, не рисуем “красивые числа”.
- **no `*_v2`** и **no-duplicates**: не создаём параллельные каноны.
- **NATS subjects**: не “лечим” проблему ширины через раздувание subjects; семантика в payload.

## Короткий ресёрч (зачем это так)

- Textual (layout/CSS): подход через `layout: grid`, `dock`, `height: 1fr` и реакцию на resize — это “нормальный путь”
  для TUI-UI, а не хаки в рантайме.
- Textual `Log`/`RichLog`: управляется `wrap` и `max_lines`, поэтому “хвост вывода” лучше делать длиннее, но ограниченно.
- NATS subjects: документация рекомендует **короткие subjects** и вынос данных в payload; 256 — практический предел.

Ссылки (для контекста команды):
- <https://textual.textualize.io/guide/layout/>
- <https://textual.textualize.io/widgets/log/>
- <https://docs.nats.io/nats-concepts/subjects>

## Что изменено (код)

Файл:
- `src/qiki/services/operator_console/main_orion.py`

Правки:

1) **Скрытие плотного радара на узких терминалах**
- На `density in {"tiny","narrow"}` скрываем `#radar-ppi`, оставляем таблицу треков.
- Причина: PPI на узких терминалах становится нечитаемым и “ломает” раскладку.

2) **Профили ширин колонок (tmux presets)**
- `_apply_table_column_widths(...)` расширен, чтобы подстраивать ширины не только для summary/power, но и для:
  - `events-table`, `console-table`, `radar-table`
  - `sensors-table`, `propulsion-table`, `thermal-table`

3) **Читабельность статусов**
- В Sensors-экране статус рендерится цветом (Rich `Text`): `ok/warn/crit/na`.

4) **Увеличение лимитов отображения (без смены смысла)**
- `OrionInspector.safe_preview(...)`: default `max_chars=1024`, `max_lines=24`
  - Управляется env:
    - `OPERATOR_CONSOLE_PREVIEW_MAX_CHARS`
    - `OPERATOR_CONSOLE_PREVIEW_MAX_LINES`
- `command-output-log` (`RichLog`): default `max_lines=1024`
  - Управляется env:
    - `OPERATOR_CONSOLE_OUTPUT_MAX_LINES`

Важно: это **только отображение**. Ничего “смыслового” (subjects/контракты) не менялось.

## Проверка (Docker-first)

- `pytest -q src/qiki/services/operator_console/tests` — зелёный.
- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
  — консоль стартует; boot-screen рисуется.

## Следующее логичное улучшение (не делал в этом круге)

1) COSMOS-style **Limits/Alerts отдельным экраном** (persist until ack/hide) — без новых subjects (на базе telemetry + rules).
2) Расширить `status/limits` слой с Sensor Plane на Power/Thermal (по той же схеме `ok/warn/crit/na`).

