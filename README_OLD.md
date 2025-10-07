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

### LR/SR разделение радара

- `q-sim-service` публикует радарные кадры в три NATS-топика: `qiki.radar.v1.frames.lr` (Long Range без ID/IFF), `qiki.radar.v1.tracks.sr` (Short Range с транспондерными данными) и совместимый `qiki.radar.v1.frames`.
- Каждое сообщение содержит CloudEvents-хедеры и расширение `x-range-band` (`RR_LR`, `RR_SR`, `RR_UNSPECIFIED`).
- Порог разделения задаётся через `radar.sr_threshold_m` в конфиге Q-Sim Service.

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

Эти команды проверяют, что данные от радара корректно проходят через NATS JetStream и что LR/SR-разделение работает.

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/integration/test_radar_flow.py tests/integration/test_radar_tracks_flow.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/integration/test_radar_lr_sr_topics.py
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
