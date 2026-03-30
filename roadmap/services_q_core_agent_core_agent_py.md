# Анализ /home/sonra44/QIKI_DTMP/services/q_core_agent/core/agent.py

## СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/agent.py

## Вход и цель
- [Факт] Модуль реализует контекст и основной агент `QCoreAgent`.
- [Цель] Подготовить обзор поведения, выявить риски и предложить патчи.

## Сбор контекста
- [Факт] Импортируются классы `IBiosHandler`, `IFSMHandler`, `IProposalEvaluator`, `IRuleEngine`, `INeuralEngine`.
- [Факт] Используются сгенерированные protobuf-сообщения `BiosStatusReport`, `FsmStateSnapshot`, `Proposal`.
- [Гипотеза] Модуль работает в связке с `TickOrchestrator` для циклического исполнения.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/agent.py`.
- [Факт] Запускается косвенно из `services/q_core_agent/main.py`.

## Фактический разбор
- [Факт] `AgentContext` хранит BIOS, FSM и список предложений.
- [Факт] Метод `update_from_provider` запрашивает данные у `IDataProvider`.
- [Факт] `QCoreAgent` инициализирует обработчики и `TickOrchestrator`.
- [Факт] `_handle_bios`, `_handle_fsm`, `_evaluate_proposals` обрабатывают соответствующие части контекста с защитой от исключений.
- [Факт] `_make_decision` отправляет команды актуаторам через `BotCore`.
- [Гипотеза] Отсутствует явная синхронизация доступа к контексту при асинхронном использовании.

## Роль в системе и связи
- [Факт] `QCoreAgent` — центральный исполнитель логики робота.
- [Гипотеза] Используется как сервис верхнего уровня для оркестрации модулей.

## Несоответствия и риски
- [Риск|Med] `_make_decision` выбирает только первое предложение без приоритезации.
- [Риск|Low] Отсутствие проверки на `None` для `fsm_state.current_state` в `get_health_snapshot`.
- [Риск|Low] Нет логирования успешных отправок в `_handle_bios` и `_handle_fsm`.

## Мини-патчи (safe-fix)
- [Патч] Добавить сортировку предложений по `confidence` перед выбором.
- [Патч] В `get_health_snapshot` использовать `getattr` для безопасного доступа.
- [Патч] Расширить логирование успешных обработок.

## Рефактор-скетч
```python
class QCoreAgent:
    def _make_decision(self):
        if not self.context.proposals:
            return
        best = max(self.context.proposals, key=lambda p: p.confidence)
        for action in best.proposed_actions:
            self.bot_core.send_actuator_command(action)
```

## Примеры использования
```python
from services.q_core_agent.core.agent import QCoreAgent
from services.q_core_agent.core.interfaces import MockDataProvider

config = {}
provider = MockDataProvider(...)
agent = QCoreAgent(config)
agent.run_tick(provider)

# Проверка состояния
snapshot = agent.get_health_snapshot()
print(snapshot['tick_id'])

# Обновление контекста
agent._update_context(provider)

# Работа в безопасном режиме при ошибке
try:
    agent._handle_bios()
except Exception:
    agent._switch_to_safe_mode()
```

## Тест-хуки/чек-лист
- [ ] Имитировать ошибку в `bios_handler` и ожидать переход в safe mode.
- [ ] Проверить, что `get_health_snapshot` возвращает корректный словарь.
- [ ] Убедиться, что при пустых предложениях `_make_decision` не вызывает `BotCore`.

## Вывод
1. [Факт] Модуль аккумулирует ключевые компоненты агента.
2. [Факт] Обработчики вызываются последовательно и защищены `try/except`.
3. [Риск] Отсутствие приоритезации предложений.
4. [Риск] Возможные `None` в `fsm_state` при сборе метрик.
5. [Патч] Ввести сортировку по `confidence`.
6. [Патч] Безопасный доступ к полям FSM.
7. [Патч] Улучшить логирование.
8. [Гипотеза] Для асинхронного режима потребуется блокировка контекста.
9. [Факт] Код пригоден для MVP.
10. [Цель] Повысить устойчивость и прозрачность решений.
