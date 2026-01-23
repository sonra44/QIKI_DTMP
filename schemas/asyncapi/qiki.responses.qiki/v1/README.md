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

- `proposed_actions` — типизированные (но в MVP обычно пустые).
- При `ok=false` поле `error` MUST быть задано.

