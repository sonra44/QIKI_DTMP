# Контракт (NATS): `qiki.responses.qiki` — `QikiChatResponse.v1`

## Назначение

`qiki.responses.qiki` — ответы QIKI на намерения оператора из `qiki.intents`.

Корреляция: `request_id` — join key между запросом и ответом.

## Версионирование

- `version` — версия схемы (integer).
- Для текущей версии: `version == 1`.

## Канон схемы

- JSON Schema: `payload.schema.json`
- Модель кода (source of truth): `src/qiki/shared/models/qiki_chat.py` (`QikiChatResponseV1`)

## Правила MVP

- `proposed_actions` — типизированные.
  - `NATS_COMMAND` — подтверждаемая отправка команды на существующий bus.
  - `ORION_PROCEDURE` — подтверждаемый запуск уже существующей процедуры в ORION V без нового transport.
- При `ok=false` поле `error` MUST быть задано.
- `legality` — продуктовый статус допустимости действия (`allowed|blocked|deferred|unsafe`).
- `trust_signals` — список явных сигналов доверия к данным/политике, релевантных ответу.
- `consequence` — подтверждение, что произошло после ответа (`confirmed|not_sent|pending|failed`).
