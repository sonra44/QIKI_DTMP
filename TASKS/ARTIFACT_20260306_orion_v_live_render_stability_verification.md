# ARTIFACT: ORION V live render stability verification

Дата: 2026-03-06
Статус: PASS

## Область

Проверка живого поведения `ORION V` в `tmux` после:
- отказа от degraded path через `docker attach qiki-operator-console`,
- перехода на canonical live path `./scripts/run_orion_v_live.sh`,
- двух узких redraw-discipline slices в `src/qiki/services/operator_console/orion_v/app.py`.

## Цель

Доказать, что в реальном операторском live-path:
- fullscreen/TUI path остаётся корректным;
- command mode, replay toggle и navigation больше не провоцируют degraded redraw behavior;
- дальнейший `_refresh_ui()` triage можно остановить до появления нового runtime-symptom.

## Canonical live path

```bash
cd /home/sonra44/QIKI_DTMP
./scripts/run_orion_v_live.sh
```

## Runtime setup

- tmux session: `1`
- window: `orionverify`
- pane target: `1:3.0`
- pane id: `%28`

## Что было проверено

### Fullscreen path

Фактическое состояние pane:

```text
alternate_on=1
mouse_any_flag=1
cmd=docker
```

Это подтверждает корректный fullscreen path под `tmux` и отличает его от деградированного `docker attach` path, где ранее наблюдались `alternate_on=0` и `mouse_any=0`.

### Command mode

Проверено:
- открыть command mode через `/`;
- закрыть command mode через `Esc`.

Факт:
- command input появляется штатно;
- после `Esc` ORION возвращается в обычный режим без постоянного курсора;
- fullscreen path не распадается;
- capture-pane не показывает “грязной” шапки или повторных рамок.

### Replay flow

Проверено:
- `replay status`
- `replay on 60`
- `replay off`

Факт:
- при `replay on 60` ORION корректно показывает `F1 Кокпит [АНАЛИЗ]`;
- виден banner `РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО`;
- при `replay off` ORION чисто возвращается в live mode с сообщением `Анализ истории отключен (режим реального времени)`;
- fullscreen path сохраняется (`alternate_on=1`, `mouse_any_flag=1`).

### Navigation/selection stability

Проверено через live interaction, что после redraw cleanup:
- paging path,
- incident selection path,
- command-mode transitions,
- replay transitions

не приводят к collapse fullscreen mode и не воспроизводят attach-style redraw artifacts.

## What changed in code before this verification

В `src/qiki/services/operator_console/orion_v/app.py`:
- `_request_refresh_ui()` усилен pre-mount safety fallback;
- UI-only navigation/selection path переведены на coalesced `_request_refresh_ui()`;
- command/replay/filter UI-state transitions переведены на coalesced `_request_refresh_ui()`.

## Verification commands

### Ruff

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  ruff check src/qiki/services/operator_console/orion_v/app.py \
  tests/unit/test_orion_v_app_incidents.py \
  tests/unit/test_orion_v_status_bars.py
```

Результат:
- `All checks passed!`

### Pytest

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/unit/test_orion_v_app_incidents.py
```

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/unit/test_orion_v_status_bars.py
```

Результат:
- green

## Вывод

PASS:
- canonical live path под `tmux` подтверждён;
- текущий redraw-discipline slice operationally sufficient;
- дальше не требуется продолжать `_refresh_ui()` triage без нового runtime evidence.

Следствие:
- при следующих жалобах сначала воспроизводить только через `./scripts/run_orion_v_live.sh`;
- возвращаться к deeper render/layout triage только если снова появится реальный live symptom.
