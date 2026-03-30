# Политика эволюции контрактов (Proto/gRPC, NATS/AsyncAPI)

## Принципы Protobuf/gRPC
- Никогда не менять номера полей, имена можно резервировать: `reserved <tags>; reserved "<names>";`.
- Добавления только совместимые (optional/repeated) с новыми тегами; не делать поля обязательными задним числом.
- Несовместимые изменения (тип, смысл) — только через новую схему/версию.
- Для взаимоисключающих вариантов использовать `oneof`.
- Отличать `unset` от `zero` через wrapper-типы (`google.protobuf.*Value`) при необходимости.
- Время — `google.protobuf.Timestamp`; длительности — `google.protobuf.Duration`.

## Версионирование
- Встроенная версия: `schema_version: uint32` в сообщениях (`RadarFrame/Track`).
- Темы NATS: версионированные subject’ы: `qiki.radar.v1.frames`, `qiki.radar.v1.tracks`, `qiki.alerts.v1`.
- Переход на новый major: новые subject’ы `v2.*`, параллельный транслятор v1↔v2 до завершения миграции.

## NATS/JetStream
- Дедупликация: на уровне Stream задать `duplicate_window: 2m` (пример), при публикации — устанавливать заголовок `Nats-Msg-Id`.
- Управление потреблением: Pull‑consumers, `ack_wait`, `max_ack_pending`; для упорядоченных потребителей — Flow Control и Idle Heartbeats.
- Хранение: `storage=file`, ограничители `max_bytes/max_age`, политика `discard=old`.

## Buf (lint/breaking)
- В CI запускать `buf lint` и `buf breaking` против основной ветки.
- Хранить конфигурацию `buf.yaml` с выбранными правилами lint/breaking.

## AsyncAPI (NATS)
- Генерировать и публиковать документацию AsyncAPI для topics (артефакт CI).
- Хранить схемы в `schemas/asyncapi/<subject>/vN/`.

## Тестирование контрактов
- Snapshot‑тесты сериализации/десериализации (golden messages).
- CDC (consumer‑driven contracts) для NATS: примеры сообщений → валидатор схем.
- Интеграционные тесты: публикация/потребление в docker‑окружении с JetStream.

