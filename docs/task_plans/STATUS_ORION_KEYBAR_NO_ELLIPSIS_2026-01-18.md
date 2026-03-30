## STATUS (2026-01-18) — ORION: Keybar без «среза» хоткеев

### Симптом

Внизу экрана (keybar) пункты меню резались «посередине» и выглядели сломанно, например:

- `Ctrl+N Sensors/Сенс…`
- `[F8 Mi…`

Это ухудшало читабельность в tmux-сплитах и создавало ощущение «кривого» UI.

### Решение (без моков / без v2 / без дублей)

1) Keybar перестроен на tmux-safe формат:
- разделители `·` вместо длинного списка в `[]`;
- активный экран помечается префиксом `▶`;
- `F9 Help/Помощь` и `F10 Quit/Выход` принудительно остаются видимыми:
  при нехватке ширины «урезаются» менее важные пункты меню, а не «ломаются» токены.

2) Sidebar help-строки в узкой плотности сокращены, чтобы не превращаться в `…`.

### Файлы

- `src/qiki/services/operator_console/main_orion.py`:
  - `OrionKeybar.render` — новый алгоритм fit (без разрыва хоткеев, F9/F10 всегда видимы)
  - `OrionSidebar.render` — короткие help-строки для `tiny/narrow`
- `docs/design/operator_console/ORION_OS_VALIDATION_RUN_2026-01-18.md` — добавлена запись о фиксе keybar.

### Проверка (Docker-first)

Команды:

- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build --force-recreate operator-console`
- `docker attach qiki-operator-console`

Ожидаемо:

- keybar снизу не содержит «обрезанных» пунктов меню;
- присутствуют `F9 Help/Помощь` и `F10 Quit/Выход`;
- активный экран отмечен `▶`.

