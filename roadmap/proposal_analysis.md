## СПИСОК ФАЙЛОВ
- QIKI_DTMP/protos/proposal.proto

## Вход и цель
- [Факт] Анализ формата предложения действий; итог — обзор и патч-идеи.

## Сбор контекста
- [Факт] Импортирует `common_types.proto`, `actuator_raw_out.proto`, `google/protobuf/timestamp.proto`, `google/protobuf/duration.proto`.
- [Гипотеза] Используется в подсистеме принятия решений.

## Локализация артефакта
- [Факт] Путь: `QIKI_DTMP/protos/proposal.proto`.

## Фактический разбор
- [Факт] `Proposal` включает `proposal_id`, `source_module_id`, `timestamp`, `proposed_actions`, `justification`, `priority`, `expected_duration`, `type`, `metadata`, `confidence`, `status`, `depends_on`, `conflicts_with`, `proposal_signature`.
- [Факт] Enum `ProposalType` содержит варианты `SAFETY`, `PLANNING`, `DIAGNOSTICS`, `EXPLORATION`.
- [Факт] Enum `ProposalStatus` включает `PENDING`, `ACCEPTED`, `REJECTED`, `EXECUTED`, `EXPIRED`.

## Роль в системе и связи
- [Гипотеза] Служит предложением действий от модулей ИИ к исполнительной подсистеме.
- [Факт] Повторно использует `ActuatorCommand` для составных действий.

## Несоответствия и риски
- [Гипотеза][Med] Отсутствует поле для оценки стоимости/ресурсов.
- [Гипотеза][Low] Нет версии протокола или сигнатуры модуля.

## Мини-патчи (safe-fix)
- [Патч] Добавить поле `resource_cost`.
- [Патч] Зафиксировать `schema_version`.

## Рефактор-скетч
```proto
message Proposal {
  // ...
  float resource_cost = 15;
  uint32 schema_version = 16;
}
```

## Примеры использования
1. ```bash
   protoc -I=. --python_out=. QIKI_DTMP/protos/proposal.proto
   ```
2. ```python
   from proposal_pb2 import Proposal
   p = Proposal(priority=0.7)
   ```
3. ```python
   cmd = p.proposed_actions.add(command_type=1)
   ```
4. ```python
   p.conflicts_with.append(p.proposal_id)
   ```
5. ```python
   p.SerializeToString()
   ```

## Тест-хуки/чек-лист
- [Факт] Проверить сериализацию повторяющихся полей `depends_on` и `conflicts_with`.
- [Факт] Тестировать корректность `ProposalStatus` при обновлении.

## Вывод
1. [Факт] Формат поддерживает сложные предложения.
2. [Гипотеза] Требуется учёт ресурсов.
3. [Патч] Добавить `resource_cost` и `schema_version`.
4. [Факт] Включает цифровую подпись для безопасности.
5. [Гипотеза] Возможны конфликты при отсутствии правил разрешения.
6. [Патч] Добавить механизм приоритета при конфликте.
7. [Факт] Повторяющиеся поля облегчают зависимость задач.
8. [Гипотеза] `priority` и `confidence` могут быть перепутаны.
9. [Патч] Уточнить диапазон и смысл.
10. [Факт] Готов к использованию в планировщике.

## СПИСОК ФАЙЛОВ
- QIKI_DTMP/protos/proposal.proto
