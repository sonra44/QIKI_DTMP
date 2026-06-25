# TUI на Python с нуля — практический референс (Textual)

> Сохранено 2026-06-25. Источник: оператор. Назначение: справочник под внедрение
> ORION V evidence-card stream. НЕ канон QIKI — это инженерный референс по Textual.
> Реконсиляция «что годится / что нет для нашего случая» — в конце файла + в памяти.

Разбито на слои: от выбора фреймворка до конкретных библиотек и паттернов.

## Слой 0 — Выбор фреймворка
**Textual** — выбор по умолчанию в 2025 для нового интерактивного проекта (макс за минимум кода).
`prompt-toolkit` — когда приложение в основном редактирование строк (IPython, pgcli). `urwid` —
ветеран. `blessed` — только примитивы терминала, слой виджетов пишешь сам.
Бенч: Textual ~120 FPS (segment trees Rich, обновляются только «грязные» регионы); 10k виджетов @45 FPS;
urwid OOM на 5k. Другие языки: Go `bubbletea`/`tview`, Rust `ratatui`.

## Слой 1 — Структура приложения с нуля
Минимальный скелет: `App` + `CSS_PATH="app.tcss"` (CSS в ФАЙЛ, не в строку) + `BINDINGS` + `compose()`
с `Header`/`Footer`/контейнерами. Dev-режим с hot-reload CSS: `textual run --dev app.py`. Debug console
для `print()` в отдельном окне.

```python
class MyApp(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [("q", "quit", "Выйти")]
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Input(placeholder="Фильтр...", id="filter")
                yield DataTable(id="table")
            yield Static("Детали", id="detail")
        yield Footer()
```

## Слой 2 — Встроенные виджеты (без установки)
- Данные/таблицы: `DataTable` (сортировка, cursor, kbd nav), `Tree`, `ListView`
- Ввод: `Input`, `TextArea` (syntax highlight), `Select`, `RadioSet`, `Checkbox`, `Switch`
- Вывод: `Static` (Rich-разметка), `RichLog` (инкрементальный лог), `Log`, `Markdown`, `Pretty`
- Хром: `Header`, `Footer`, `TabbedContent`, `ContentSwitcher`, `Collapsible`, `ProgressBar`,
  `LoadingIndicator`, `Sparkline`
- Контейнеры: `Horizontal`, `Vertical`, `Grid`, `ScrollableContainer`, `Center`, `Middle`

## Слой 3 — Экосистема плагинов (pip install)
`textual-plotext` (графики, обёртка Plotext; через `PlotextPlot.plt`, не `plt.show()`; темы
`textual-design-dark/light`), `textual-autocomplete`, `textual-image` (Kitty/Sixel/Halfblock),
`textual-canvas`, `textual-fspicker`, `rich-pixels`.

## Слой 4 — Архитектурные паттерны
- **Reactive** — связь данных и UI: `x = reactive(default)` + `watch_x(self,new)` вызывается сам.
- **Worker API** — async/IO без блокировки: `@work(thread=True)` + `self.call_from_thread(...)`.
- **Messages** — коммуникация виджетов без прямых ссылок: `class Selected(Message)` → `post_message` →
  ловится `on_my_widget_selected`.

## Слой 5 — Структура проекта
```
myapp/
├── app.py          App + BINDINGS + compose
├── app.tcss        всё CSS здесь
├── screens/        main.py, settings.py, detail.py
├── widgets/        header.py, table_panel.py, chart_panel.py
├── data/fetcher.py логика данных, БЕЗ UI-зависимостей
└── main.py         точка входа: 3 строки
```
Ключевое правило: **data/fetcher.py не знает о Textual вообще** — только чистые данные. Виджеты получают
данные через Messages или reactive.

## Слой 6 — Что делает TUI «правильно играбельным»
Keyboard-first (всё с клавиатуры, `BINDINGS`+`Footer`); focus management (`can_focus=True`, Tab,
`set_focus`); НЕ блокировать event loop (IO через `@work(thread=True)`/`async`); скролл по содержимому
(`ScrollableContainer`); размеры через CSS (`1fr`/`auto`, не `width=80`); `DataTable` вместо
форматированных строк; `RichLog` для стримов (`log.write_line()`, не перестраивать через `update()`).

## Тулзы разработки
```
pip install textual-dev
textual run --dev app.py    # hot-reload CSS
textual console             # debug console
textual colors              # палитра темы
textual diagnose            # инфо о терминале (цвета, Kitty, Sixel)
```
`tuilwindcss` — Tailwind-подобные CSS-классы для Textual.

**Итог:** Textual + `.tcss` + reactive + workers + DataTable/RichLog — весь стек. Остальное (plotext,
autocomplete, image) — по задаче.

---

## РЕКОНСИЛЯЦИЯ под ORION V evidence-card stream (что годится / что нет)
См. сводный анализ Claude+Codex и memory DESIGN/DEV_METHODS 2026-06-25. Кратко:
- ГОДИТСЯ: CSS-в-файл (.tcss), reactive (состояние карточки), Messages (выбор карточки→деталь),
  keyboard-first+Footer, focus management, data-слой без UI (= наши `*_evidence.py`, маршрут a),
  `textual run --dev` для подгонки вида, Sparkline/ProgressBar (trust/freshness), `Collapsible` (детали).
- НЕ НАШ ОСНОВНОЙ ПУТЬ: `DataTable`/`RichLog` как ГЛАВНАЯ поверхность — у нас карточки = кастомные
  фокусируемые `Widget` в `VerticalScroll` (decision-first, многострочные, selectable+detail), не
  таблица и не append-only лог. DataTable — только для табличной детали внутри карточки.
- ОСТОРОЖНО: плагины (plotext/image/autocomplete) = новые pip-зависимости → пересборка
  operator-console Docker-образа. Для v1 держимся ВСТРОЕННЫХ виджетов, плагины — по необходимости позже.
