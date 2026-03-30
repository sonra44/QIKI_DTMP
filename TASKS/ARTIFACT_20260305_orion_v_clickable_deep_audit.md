# ARTIFACT: ORION V clickable deep audit

Статус: pass
Дата: 2026-03-05
Область: `ORION V` cockpit + clickable logic

## Цель

Проверить, действительно ли в текущем ORION V есть проблемы с видимостью подписей и логикой кликов, и отделить реальные дефекты от субъективного ощущения.

## Как проверяли

1. Прочитаны канонические документы:
- `docs/design/operator_console/CANONICAL_SPEC_ORION_QIKI.md`
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md`
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_RUN_2026-03-05.md`

2. Проверен текущий код:
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `src/qiki/services/operator_console/orion_v/app.py`

3. Проверены внешние ориентиры:
- NASA Display Standard
- NASA Crew Interfaces
- NASA Human Factors
- NN/g error/status guidance

4. Снят фактический headless-снимок labels в `run_test(size=(140,44))`.

## Найденные проблемы

### 1. Реальный дефект: QIKI-кнопки были слишком длинными

Симптом:
- подписи вида `Подтвердить/Confirm QIKI: <название действия>` и `Отменить/Cancel QIKI: <название действия>` были слишком длинными для компактного верхнего блока.

Почему это плохо:
- важнее действие, чем длинное повторение title;
- длинная подпись ухудшает читаемость и делает кнопку визуально тяжелее.

Что сделано:
- кнопки сокращены до коротких и понятных:
  - `QIKI подтвердить/Confirm`
  - `QIKI отменить/Cancel`
- подробность о pending-action перенесена в текстовый блок `QIKI`.

### 2. Реальный дефект: логика `Навигация -> F2` была слишком широкой

Симптом:
- старый быстрый переход на `F1` вёл только в `navigation`, хотя сам блок движения включал и навигацию, и данные стыковки.

Почему это плохо:
- оператор видел docking-related проблему, но клик вёл не в наиболее естественную цель.

Что сделано:
- добавлен отдельный переход `Стыковка/Docking -> F2`;
- теперь логика быстрее соответствует содержанию обзорного блока.

### 3. Реальный дефект: refresh-path был хрупким при раннем таймере

Симптом:
- в headless `run_test` таймер мог дёрнуть `_refresh_ui()` до полного монтирования всех экранов.

Почему это плохо:
- это давало ложные падения UI-тестов и делало поведение менее надёжным.

Что сделано:
- добавлен дополнительный `NoMatches` guard вокруг раннего refresh-path.

## Что не подтвердилось как дефект

- Сам факт наличия section quick-actions в `F1` не является ошибкой; наоборот, это улучшает операторский путь.
- Keyboard parity не нарушена: все новые клики ведут в уже существующие action-paths.
- Нового обходного QIKI-контура не создано.

## Что исправлено по итогам аудита

- `F1` теперь имеет отдельные переходы:
  - `Энергия/Power`
  - `Навигация/Navigation`
  - `Стыковка/Docking`
  - `Связь/Comms`
  - `Температура/Thermal`
  - `Инциденты/Incidents`
- QIKI pending path стал визуально компактнее и понятнее.
- Внутри `QIKI`-блока теперь явно показывается подготовленное действие.

## Проверки

### Lint

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  ruff check \
  src/qiki/services/operator_console/orion_v/screens/cockpit.py \
  src/qiki/services/operator_console/orion_v/app.py \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_app_incidents.py
```

Результат:
- `All checks passed!`

### UI / unit slice

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_app_incidents.py \
  tests/unit/test_orion_v_status_bars.py
```

Результат:
- `exit 0`

### Новые прямые доказательства

- `test_cockpit_docking_click_opens_f2_and_selects_docking`
- `test_cockpit_qiki_cancel_click_clears_pending_action`
- `test_cockpit_renders_confirmable_qiki_action`

## Итог аудита

Вывод: замечание пользователя было по делу.

Подтверждено:
1. часть подписей действительно была перегружена;
2. часть логики быстрого перехода была слишком грубой;
3. после правок cockpit стал логичнее и чище.

## Остаточный риск

- Остаточный риск по `F1 quick-actions` закрыт отдельным live runtime-proof:
  - `bash scripts/prove_orion_v_f1_quick_actions.sh`
  - `TASKS/ARTIFACT_20260305_orion_v_f1_quick_actions_runtime_proof.md`
- Необязательный будущий шаг: если потребуется именно визуальная pane-картинка в tmux для релизного пакета, её можно снять дополнительно, но для функционального доказательства это больше не блокер.
