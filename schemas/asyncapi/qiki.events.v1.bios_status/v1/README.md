# Контракт события: `qiki.events.v1.bios_status` (v1)

## Назначение

`qiki.events.v1.bios_status` — периодическое событие от `q-bios-service`, которое сообщает:
- результаты POST по устройствам (`post_results`);
- вычисленное агрегированное состояние (`all_systems_go`);
- идентификаторы/метаданные сообщения (версия схемы, источник, subject, timestamp).

Это **единственный канонический** subject для статуса BIOS в v1. Отдельные subject’ы вида `hardware_ready` / `hardware_error`
в v1 **не используются** (зарезервировано для возможного будущего major/extension).

## Версионирование

- `event_schema_version` — версия payload-схемы (integer).
- Для текущей версии: `event_schema_version == 1`.
- При несовместимых изменениях вводится новая версия (`event_schema_version: 2`) и/или новый subject.

## Формат payload (v1)

См. JSON Schema: `payload.schema.json`.

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

