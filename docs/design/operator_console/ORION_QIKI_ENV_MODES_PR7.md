# PR7 — Factory/Mission режимы и gating (ORION ↔ QCore ↔ QIKI)

## Цель

Сделать `Factory/Mission` системным состоянием (истина в QCore), чтобы:

- ORION показывал текущий режим в header.
- Один переключатель режима влиял на поведение QIKI (формат/“строгость”/шум) при генерации proposals.
- Режим попадал в политику взаимодействия, но без внедрения OpenAI (proposals-only).

## NATS subjects (канал протокола)

Файл: `src/qiki/shared/nats_subjects.py`

- `qiki.intent.v1` — Intent от ORION к QCore/QIKI.
- `qiki.proposals.v1` — ProposalsBatch от QCore/QIKI к ORION.
- `qiki.environment.v1` — EnvironmentSnapshot (истина от QCore наружу).
- `qiki.environment.v1.set` — запрос смены режима (от ORION к QCore).

## Схемы сообщений

Файл: `src/qiki/shared/models/orion_qiki_protocol.py`

- `EnvironmentSnapshotV1`: `{version=1, ts, environment_mode, source}`
- `EnvironmentSetV1`: `{version=1, ts, environment_mode, requested_by?}`

Тесты схем: `tests/unit/test_orion_qiki_protocol_v1.py`

## QCore: источник истины для environment_mode

Файл: `src/qiki/services/q_core_agent/intent_bridge.py`

Поведение:

1. На старте выбирается текущий режим:
   - `QCORE_ENVIRONMENT_MODE=MISSION` → `MISSION`
   - иначе → `FACTORY`
2. На старте публикуется `EnvironmentSnapshotV1` в `qiki.environment.v1`.
3. QCore слушает:
   - `qiki.environment.v1.set` → обновляет режим и публикует новый snapshot.
   - `qiki.intent.v1` → валидирует `IntentV1`, при необходимости синхронизирует режим по `intent.environment_mode` (как hint), публикует snapshot (если режим изменился), затем публикует proposals.

## Gating proposals по режиму

Файл: `src/qiki/services/q_core_agent/intent_bridge.py`

`build_stub_proposals(..., environment_mode=...)`:

- `FACTORY`:
  - 2–3 предложения, более подробные justification.
  - `metadata.verbosity="high"`.
- `MISSION`:
  - 1–2 предложения, justification короче (“меньше шума”).
  - `metadata.verbosity="low"`.

Инвариант: `proposed_actions=[]` всегда (proposals-only).

Тесты: `src/qiki/services/q_core_agent/tests/test_intent_bridge.py`

## ORION: отображение режима и запрос смены

### Header

Файл: `src/qiki/services/operator_console/main_orion.py`

- Header получает поле `mode` и отображает его в первой ячейке вместе со статусом связи.
- Обновление режима делается даже если телеметрия ещё не пришла.

### Подписка на режим

Файл: `src/qiki/services/operator_console/clients/nats_client.py`

- Добавлена подписка `subscribe_qiki_environment(...)`.

Файл: `src/qiki/services/operator_console/main_orion.py`

- ORION подписывается на environment snapshot в `_init_nats()`.
- `handle_environment_data(...)` валидирует `EnvironmentSnapshotV1`, обновляет локальное состояние и пишет факт в calm strip.

### Команды оператора

Файл: `src/qiki/services/operator_console/main_orion.py`

- `mode/режим` — показать текущий режим (как его знает ORION по QCore snapshot).
- `mode mission/режим миссия` — опубликовать `EnvironmentSetV1` в `qiki.environment.v1.set`.
- `mode factory/режим завод` — аналогично для Factory.

Тест: `src/qiki/services/operator_console/tests/test_environment_mode.py`

### Intent использует режим из QCore (если есть)

При отправке `q:`/`//`:

- Если ORION уже получил `EnvironmentSnapshotV1`, то `IntentV1.environment_mode` берётся из QCore (истина).
- Иначе используется fallback `OPERATOR_CONSOLE_ENVIRONMENT_MODE`.

## Как проверить (Docker-first)

1. Прогнать тесты (важно: запускать по подсистемам, чтобы подхватился `pytest.ini` ORION):

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_core_agent/tests
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_qiki_protocol_v1.py
```

2. Запустить Phase1 + ORION:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up operator-console
```

3. В ORION:

- `mode` → увидите текущий режим (если QCore уже опубликовал snapshot).
- `mode mission` → QCore должен опубликовать новый snapshot; в header сменится режим.
- `q: scan 360` → получите proposals; в `MISSION` они должны быть короче и их меньше.

