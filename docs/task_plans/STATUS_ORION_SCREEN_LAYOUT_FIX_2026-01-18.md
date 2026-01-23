# STATUS: ORION — выравнивание раскладки экранов (F3/F4 и др.) (2026-01-18)

## Симптом
- `F3 Events/События` выглядит «органично»: таблица занимает центр, снизу нормальный `Output/Вывод` + строка команды.
- `F4 Console/Консоль` (и часть других экранов) выглядели «сломано»:
  - основной контент мог рендериться **ниже** `bottom-bar` (строка команд/кейбар),
  - визуально казалось, что «центр пустой», а снизу «огромная панель»,
  - одинаковая chrome-рамка (sidebar/inspector/bottom) применялась неравномерно.

## Причина
В `OrionApp.compose()` часть контейнеров `screen-*` была размещена **вне** `#orion-workspace`.
В результате:
- одни экраны делили единый layout (sidebar/inspector/output),
- другие рендерились отдельным блоком ниже и получали другой поток/геометрию.

## Исправление
- Все `screen-*` контейнеры перенесены внутрь `#orion-workspace`.
- `bottom-bar` вынесен из `#orion-workspace` в `#orion-root` и оставлен `dock: bottom`, чтобы он:
  - всегда был видим,
  - не «конкурировал» по раскладке со screen-контентом,
  - одинаково работал для всех экранов.

## Инварианты
- no-mocks: данные не подменяем; если данных нет — `N/A/—`.
- no-v2 / no-duplicates: не создаём новые subject’ы/протоколы.

## Проверка (Docker-first)
- Тесты: `docker compose -f docker-compose.phase1.yml run --rm --no-deps qiki-dev pytest -q src/qiki/services/operator_console/tests`
- Визуально (tmux):
  1) `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
  2) `docker attach qiki-operator-console`
  3) `F3` и `F4`: основной контент всегда в центре, `Output/Вывод` и строка команды всегда внизу, без «провала» экрана вниз.

## Изменённые файлы
- `src/qiki/services/operator_console/main_orion.py` (`OrionApp.compose`)