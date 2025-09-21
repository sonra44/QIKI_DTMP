# QIKI Digital Twin Microservices Platform (QIKI_DTMP)

**Версия: Phase 1 (сентябрь 2025)**

Этот документ содержит основную информацию о проекте, его архитектуре и инструкции по запуску и проверке системы.

## Описание

QIKI_DTMP — это высокопроизводительная, модульная платформа для разработки и симуляции интеллектуальных агентов, построенная на микросервисной архитектуре. Текущая версия (Phase 1) включает полностью интегрированный радарный пайплайн (Radar v1) с обработкой данных через NATS JetStream.

## Архитектура Phase 1

Система состоит из следующих контейнеров:

-   **`qiki-nats-phase1`**: Брокер сообщений NATS с включенным JetStream.
-   **`q-sim-service`**: Основной gRPC сервис симуляции, предоставляющий данные сенсоров.
-   **`q-sim-radar`**: Генератор радарных кадров, который публикует данные в NATS.
-   **`faststream-bridge`**: Приложение на FastStream, которое обрабатывает радарные кадры и генерирует треки.
-   **`qiki-dev`**: Основной контейнер для разработки и запуска Q-Core Agent.
-   **`nats-js-init`** (one-shot): Утилита, которая инициализирует необходимые потоки (streams) и потребителей (consumers) в JetStream при первом запуске.
-   **`qiki-registrar-phase1`**: Сервис аудита событий, который записывает структурированные логи событий системы с кодами 1xx-9xx.

## Быстрый старт

Все команды выполняются из корневой директории проекта `QIKI_DTMP`.

### 1. Сборка и запуск

Эта команда соберет и запустит все сервисы в фоновом режиме.

```bash
docker compose -f docker-compose.phase1.yml up -d --build
```

### 2. Проверка статуса контейнеров

```bash
docker compose -f docker-compose.phase1.yml ps
```

### 3. Проверка работоспособности (Health Checks)

#### NATS Health Check

```bash
curl -sf http://localhost:8222/healthz
```

Ожидаемый ответ: `{ "status": "ok" }`

#### gRPC Health Check (q-sim-service)

```bash
docker compose -f docker-compose.phase1.yml exec -T q-sim-service python - <<\'PY\'
import grpc
from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub
from generated.q_sim_api_pb2 import HealthCheckRequest
channel = grpc.insecure_channel(\'localhost:50051\'')
stub = QSimAPIServiceStub(channel)
print(stub.HealthCheck(HealthCheckRequest(), timeout=3.0))
PY
```

### 4. Запуск тестов

#### Интеграционные тесты радарного пайплайна

Эта команда проверит, что данные от радара корректно проходят через NATS JetStream.

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/integration/test_radar_flow.py tests/integration/test_radar_tracks_flow.py
```

#### Smoke-тесты Stage 0

Эта команда запускает комплексную проверку всех компонентов Stage 0, включая BotSpec, CloudEvents, мониторинг лагов, сервис регистратора и другие компоненты.

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  bash /workspace/scripts/smoke_test.sh
```

#### Полный набор тестов

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests
```

### 5. Остановка системы

```bash
docker compose -f docker-compose.phase1.yml down
```

