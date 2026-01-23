# STATUS: ORION Sensors — автофокус и «видимый выбор» (2026-01-18)

## Проблема
В tmux/узких размерах казалось, что «изменений нет», потому что при переходе на экран **Sensors/Сенсоры**:
- фокус часто оставался в sidebar/командной строке,
- Inspector мог показывать только общий Summary (без выбранной строки),
- оператору приходилось вручную делать `Tab` и только потом стрелки.

Это ухудшало UX и создавало ощущение, что новые изменения (компактная таблица, стабильный курсор) «не работают».

## Решение
Сделали переход на экран `sensors` **самодостаточным**:
- при `action_show_screen("sensors")` вызываем `_render_sensors_table()`,
- после layout refresh (`call_after_refresh`) ставим фокус на `#sensors-table`,
- обеспечиваем первичное выделение (курсор на первой строке, если он ещё не задан),
- вследствие `RowHighlighted` Inspector получает `Selection/Выбор` автоматически.

### Инварианты
- no-mocks: отсутствие данных остаётся честным `N/A/—`.
- no-v2 / no-duplicates: без новых subject’ов/протоколов.

## Изменённые файлы
- `src/qiki/services/operator_console/main_orion.py` — `OrionApp/action_show_screen`: добавили `sensors` в список экранов + post-refresh focus.

## Проверка (Docker-first)
- Тесты: `docker compose -f docker-compose.phase1.yml run --rm --no-deps qiki-dev pytest -q src/qiki/services/operator_console/tests`
- Рантайм:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
  - `docker attach qiki-operator-console`
  - нажать `Ctrl+N` → **видно экран Sensors**, фокус/выбор активен, Inspector показывает `Selection/Выбор` без `Tab`.

## Итог
Экран Sensors теперь «сам объясняет себя»: после входа оператор сразу видит, что выделено и что это за строка (через Inspector).