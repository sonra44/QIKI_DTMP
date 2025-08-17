# Отчёт: `generated/proposal_pb2.py`

## Вход и цель
- [Факт] Анализ структуры сообщения `Proposal` в `generated/proposal_pb2.py`.
- [Факт] Итог: обзор полей и enum предложений.

## Сбор контекста
- [Факт] Файл определяет сообщение `Proposal` и перечисления `ProposalType`, `ProposalStatus`.
- [Факт] Зависимости: `common_types_pb2`, `actuator_raw_out_pb2`, `timestamp_pb2`, `duration_pb2`.
- [Гипотеза] Используется в модулях планирования и диагностики агента.

## Локализация артефакта
- [Факт] Путь: `generated/proposal_pb2.py` (архив `QIKI_DTMP.zip`).
- [Факт] Протокол `protobuf` версии 6.31.1.

## Фактический разбор
- [Факт] Поля `Proposal`:
  - `proposal_id`: UUID
  - `source_module_id`: string
  - `timestamp`: Timestamp
  - `proposed_actions`: repeated ActuatorCommand
  - `justification`: string
  - `priority`: float
  - `expected_duration`: Duration
  - `type`: enum `ProposalType`
  - `metadata`: map<string, string>
  - `confidence`: float
  - `status`: enum `ProposalStatus`
  - `depends_on`: repeated UUID
  - `conflicts_with`: repeated UUID
  - `proposal_signature`: string
- [Факт] `ProposalType`: `SAFETY`, `PLANNING`, `DIAGNOSTICS`, `EXPLORATION`.
- [Факт] `ProposalStatus`: `PENDING`, `ACCEPTED`, `REJECTED`, `EXECUTED`, `EXPIRED`.
- [Гипотеза] `priority` и `confidence` нормируются в диапазоне 0..1.

## Роль в системе и связи
- [Факт] Служит для передачи предложений между модулями агента и исполнительной системой.
- [Гипотеза] Может храниться в очереди задач для дальнейшей оценки.

## Несоответствия и риски
- [Факт] Нет проверки уникальности `depends_on`/`conflicts_with` (Med).
- [Гипотеза] Некорректные диапазоны `priority` и `confidence` могут нарушить планирование (Low).

## Мини-патчи (safe-fix)
- [Патч] Проверять, что `priority` и `confidence` находятся в пределах 0..1.
- [Патч] Удалять дубликаты UUID в `depends_on` и `conflicts_with`.

## Рефактор-скетч (по желанию)
```python
# [Патч]
proposal.depends_on = list(dict.fromkeys(proposal.depends_on))
```

## Примеры использования
```python
# [Факт]
from generated import proposal_pb2
p = proposal_pb2.Proposal(priority=0.5, confidence=0.8)
```

## Тест-хуки/чек-лист
- [Факт] Unit-тест сериализации `Proposal` с заполненными полями.
- [Гипотеза] Интеграционный тест проверки конфликтующих предложений.

## Вывод
- [Факт] Файл описывает структуру предложения агента.
- [Патч] Валидация числовых полей и уникальности списков повысит надёжность.
- [Гипотеза] Расширение набора статусов можно отложить.
