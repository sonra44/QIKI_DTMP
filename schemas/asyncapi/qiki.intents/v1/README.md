# Контракт (NATS): `qiki.intents` — `QikiChatRequest.v1`

## Назначение

`qiki.intents` — канал, по которому ORION публикует намерение оператора (free text) вместе с UI/system контекстом.

## Версионирование

- `version` — версия схемы (integer).
- Для текущей версии: `version == 1`.

## Канон схемы

- JSON Schema: `payload.schema.json`
- Модель кода (source of truth): `src/qiki/shared/models/qiki_chat.py` (`QikiChatRequestV1`)

