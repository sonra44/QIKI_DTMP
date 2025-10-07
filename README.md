# QIKI Digital Twin Microservices Platform (QIKI_DTMP)

**Версия: Production Ready (октябрь 2025)**

Этот документ содержит основную информацию о проекте, его архитектуре и инструкции по запуску и проверке системы.

## Описание

QIKI_DTMP — это высокопроизводительная, модульная платформа для разработки и симуляции интеллектуальных агентов, построенная на микросервисной архитектуре. Система включает полностью интегрированный радарный пайплайн (Radar v1) с обработкой данных через NATS JetStream.

## Архитектура системы

**Оптимизированная архитектура для эффективной разработки:**

Система состоит из следующих контейнеров:

-   **`qiki-nats-phase1`**: Брокер сообщений NATS с включенным JetStream (порты: 4222, 8222).
-   **`qiki-sim-phase1`**: Основной gRPC сервис симуляции, предоставляющий данные сенсоров.
-   **`qiki-sim-radar-phase1`**: Генератор радарных кадров, который публикует данные в NATS.
-   **`qiki-faststream-bridge-phase1`**: Приложение на FastStream, которое обрабатывает радарные кадры и генерирует треки.
-   **`qiki-dev-phase1`**: Основной контейнер для разработки и запуска Q-Core Agent.
-   **`qiki-nats-js-init`** (one-shot): Утилита инициализации потоков JetStream.
-   **`qiki-registrar-phase1`**: Сервис аудита событий.

### LR/SR разделение радара

- `q-sim-service` публикует радарные кадры в три NATS-топика: `qiki.radar.v1.frames.lr` (Long Range без ID/IFF), `qiki.radar.v1.tracks.sr` (Short Range с транспондерными данными) и совместимый `qiki.radar.v1.frames`.
- Каждое сообщение содержит CloudEvents-хедеры и расширение `x-range-band` (`RR_LR`, `RR_SR`, `RR_UNSPECIFIED`).
- Порог разделения задаётся через `radar.sr_threshold_m` в конфиге Q-Sim Service.

## Быстрый старт

Все команды выполняются из корневой директории проекта `QIKI_DTMP_LOCAL`.

**Требования:**
- Docker Desktop запущен и работает
- Protobuf файлы сгенерированы в папке `generated/`
- Windows PowerShell или Bash

### 1. Сборка и запуск

```bash
# Стандартный запуск системы
docker compose up -d --build
```

### 2. Проверка статуса контейнеров

```bash
docker compose ps
```

### 3. Проверка работоспособности (Health Checks)

#### NATS Health Check

```bash
# В Linux/WSL
curl -sf http://localhost:8222/healthz

# В Windows PowerShell
Invoke-WebRequest -Uri http://localhost:8222/healthz -UseBasicParsing | Select-Object -ExpandProperty Content
```

Ожидаемый ответ: `{"status":"ok"}`

#### gRPC Health Check (q-sim-service)

```bash
docker compose exec q-sim-service python -c "import grpc; from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub; from generated.q_sim_api_pb2 import HealthCheckRequest; ch=grpc.insecure_channel('localhost:50051'); stub=QSimAPIServiceStub(ch); print(stub.HealthCheck(HealthCheckRequest(), timeout=3.0))"
```

### 4. Функциональное тестирование

#### Интеграционные тесты радарного пайплайна

Эти команды проверяют, что данные от радара корректно проходят через NATS JetStream и что LR/SR-разделение работает.

```bash
docker compose exec qiki-dev pytest -v tests/integration/test_radar_flow.py tests/integration/test_radar_tracks_flow.py

docker compose exec qiki-dev pytest -v tests/integration/test_radar_lr_sr_topics.py
```

#### Smoke-тесты Stage 0

Комплексная проверка всех компонентов системы.

```bash
docker compose exec qiki-dev bash /workspace/scripts/smoke_test.sh
```

#### Полный набор тестов

```bash
docker compose exec qiki-dev pytest -v tests/
```

### 5. Остановка системы

```bash
docker compose down
```

## Устранение неисправностей

### Protobuf файлы
Если система не запускается с ошибкой "ModuleNotFoundError: No module named 'generated'":

```bash
# Сгенерировать protobuf файлы
docker run --rm -v ${PWD}:/workspace -w /workspace qiki_dtmp_local-qiki-dev bash -c "
python -m grpc_tools.protoc -I./protos --python_out=./generated --grpc_python_out=./generated ./protos/*.proto
python -m grpc_tools.protoc -I./protos --python_out=./generated ./protos/radar/v1/radar.proto
"
```

### Просмотр логов

```bash
# Логи конкретного сервиса
docker logs qiki-sim-phase1 -f
docker logs qiki-nats-phase1 --tail 50

# Статус ресурсов
docker stats
```

---

**Готово к разработке!** Система оптимизирована для быстрого запуска и эффективной разработки.