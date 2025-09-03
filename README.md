# QIKI Digital Twin Microservices Platform (QIKI_DTMP) - Полное Руководство

**Версия Документа:** 2.0 (Полный анализ)  
**Дата Последней Верификации:** 2025-09-03

---

## 1. Философия и Назначение Проекта

**QIKI_DTMP** — это высокопроизводительная, модульная платформа для разработки, симуляции и запуска интеллектуальных агентов, спроектированная с фокусом на надежность и масштабируемость. Изначально задуманный как архитектурный макет и "цифровой двойник" для AI-агента, проект эволюционировал в сложную экосистему, готовую к реальным задачам.

### Ключевые Принципы ("Почему?"):

-   **Надежность превыше всего:** Проект является прямым ответом на предыдущие неудачные итерации, страдавшие от гонок состояний, неконсистентности данных и скрытых ошибок. Главный принцип — создание предсказуемой и стабильной системы.
-   **Document-First & Contract-Oriented:** Каждый компонент сначала описывается в детальных дизайн-документах, а взаимодействие между сервисами строго регламентируется через Protobuf-контракты. Это гарантирует, что все части системы "говорят на одном языке".
-   **Эволюционная Архитектура:** Система спроектирована для роста — от базового наземного робота (`Bot`) до сложного космического аппарата (`Ship`) и, в перспективе, до управления флотом.
-   **Проверяемость и Честность:** Встроенные механизмы (`ANTI_FRAUD_DOCUMENTATION_PROTOCOL.md`, `AI_DEVELOPER_PRINCIPLES.md`) требуют, чтобы каждое утверждение о готовности системы было подкреплено практическими тестами.

### Как это работает ("Как?"):

Система состоит из двух ключевых микросервисов:
1.  **`Q-Core Agent`**: "Мозг" агента. Работает в дискретном цикле ("тике"), на каждом шаге получая данные, обрабатывая их через конечный автомат (FSM) и принимая решения.
2.  **`Q-Sim Service`**: Симулятор физического мира. Генерирует данные сенсоров и исполняет команды, полученные от агента.

Взаимодействие между ними происходит через два независимых слоя коммуникации:
-   **gRPC:** Для прямых, синхронных запросов (например, "получить данные сенсора").
-   **NATS (через FastStream):** Для асинхронного, событийно-ориентированного обмена сообщениями в распределенной среде.

---

## 2. Детальный Анализ Компонентов

Для глубокого понимания каждого компонента, его роли, принципов работы и взаимодействия с другими модулями, пожалуйста, ознакомьтесь с детальными аналитическими файлами:

### 2.1. Компоненты Q-Core Agent

-   **Основная логика агента:**
    -   [`agent.py`](docs/analysis/agent.py.md) - Главный оркестратор агента.
    -   [`main.py`](docs/analysis/main.py.md) - Точка входа и сборщик зависимостей агента.
    -   [`tick_orchestrator.py`](docs/analysis/tick_orchestrator.py.md) - Дирижер цикла работы агента.
    -   [`bot_core.py`](docs/analysis/bot_core.py.md) - Низкоуровневое ядро и идентификация бота.
    -   [`interfaces.py`](docs/analysis/interfaces.py.md) - Абстрактные интерфейсы для модульности.
    -   [`agent_logger.py`](docs/analysis/agent_logger.py.md) - Независимая система логирования агента.

-   **Управление состоянием FSM:**
    -   [`store.py`](docs/analysis/store.py.md) - Единственный источник правды для состояния FSM (AsyncStateStore).
    -   [`types.py`](docs/analysis/types.py.md) - Неизменяемые DTO для состояний FSM.
    -   [`conv.py`](docs/analysis/conv.py.md) - Конвертер между DTO и Protobuf.
    -   [`fsm_handler.py`](docs/analysis/fsm_handler.py.md) - Хранитель логики переходов FSM.

-   **Движки Принятия Решений:**
    -   [`rule_engine.py`](docs/analysis/rule_engine.py.md) - Генерация предложений на основе правил.
    -   [`neural_engine.py`](docs/analysis/neural_engine.py.md) - Генерация предложений на основе ML-моделей (заглушка).
    -   [`proposal_evaluator.py`](docs/analysis/proposal_evaluator.py.md) - Оценка и выбор предложений.

### 2.2. Компоненты Q-Sim Service

-   [`main.py`](docs/analysis/q_sim_service_main.py.md) - Основной сервис симулятора.
-   [`core/world_model.py`](docs/analysis/world_model.py.md) - Модель симулируемого мира.
-   [`grpc_server.py`](docs/analysis/q_sim_service_grpc_server.py.md) - gRPC-сервер для симулятора.
-   [`logger.py`](docs/analysis/q_sim_service_logger.py.md) - Независимая система логирования симулятора.

### 2.3. Общие Модели Данных

