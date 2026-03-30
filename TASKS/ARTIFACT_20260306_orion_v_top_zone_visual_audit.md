# Артефакт: глубокий аудит верхней зоны ORION V

Дата: 2026-03-06
Статус: complete

## Что было плохо

1. Верхняя зона была собрана из нескольких полос без единого языка названий.
2. `ACTIONS` и `SKELETON/СКЕЛЕТ` звучали как внутренние технические метки, а не как операторские секции.
3. Header был одной длинной строкой без явной иерархии.
4. Быстрые действия в `F1` находились вверху экрана, но сам блок не был назван как отдельная операторская зона.
5. Часть кнопок была перегружена подписями и визуально спорила с телом cockpit.

## Что решено исправить

1. Сделать все верхние полосы именованными.
2. Усилить identity header как главной строки состояния.
3. Сжать labels в action bar и status bars.
4. Дать `F1` quick-actions собственный border title и subtitle.
5. Доказать изменения через targeted UI tests.

## Что изменено фактически

1. Header перестроен в явный мостик состояния:
   - отдельная identity-строка `ORION V / OPERATOR BRIDGE`,
   - отдельная строка секции, профиля UI и счётчика событий,
   - отдельная строка состояния шины и NATS URL.
2. Верхние полосы получили предметные названия:
   - `МОСТИК/BRIDGE STATUS`
   - `НАВИГАЦИЯ/NAVIGATION`
   - `КЛЮЧЕВЫЕ СИСТЕМЫ/CORE SYSTEMS`
   - `ТРЕВОГИ/ALERTS`
   - `КОМАНДНАЯ СТРОКА/COMMAND LINE`
   - `БЫСТРЫЕ ДЕЙСТВИЯ/QUICK ACTIONS`
3. Labels action bar сокращены до коротких операторских форм.
4. Status bars больше не называются `SKELETON/СКЕЛЕТ`; это теперь именованная зона системного обзора.
5. Quick-actions в `F1` получили собственный title/subtitle и перестали выглядеть как безымянный верхний ряд.

## Доказательства

### Targeted checks

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/app.py src/qiki/services/operator_console/orion_v/widgets/header.py src/qiki/services/operator_console/orion_v/widgets/action_bar.py src/qiki/services/operator_console/orion_v/widgets/status_bars.py src/qiki/services/operator_console/orion_v/screens/cockpit.py tests/unit/test_orion_v_header.py tests/unit/test_orion_v_status_bars.py tests/unit/test_orion_v_app_incidents.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_header.py tests/unit/test_orion_v_status_bars.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py`

### Runtime proof

- `bash scripts/prove_orion_v_top_zone.sh`

Фактический результат:

```text
OK: orion_v_top_zone_smoke
HEADER_TITLE=МОСТИК/BRIDGE STATUS
ACTIONS_TITLE=НАВИГАЦИЯ/NAVIGATION
BARS_TITLE=КЛЮЧЕВЫЕ СИСТЕМЫ/CORE SYSTEMS
OVERLAY_TITLE=ТРЕВОГИ/ALERTS
COMMAND_TITLE=КОМАНДНАЯ СТРОКА/COMMAND LINE
COCKPIT_ACTIONS_TITLE=БЫСТРЫЕ ДЕЙСТВИЯ/QUICK ACTIONS
ACTION_F1=F1 Мостик
ACTION_F6=F6 Журнал
```

## Внешние источники

- Textual CSS guide: https://textual.textualize.io/guide/CSS/
- Textual actions guide: https://textual.textualize.io/guide/actions/
- Textual testing guide: https://textual.textualize.io/guide/testing/

## Ожидаемый результат

1. Верхняя зона читается как единый мостик оператора.
2. У каждой полосы есть предметное имя.
3. Кликабельность остаётся прежней, но визуальная иерархия становится чище.
