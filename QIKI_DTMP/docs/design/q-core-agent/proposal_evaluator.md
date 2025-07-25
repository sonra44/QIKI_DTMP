# Дизайн: Оценщик Предложений (Proposal Evaluator)

## 1. Обзор
Этот документ описывает компонент `Proposal Evaluator` в составе `Q-Core Agent`. Его основная задача — принимать список предложений (`Proposal` Protobuf-объектов) от различных источников (например, `Rule Engine`, `Neural Engine`) и выбирать наиболее подходящее или набор подходящих предложений для дальнейшей обработки модулем принятия решений (`_make_decision`).

## 2. Функциональные Требования
- Должен принимать список `Proposal` объектов.
- Должен оценивать предложения на основе их `priority` и `confidence`.
- Должен возвращать отфильтрованный и/или отсортированный список принятых предложений.
- Должен логировать отклоненные предложения с указанием причины.

## 3. Архитектура и Дизайн
`Proposal Evaluator` реализован как класс `ProposalEvaluator`, который имплементирует интерфейс `IProposalEvaluator`.

### 3.1. Логика Оценки (Текущая MVP реализация)
1.  **Фильтрация по уверенности:** Отклоняет предложения с `confidence` ниже заданного порога (например, 0.6).
2.  **Приоритезация:** Сортирует оставшиеся предложения сначала по `ProposalType` (используя их enum-значения как приоритет, где более высокое значение enum означает более высокий приоритет), затем по `priority` (поле `priority` в `Proposal`), и, наконец, по `confidence`.
3.  **Выбор:** Для MVP выбирается одно лучшее предложение после сортировки.

## 4. API Specification
`ProposalEvaluator` предоставляет программный API через метод `evaluate_proposals`.

- `evaluate_proposals(proposals: List[Proposal]) -> List[Proposal]`: Принимает список предложений и возвращает список принятых предложений.

## 5. Модели Данных
Использует `Proposal` Protobuf-объект, определенный в `protos/proposal.proto`.

## 6. Анти-паттерны
- **Сложная бизнес-логика:** `Proposal Evaluator` не должен содержать сложной бизнес-логики, не связанной напрямую с оценкой и выбором предложений. Например, он не должен генерировать новые команды или изменять состояние FSM.
- **Прямое взаимодействие с актуаторами:** Не должен напрямую отправлять команды актуаторам; это задача модуля принятия решений (`_make_decision`).

## 7. Открытые Вопросы
1.  Как будет реализована более сложная логика оценки предложений (например, учет конфликтов между предложениями, временные ограничения)?
2.  Нужен ли механизм для динамической настройки порогов `confidence` или правил приоритезации?
