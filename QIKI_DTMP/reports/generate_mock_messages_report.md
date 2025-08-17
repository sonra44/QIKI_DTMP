# Отчёт: proto_extensions/utils/generate_mock_messages.py

## Назначение
Утилита для генерации JSON-моков из protobuf сообщений.

## Задачи
- Создаёт `SensorReading` и сохраняет его как `sensor_reading.mock.json`.
- Создаёт `ActuatorCommand` и сохраняет его как `actuator_command.mock.json`.
- Создаёт `Proposal` с вложенной командой и сохраняет его как `proposal.mock.json`.
- При запуске обеспечивает наличие каталога `proto_extensions/mocks`.

## Комментарии
Скрипт используется вручную для подготовки тестовых данных и примеров.
