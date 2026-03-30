# СПИСОК ФАЙЛОВ
- `QIKI_DTMP/generated/proposal_pb2.py`

## Вход и цель
[Факт] Анализ protobuf-модуля предложений (Proposal). Цель — описать структуры и потенциальные риски.

## Сбор контекста
[Факт] Генерация из `proposal.proto`; используется `common_types_pb2`, `actuator_raw_out_pb2`, `timestamp_pb2`, `duration_pb2`.

## Локализация артефакта
[Факт] `generated/proposal_pb2.py`; Python 3.12, Protobuf 6.31.1.

## Фактический разбор
- [Факт] Сообщение `Proposal` со строковыми полями `proposal_id`, `source_module_id`, `justification`, `proposal_signature`.
- [Факт] Списки `proposed_actions`, `depends_on`, `conflicts_with`.
- [Факт] Числовые поля: `priority`, `confidence`.
- [Факт] Поле `expected_duration` типа `google.protobuf.Duration`.
- [Факт] Enum `ProposalType`: `UNSPECIFIED`, `SAFETY`, `PLANNING`, `DIAGNOSTICS`, `EXPLORATION`.
- [Факт] Enum `ProposalStatus`: `UNSPECIFIED`, `PENDING`, `ACCEPTED`, `REJECTED`, `EXECUTED`, `EXPIRED`.

## Роль в системе и связи
[Гипотеза] Используется модулем планирования для обмена предложениями между агентами и симулятором.

## Несоответствия и риски
- [Гипотеза] Отсутствие ограничения размера `metadata` (Med).
- [Гипотеза] Нет явной проверки взаимных конфликтов в зависимости (Low).

## Мини-патчи (safe-fix)
[Патч] Уточнить в .proto лимиты на размер `metadata` и `depends_on`.

## Рефактор-скетч
```python
prop = Proposal(priority=1,
                type=Proposal.ProposalType.SAFETY)
```

## Примеры использования
```python
# 1. Создание предложения
p = Proposal(proposal_id=common__types__pb2.UUID())
```
```python
# 2. Добавление команды
p.proposed_actions.add()
```
```python
# 3. Установка статуса
p.status = Proposal.ProposalStatus.PENDING
```
```python
# 4. Сериализация
raw = p.SerializeToString()
```
```bash
# 5. Просмотр ключей Enum
python - <<'PY'
from generated import proposal_pb2 as pr
print(pr.Proposal.ProposalType.keys())
PY
```

## Тест-хуки / чек-лист
- Создание `Proposal` с заполненными enum и списками.
- Сериализация/десериализация с `ActuatorCommand`.
- Поведение при пустом `proposal_id`.

## Вывод
1. [Факт] Сообщение `Proposal` богато полями и перечислениями.
2. [Гипотеза] Нужны ограничения на размеры списков.
3. [Патч] Добавить лимиты в спецификацию.
4. [Факт] Примеры демонстрируют создание и сериализацию.
5. [Гипотеза] Проверки конфликтов лучше реализовать на уровне сервиса.
6. [Факт] Присутствуют поля для зависимостей и конфликтов.
7. [Гипотеза] Поле `confidence` требует нормализации.
8. [Факт] Используются внешние типы `UUID`, `Timestamp`, `Duration`.
9. [Гипотеза] Возможна интеграция с системой аутентификации по `proposal_signature`.
10. [Факт] Изменения вносятся в .proto.