-   [`shared/models/core.py`](docs/analysis/shared_models_core.py.md) - Pydantic-модели для FastStream-коммуникации.
-   [`shared/models/validators.py`](docs/analysis/shared_models_validators.py.md) - Пользовательские валидаторы Pydantic.

### 2.4. FastStream Bridge

-   [`services/faststream_bridge/app.py`](docs/analysis/faststream_bridge_app.py.md) - Мост для FastStream-коммуникации через NATS.

### 2.5. Определения Protobuf (.proto)

-   [`common_types.proto`](docs/analysis/protos_common_types.proto.md) - Фундаментальные типы данных.
-   [`sensor_raw_in.proto`](docs/analysis/protos_sensor_raw_in.proto.md) - Формат сообщений для сенсорных данных.
-   [`actuator_raw_out.proto`](docs/analysis/protos_actuator_raw_out.proto.md) - Формат сообщений для команд актуаторам.
-   [`bios_status.proto`](docs/analysis/protos_bios_status.proto.md) - Формат сообщений для отчетов BIOS.
-   [`fsm_state.proto`](docs/analysis/protos_fsm_state.proto.md) - Формат сообщений для снимков состояния FSM.
-   [`proposal.proto`](docs/analysis/protos_proposal.proto.md) - Формат сообщений для предложений.
-   [`q_sim_api.proto`](docs/analysis/protos_q_sim_api.proto.md) - gRPC-сервисный интерфейс для Q-Sim Service.

### 2.6. Тестовые Файлы

-   [`tests/models/test_pydantic_compatibility.py`](docs/analysis/tests_models_test_pydantic_compatibility.py.md) - Тесты совместимости Pydantic-моделей.
-   [`shared/models/tests/test_pydantic_models.py`](docs/analysis/shared_models_tests_pydantic_models.py.md) - Юнит-тесты для Pydantic-моделей.
-   [`tests/integration/test_faststream_bridge.py`](docs/analysis/tests_integration_test_faststream_bridge.py.md) - Интеграционные тесты FastStream-моста.

### 2.7. Скрипты Автоматизации

-   [`scripts/run_qiki_demo.sh`](docs/analysis/scripts_run_qiki_demo.sh.md) - Скрипт для запуска демо-системы.

---

## 3. Технологический Стек

-   **Язык:** Python 3.12
-   **Асинхронность:** `asyncio`
-   **Межсервисное взаимодействие:** `gRPC`, `FastStream` (поверх `NATS`)
-   **Валидация данных:** `Pydantic` (в `UP/` и `shared/`), `Protocol Buffers`
-   **Тестирование:** `pytest`, `pytest-asyncio`
-   **Контейнеризация:** `Docker`, `Docker Compose`
-   **Инструменты CI/CD:** `ruff` (линтинг), `shell-скрипты`

---

## 4. Как запустить и использовать

### Требования
-   Python 3.12+
-   Docker и Docker Compose
-   `protoc` (компилятор Protocol Buffers)

### Установка зависимостей
```bash
# Установка основных и faststream зависимостей
pip install -r requirements.txt && pip install -r requirements-faststream.txt
```

### Запуск через Docker (Рекомендуемый способ)
Этот способ автоматически поднимет все сервисы, включая NATS, в изолированной сети.

```bash
# Запустить все сервисы в фоновом режиме
docker-compose -f docker-compose.phase1.yml up --build -d

# Посмотреть логи агента
docker-compose -f docker-compose.phase1.yml logs -f qiki-dev
```

### Локальный запуск (для отладки)
Используйте `python3`.

1.  **Запустить gRPC сервер симулятора:**
    ```bash
    python3 services/q_sim_service/grpc_server.py
    ```

2.  **Запустить агента в отдельном терминале:**
    -   **В режиме gRPC (взаимодействие по сети):**
        ```bash
        python3 services/q_core_agent/main.py --grpc
        ```
    -   **В режиме с мок-данными (не требует симулятора):**
        ```bash
        python3 services/q_core_agent/main.py --mock
        ```
    -   **В Legacy режиме (прямой вызов в одном процессе):**
        ```bash
        python3 services/q_core_agent/main.py
        ```

### Запуск тестов
```bash
# Запустить все unit и integration тесты
python3 -m pytest

# Запустить полный hot-test для StateStore
./scripts/hot_test_statestore.sh
```

---

## 5. Структура Проекта

-   **/services**: Исходный код основных микросервисов (`q_core_agent`, `q_sim_service`, `faststream_bridge`).
-   **/UP**: Альтернативная реализация ядра системы на Pydantic.
-   **/protos**: `.proto` файлы, определяющие контракты данных для gRPC.
-   **/generated**: Автоматически сгенерированный Python-код из `.proto` файлов.
-   **/docs**: Проектная и архитектурная документация.
-   **/tests**: Комплексные тесты для проекта.
-   **/scripts**: Вспомогательные скрипты для тестирования и автоматизации.
-   **docker-compose.phase1.yml**: Файл для оркестрации сервисов с помощью Docker.
-   **requirements.txt**: Основные зависимости проекта.
