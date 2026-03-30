# ARTIFACT: ORION V cockpit clickable refresh

Статус: pass
Дата: 2026-03-05
Область: `ORION V` (`F1` cockpit, clickable UX)

## Что было плохо

1. `F1` экран оставался в основном длинным статическим текстом.
2. Кликабельность была уже хорошей в overlay, status-bars и action-bar, но в самом cockpit не хватало прямых действий по месту.
3. Для ожидающего действия QIKI оператор видел текст `q confirm`, но не имел рядом с контекстом явной кликабельной кнопки `confirm/cancel`.
4. Это ухудшало главный сценарий: быстрый обзор -> переход в деталь -> подтверждение действия.

## На что опирались при правке

### Внутренний канон

- `docs/design/operator_console/CANONICAL_SPEC_ORION_QIKI.md`
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md`
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_RUN_2026-03-05.md`

### Внешние источники

1. NASA Display Standard:
   - https://www.nasa.gov/reference/appendix-f-vol-2/
   - ключевая мысль: показывать только то, что нужно для текущей задачи; не заставлять оператора ходить по лишним экранам ради базового решения.

2. NASA Crew Interfaces:
   - https://www.nasa.gov/reference/10-0-crew-interfaces-vol-2/
   - ключевая мысль: safety-critical интерфейсы должны поддерживать быстрые и точные решения без двусмысленности.

3. NASA Human Factors & Performance:
   - https://www.nasa.gov/reference/jsc-human-factors-performance/
   - ключевая мысль: task analysis и workload reduction важнее декоративного усложнения интерфейса.

4. Nielsen Norman Group, error/status guidance:
   - https://www.nngroup.com/articles/error-message-guidelines/
   - ключевая мысль: интерфейс должен не просто сообщать проблему, а помогать понять, что делать дальше.

## Что изменено

### Код

- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `src/qiki/services/operator_console/orion_v/app.py`

### Новое поведение

1. В `F1` добавлен верхний блок быстрых действий:
   - `Энергия/Power -> F2`
   - `Навигация/Navigation -> F2`
   - `Связь/Comms -> F2`
   - `Температура/Thermal -> F2`
   - `Инциденты/Incidents -> F3`

2. Эти кнопки теперь показывают текущее состояние по секциям:
   - `OK`
   - `WARN`
   - `CRIT`
   - `DEGRADED`

3. В `F1` добавлены явные кликабельные действия для QIKI:
   - `Подтвердить/Confirm QIKI`
   - `Отменить/Cancel QIKI`

4. Эти QIKI-кнопки не создают новый обходной контур.
   Они используют уже существующие безопасные пути:
   - `q confirm`
   - `q cancel`

5. В body `F1` добавлена явная discoverability-подсказка:
   - `click section -> focus detail, click QIKI -> confirm/cancel pending action`

6. В `app.py` добавлена безопасная маршрутизация новых кликов.

7. Укреплена устойчивость refresh-path:
   - `_refresh_ui()` теперь безопасно выходит, если некоторые экраны ещё не смонтированы во время раннего таймера.

## Документы обновлены

- `docs/design/operator_console/CANONICAL_SPEC_ORION_QIKI.md`
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md`
- `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_RUN_2026-03-05.md`

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

### Unit / UI

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_app_incidents.py \
  tests/unit/test_orion_v_qiki_loop.py
```

Результат:
- `exit 0`

### Новые доказательства

- `tests/unit/test_orion_v_app_incidents.py::test_cockpit_power_click_opens_f2_and_selects_power`
- `tests/unit/test_orion_v_app_incidents.py::test_cockpit_qiki_cancel_click_clears_pending_action`

## Вывод

Правка улучшила именно то, что было слабым:
- `F1` стал более task-oriented,
- переходы в detail стали прямыми,
- QIKI pending-action стал ближе к месту принятия решения,
- кликабельность усилилась без нарушения keyboard parity и без обхода operator-confirmation policy.

## Остаточный риск

- Пока ещё нет отдельного runtime-артефакта с tmux-capture именно нового cockpit quick-actions блока.
- Но unit/UI доказательство уже есть, а существующий clickable acceptance run синхронизирован с новым покрытием.
