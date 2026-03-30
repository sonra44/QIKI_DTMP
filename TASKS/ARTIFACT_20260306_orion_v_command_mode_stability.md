# ARTIFACT: ORION V command mode stability

Дата: 2026-03-06
Статус: PASS

## Что изменено

В ORION V убран постоянный видимый `Input` из обычного режима.

Новый контракт:
- обычный режим = без постоянного курсора;
- командный ввод открывается только по требованию;
- открыть можно клавишами `:` или `/`, либо кнопкой `Открыть ввод/Open command`;
- `Esc` закрывает ввод и возвращает экран в спокойный режим.

## Зачем

Целью было убрать:
- постоянный мигающий курсор,
- визуальный шум от input-centric режима,
- лишний фокус в обычном операторском состоянии.

## Проверки

### Ruff

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  ruff check src/qiki/services/operator_console/orion_v/app.py \
  tests/unit/test_orion_v_app_incidents.py \
  tools/orion_v_command_mode_smoke.py
```

### Pytest

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/unit/test_orion_v_app_incidents.py
```

### Runtime proof

```bash
bash scripts/prove_orion_v_command_mode.sh
```

Факт:

```text
OK: orion_v_command_mode_smoke
DEFAULT_MODE=no_persistent_input
COMMAND_MODE=open_on_demand
```
