# Отчёт по файлу `proposal.proto`

## Вход и цель
- [Факт] Анализ `protos/proposal.proto`.
- [Факт] Цель: изучение структуры предложений действий для системы.

## Сбор контекста
- [Факт] Импортирует `common_types.proto`, `actuator_raw_out.proto`, `google/protobuf/timestamp.proto`, `google/protobuf/duration.proto`.
- [Факт] Определяет `message Proposal`.
- [Гипотеза] Используется когнитивным модулем для формулирования действий.

## Локализация артефакта
- [Факт] Путь: `protos/proposal.proto`.
- [Факт] Пакет: `qiki.mind`.
- [Гипотеза] Сообщения отправляются диспетчеру решений.

## Фактический разбор
- [Факт] Поля: `proposal_id`, `source_module_id`, `timestamp`, `proposed_actions`, `justification`, `priority`, `expected_duration`, `type`, `metadata`, `confidence`, `status`, `depends_on`, `conflicts_with`, `proposal_signature`.
- [Факт] `ProposalType` включает `SAFETY`, `PLANNING`, `DIAGNOSTICS`, `EXPLORATION`.
- [Факт] `ProposalStatus` включает `PENDING`, `ACCEPTED`, `REJECTED`, `EXECUTED`, `EXPIRED`.

## Роль в системе и связи
- [Факт] Содержит набор команд (`ActuatorCommand`), объединённых логикой.
- [Гипотеза] Может служить интерфейсом между планировщиком и исполнительной частью.

## Несоответствия и риски
- [Гипотеза][Med] Отсутствие максимального размера `proposed_actions` может перегружать канал связи.
- [Гипотеза][Low] Поле `justification` без локализации может быть сложно использовать в разных языках.

## Мини-патчи (safe-fix)
- [Патч] Ограничить длину списка `proposed_actions` или добавить предупреждение в документации.
- [Патч] Ввести поле `locale` для `justification`.

## Рефактор-скетч
```proto
message Proposal {
  UUID proposal_id = 1;
  repeated ActuatorCommand actions = 4;
  float priority = 6;
}
```

## Примеры использования
```python
prop = Proposal(proposal_id=uuid1(),
                proposed_actions=[cmd],
                priority=0.8,
                type=Proposal.SAFETY)
```

## Тест-хуки/чек-лист
- Проверить сериализацию `depends_on` и `conflicts_with`.
- Тестировать влияние `priority` на порядок выполнения.
- Проверить подпись `proposal_signature` при валидации.

## Вывод
- [Факт] Структура описывает предложения действий с приоритетами и зависимостями.
- [Гипотеза] Необходимо учитывать размер и локализацию полей.
- [Патч] Предложены ограничения и дополнительное поле для `justification`.
