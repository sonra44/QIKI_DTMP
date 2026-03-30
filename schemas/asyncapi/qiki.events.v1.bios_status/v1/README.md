# Контракт события: `qiki.events.v1.bios_status` (v1)

## Назначение

`qiki.events.v1.bios_status` — периодическое событие от `q-bios-service`, которое сообщает:
- результаты POST по устройствам (`post_results`);
- вычисленное агрегированное состояние (`all_systems_go`);
- идентификаторы/метаданные сообщения (версия схемы, источник, subject, timestamp).

Роль сервиса: `q-bios-service` является **support-tier derived BIOS/status layer**.
Он собирает производный status payload из `bot_config.json` и health-check `q-sim-service`, но
не становится owner physical truth и не становится owner intents/policy.

Это **единственный канонический** subject для статуса BIOS в v1. Отдельные subject’ы вида `hardware_ready` / `hardware_error`
в v1 **не используются** (зарезервировано для возможного будущего major/extension).

Канонический v1 subject фиксирован как `qiki.events.v1.bios_status`. Переменная окружения `NATS_EVENT_SUBJECT`
может быть переопределена только для non-canonical/dev wiring; такие override не относятся к данному AsyncAPI контракту.

## Версионирование

- `event_schema_version` — версия payload-схемы (integer).
- Для текущей версии: `event_schema_version == 1`.
- При несовместимых изменениях вводится новая версия (`event_schema_version: 2`) и/или новый subject.

## Формат payload (v1)

См. JSON Schema: `payload.schema.json`.

### Runtime behavior, относящийся к контракту

- При `BIOS_PUBLISH_ENABLED=1` сервис публикует payload с интервалом `BIOS_PUBLISH_INTERVAL_SEC` (по умолчанию `5.0` сек).
- Тот же payload-формат используется и в HTTP `GET /bios/status`.
- `POST /bios/reload` в MVP не вводит новую семантику события и не меняет ownership: он только сбрасывает кэш последнего derived payload, после чего следующий read/publish пересчитывает статус из текущего `BOT_CONFIG_PATH`.

### Ключевые правила для потребителей

- Потребитель **MUST** уметь обработать поля из схемы v1.
- Потребитель **MUST** игнорировать неизвестные поля (forward compatible).
- `status` в `post_results[*]` — числовой enum:
  - `0` = UNKNOWN
  - `1` = OK
  - `2` = DEGRADED
  - `3` = ERROR

## Пример сообщения (минимально полезный)

```json
{
  "event_schema_version": 1,
  "source": "q-bios-service",
  "subject": "qiki.events.v1.bios_status",
  "timestamp": "2026-01-23T00:00:00+00:00",
  "bios_version": "virtual_bios_mvp",
  "firmware_version": "virtual_bios_mvp",
  "hardware_profile_hash": "sha256:...",
  "all_systems_go": false,
  "post_results": [
    {
      "device_id": "motor_left",
      "device_name": "wheel_motor",
      "status": 1,
      "status_message": "OK"
    }
  ]
}
```
