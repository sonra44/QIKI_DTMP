# ORION ↔ QIKI: отчёт по PR1–PR7

Дата: 2026-01-08  
Контекст: “proposals-only” интеграция ORION↔QCore↔QIKI через NATS, с подготовкой консоли оператора к подключению LLM.

## Сводка (что стало возможно)

- ORION отправляет операторские intents (`q:` / `//`) как структурированные сообщения `IntentV1`.
- QCore (без OpenAI) отвечает структурированными `ProposalsBatchV1` (заглушки), ORION отображает их отдельно от инцидентов.
- NeuralEngine получил опциональную OpenAI-реализацию (proposals-only, actions пустые) с безопасным fallback.
- Улучшено качество данных: UI меньше “таблиц из N/A”, snapshot для QIKI не содержит строковых “N/A”, а несёт структурированный статус.
- Введён системный режим `Factory/Mission` (истина в QCore), который влияет на “строгость/шум” proposals.

## PR1 — Schemas & subjects (Stage A)

**Ветка:** `feature/orion-qiki-schemas-subjects-a`  
**Коммит:** `55efea1`  
**Цель:** зафиксировать канонические subjects и схемы сообщений для ORION↔QIKI.

**Изменения:**
- Добавлены subjects:
  - `qiki.intent.v1`
  - `qiki.proposals.v1`
  - (alias) `QIKI_INTENTS` → `QIKI_INTENT_V1`
- Добавлены Pydantic модели:
  - `IntentV1` (включает `environment_mode`)
  - `ProposalV1` (инвариант: `proposed_actions=[]` на этом этапе)
  - `ProposalsBatchV1`

**Ключевые файлы:**
- `src/qiki/shared/nats_subjects.py`
- `src/qiki/shared/models/orion_qiki_protocol.py`
- `tests/unit/test_orion_qiki_protocol_v1.py`

**Как проверить:**
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_qiki_protocol_v1.py`

## PR2 — ORION публикует Intent (Stage B)

**Ветка:** `feature/orion-publish-intent-v1-b`  
**Коммит:** `be099c5`  
**Цель:** при вводе `q:`/`//` ORION публикует `IntentV1` в NATS, не блокируя UI.

**Изменения:**
- Добавлена маршрутизация ввода:
  - `q:`/`//` → intent в `qiki.intent.v1`
  - shell-команды не уходят в QIKI
- intent включает минимальный snapshot (`vitals`, `active_screen`, `selection`, `incidents_top`)
- публикация “fire-and-forget” (ORION не ждёт ответа синхронно)

**Ключевые файлы:**
- `src/qiki/services/operator_console/main_orion.py`
- `src/qiki/services/operator_console/tests/test_qiki_routing.py`

**Как проверить:**
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_qiki_routing.py`

## PR3 — QCore принимает intent и отвечает stub proposals (Stage C)

**Ветка:** `feature/qcore-intent-stub-proposals-c`  
**Коммиты:** `07492fb`, `dd4d58b`  
**Цель:** QCore начинает “жить” без OpenAI: принимает `IntentV1`, публикует `ProposalsBatchV1` заглушки в `qiki.proposals.v1`.

**Изменения:**
- Добавлен `intent_bridge`:
  - подписка на `qiki.intent.v1`
  - валидация `IntentV1`
  - публикация `ProposalsBatchV1` (1–3 предложения)
  - при невалидном intent публикуется `invalid-intent` без утечек сырого payload
- Фикс docker: в контейнере может не быть `NATS_URL` → используется fallback серверов.

**Ключевые файлы:**
- `src/qiki/services/q_core_agent/intent_bridge.py`
- `src/qiki/services/q_core_agent/main.py` (авто-старт bridge)
- `src/qiki/services/q_core_agent/tests/test_intent_bridge.py`

**Как проверить:**
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_core_agent/tests/test_intent_bridge.py`

## PR4 — ORION отображает proposals (Stage D)

**Ветка:** `feature/orion-display-proposals-d`  
**Коммит:** `cd34190`  
**Цель:** оператор видит ответы QIKI как управляемые объекты, отдельно от инцидентов/событий.

**Изменения:**
- ORION подписывается на `qiki.proposals.v1`
- Каждое предложение пишет короткую строку в calm strip: `QIKI: <title>`
- Добавлен экран `Proposals/Предложения` (таблица + Inspector)

**Ключевые файлы:**
- `src/qiki/services/operator_console/clients/nats_client.py` (subscribe proposals)
- `src/qiki/services/operator_console/main_orion.py` (store + экран)
- `src/qiki/services/operator_console/tests/test_qiki_proposals_display.py`

