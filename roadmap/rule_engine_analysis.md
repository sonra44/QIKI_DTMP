СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control_ultimate.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/rule_engine.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_actuators.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_bios_handler.py

# `/home/sonra44/QIKI_DTMP/services/q_core_agent/core/rule_engine.py`

## Вход и цель
- [Факт] Класс `RuleEngine` реализует `IRuleEngine`; генерирует предложения действий.
- [Гипотеза] Итог — чек-риск и патч-скетч.

## Сбор контекста
- [Факт] Использует Protobuf-сообщения (`Proposal`, `ActuatorCommand`, `FSMStateEnum`).
- [Гипотеза] В окружении есть `generated/*.pb2` файлы.
- [Факт] Зависит от `AgentContext` для проверки BIOS.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/rule_engine.py`.
- [Гипотеза] Вызывается агентом при каждом цикле принятия решения.

## Фактический разбор
- [Факт] Методы: `__init__`, `generate_proposals`.
- [Факт] Правило: при `context.is_bios_ok()==False` предлагает `SAFE_MODE`.
- [Гипотеза] Дополнительные правила пока не реализованы.

## Роль в системе и связи
- [Факт] Производит список `Proposal` для верхнего уровня агента.
- [Гипотеза] Считывает состояние из `AgentContext` и передает команды в `ShipCore`.

## Несоответствия и риски
- [Гипотеза] Нет разграничения уровней приоритетов (значения захардкожены) — Priority: Med.
- [Факт] Отсутствуют проверки на дублирование предложений — Priority: Low.
- [Гипотеза] При отсутствии Protobuf зависимостей модуль не имеет fallback — Priority: Low.

## Мини-патчи
- [Патч] Вынести коэффициенты `priority` и `confidence` в конфиг.
- [Патч] Добавить проверку, есть ли уже активное предложение `SAFE_MODE`.

## Рефактор-скетч
```python
class Rule:
    def evaluate(ctx) -> Optional[Proposal]: ...
class RuleEngine:
    def __init__(self, rules): self.rules = rules
    def generate(self, ctx): return [r.evaluate(ctx) for r in self.rules if r.evaluate(ctx)]
```

## Примеры использования
```python
# 1. Инстанцирование
engine = RuleEngine(context, {})

# 2. Генерация предложений
proposals = engine.generate_proposals(context)

# 3. Проверка наличия safe-mode
if any(p.type == Proposal.ProposalType.SAFETY for p in proposals):
    print("SAFE MODE suggested")

# 4. Добавление новой конфигурации
engine.config["max_priority"] = 1.0

# 5. Логгирование
from core.agent_logger import logger
logger.info(f"Generated {len(proposals)} proposals")
```

## Тест-хуки/чек-лист
- Симулировать `BIOS not OK` → получаем `SAFE_MODE`.
- Убедиться, что при `BIOS OK` список пуст.
- Проверить корректность полей `Proposal` (ID, приоритет).
- Обработка неизвестного `context` (исключения).
- Подключение к реальному `AgentContext` без Protobuf ошибок.

## Вывод
1. [Факт] Реализовано минимальное правило безопасности.
2. [Гипотеза] Конфигурация не используется.
3. [Факт] Код лаконичен, но без расширяемости.
4. [Гипотеза] Нужен механизм регистрации правил.
5. [Патч] Ввести структуру `Rule` и списком.
6. [Гипотеза] Логирование не учитывает контекст.
7. [Факт] Возвращается список `Proposal`.
8. [Патч] Добавить type-hints для `config`.
9. [Гипотеза] Возможны гонки при многопоточном доступе.
10. [Факт] Модуль годится для MVP, но требует расширения.

СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control_ultimate.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/rule_engine.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_actuators.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_bios_handler.py
