# STATUS: ORION — строка ввода (placeholder) перестал «влезать» (2026-01-18)

## Симптом
Внизу (строка команды) длинный placeholder перестал помещаться и выглядел «обрубленным»/с некрасивым хвостом.

## Причина
`OrionApp._update_command_placeholder()` задавал фиксированную «простыню» команд независимо от ширины терминала и density.
Textual/Input не переносит placeholder построчно, поэтому он резался произвольно.

## Решение
Сделали placeholder:
- адаптивным по `density` (`tiny/narrow/normal/wide`) — на узких режимах показываем меньше команд;
- заранее обрезаем по ширине (pre-ellipsize), чтобы строка завершалась аккуратно `…`, а не «висящим» `|`.

Дополнительно: `_apply_responsive_chrome()` теперь вызывает `_update_command_placeholder()`, чтобы placeholder обновлялся при ресайзе tmux.

## Проверка
- Docker tests: `pytest -q src/qiki/services/operator_console/tests` — зелёный.
- В рантайме placeholder выглядит так:
  - начинается с `command/команда>`
  - на узком размере становится короче
  - при нехватке места заканчивается `…`.

## Изменённый файл
- `src/qiki/services/operator_console/main_orion.py` (`_update_command_placeholder`, `_apply_responsive_chrome`)