**Как проверить:**
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_qiki_proposals_display.py`

## PR5 — OpenAI в NeuralEngine (Stage E)

**Ветка:** `feature/neuralengine-openai-proposals-pr5`  
**Коммит:** `ca9e1a8`  
**Статус:** локальная ветка (не в `origin/*` на момент отчёта).  
**Цель:** заменить заглушку NeuralEngine на генерацию proposals через OpenAI, но строго **proposals-only**.

**Изменения:**
- Реализован минимальный клиент Responses API (HTTP) с:
  - JSON-only output (json_schema strict)
  - retries: backoff+jitter на 429/5xx
  - hard-cap по попыткам
- Fallback: при отсутствии ключа/ошибке → 1 stub proposal “LLM unavailable…”
- Инвариант: `proposed_actions=[]` всегда

**Ключевые файлы:**
- `src/qiki/services/q_core_agent/core/openai_responses_client.py`
- `src/qiki/services/q_core_agent/core/neural_engine.py`
- `src/qiki/services/q_core_agent/tests/test_agent.py` (mock OpenAI, без сети)

**ENV (не в git):**
- `OPENAI_API_KEY` (обязательно)
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `OPENAI_TIMEOUT_S`, `OPENAI_MAX_OUTPUT_TOKENS`, `OPENAI_MAX_RETRIES`, `OPENAI_TEMPERATURE`, `OPENAI_BASE_URL`

**Как проверить:**
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_core_agent/tests/test_agent.py`

## PR6 — N/A и качество данных (Stage F)

**Ветка:** `feature/orion-na-quality-pr6`  
**Коммит:** `1a46f7c`  
**Статус:** локальная ветка (не в `origin/*` на момент отчёта).  
**Цель:** убрать “таблицы из N/A” и улучшить сигнал для QIKI без выдумывания данных.

**Изменения (ORION):**
- `N/A/НД` закреплено как инвариант отображения (`I18N.NA`).
- Пустые таблицы показывают “No incidents/No tracks/…” вместо заполнения колонок N/A.
- Для QIKI snapshot:
  - vitals несут структурированный статус поля (`ok/value` или `na/reason`) вместо строк “N/A”
  - добавлен `snapshot_min.telemetry.{freshness, age_s}`
- Inspector показывает причину N/A когда можно вывести (Not wired / Stale / Unsupported).

**Ключевые файлы:**
- `src/qiki/services/operator_console/ui/i18n.py`
- `src/qiki/services/operator_console/main_orion.py`

**Как проверить:**
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests`

## PR7 — Режимы и gating (Stage G)

**Ветка:** `feature/env-modes-gating-pr7`  
**Коммит:** `a26f7d7` (в ветке есть merge-база `8a98cc1`)  
**Цель:** реализовать `Factory/Mission` как системное состояние (истина в QCore) и включить его в политику.

**Изменения:**
- Добавлены subjects:
  - `qiki.environment.v1` (snapshot от QCore)
  - `qiki.environment.v1.set` (запрос смены режима)
- Добавлены схемы:
  - `EnvironmentSnapshotV1`
  - `EnvironmentSetV1`
- QCore:
  - публикует snapshot режима на старте и при изменении
  - принимает set-запросы
  - gating proposals по режиму:
    - `FACTORY` → подробнее/больше предложений (`verbosity=high`)
    - `MISSION` → меньше “шума” (`verbosity=low`)
- ORION:
  - показывает режим в header
  - подписывается на `qiki.environment.v1`
  - команды `mode/режим`, `mode mission/режим миссия`, `mode factory/режим завод`
  - intent использует режим из QCore (если snapshot уже получен), иначе fallback env var

**Ключевые файлы:**
- `src/qiki/shared/nats_subjects.py`
- `src/qiki/shared/models/orion_qiki_protocol.py`
- `src/qiki/services/q_core_agent/intent_bridge.py`
- `src/qiki/services/operator_console/main_orion.py`
- `src/qiki/services/operator_console/clients/nats_client.py`
- Док: `docs/design/operator_console/ORION_QIKI_ENV_MODES_PR7.md`

**Как проверить (важно запускать по подсистемам):**
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_core_agent/tests`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_qiki_protocol_v1.py`

## Примечания по порядку мержа

Рекомендуемый порядок в master:
1) PR1 → PR2 → PR3 → PR4 (база взаимодействия ORION↔QCore)  
2) PR6 (качество данных ORION)  
3) PR7 (режимы/gating)  
4) PR5 (OpenAI в NeuralEngine, опционально — после стабилизации)

