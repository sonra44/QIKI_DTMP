# ARTIFACT: ORION V menu semantics audit — F4 Console

Дата: 2026-03-06
Статус: complete

## Проблема

Пользовательский feedback был не про косметику, а про логику меню:
- в интерфейсе не должно быть бесполезной информации;
- должно быть ясно, что показывает каждый экран и почему;
- `F2` не должен обещать маршрут в экран, который по факту не помогает оператору.

Конкретный дефект:
- `F4` был назван `Сырой поток`,
- в коде он показывал JSON-снимок runtime-state,
- но в ожидании оператора это читалось как экран потока сообщений/логов.

Это создавало ложное обещание:
- пользователь искал историю сообщений,
- а получал сырую диагностическую структуру;
- при отсутствии полезного содержания экран воспринимался как "просто пустой поток логов".

## Почему это архитектурный дефект

Канон ORION уже фиксирует:
- `Events/События` = высокочастотные события и инциденты;
- `Console/Консоль` = спокойная история операторского диалога и ответов системы.

Значит проблема была не в том, что данных мало, а в том, что экран `F4` нарушал собственную семантику продукта.

## Что изменено

### 1. F4 переопределён как Console

Файлы:
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/screens/raw.py`
- `src/qiki/services/operator_console/orion_v/widgets/action_bar.py`

Сделано:
- `F4` переименован из `Сырой поток/Raw` в `Консоль/Console`;
- `LEVEL_META` и hotkey labels синхронизированы;
- экран теперь показывает историю операторских сообщений, QIKI-ответов, подтверждений и ошибок.

### 2. Help-strip стал источником console history

Файл:
- `src/qiki/services/operator_console/orion_v/app.py`

Сделано:
- `_set_help_text()` теперь не только обновляет текущую строку помощи,
  но и пишет нормализованную запись в bounded console history;
- одинаковые подряд сообщения не дублируются.

### 3. F4 теперь показывает операторски полезный контекст

Файл:
- `src/qiki/services/operator_console/orion_v/app.py`

Сделано:
- `F4` рендерит последние операторские сообщения;
- ниже даёт короткий context block:
  - активный экран;
  - число событий на странице;
  - выбранная подсистема;
  - выбранный инцидент.

### 4. F2 больше не врёт про маршрут

Файл:
- `src/qiki/services/operator_console/orion_v/screens/systems.py`

Сделано:
- строка `Подробнее: F3/F4` заменена на честную:
  - `Подробнее: F3 | История действий: F4`

## Результат

Теперь логика экранов стала честнее:
- `F2` = системная сводка;
- `F3` = события/инциденты/глубокий анализ;
- `F4` = история операторских действий и ответов системы.

Это ближе к реальному операторскому использованию и убирает один из главных источников бесполезной инфы.

## Проверки

### Ruff

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/operator_console/orion_v/app.py \
  src/qiki/services/operator_console/orion_v/screens/raw.py \
  src/qiki/services/operator_console/orion_v/screens/systems.py \
  src/qiki/services/operator_console/orion_v/widgets/action_bar.py \
  tests/unit/test_orion_v_action_bar.py \
  tests/unit/test_orion_v_raw.py \
  tests/unit/test_orion_v_app_incidents.py
```

Результат:
- `All checks passed!`

### Pytest

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_action_bar.py \
  tests/unit/test_orion_v_raw.py \
  tests/unit/test_orion_v_app_incidents.py
```

Результат:
- зелёный прогон

## Честный остаток

После этого прохода самая большая смысловая перегрузка остаётся не в меню, а внутри `F1`:
- блок `QIKI`
- блок `Движение и навигация`

Следующий логический проход по интерфейсу должен идти туда.
