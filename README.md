# QIKI_DTMP

Платформа цифрового двойника и симуляции для операторских сценариев.

QIKI_DTMP — это не просто набор микросервисов. Это симулятор с единой “истиной мира” (`q-sim-service`), потоком телеметрии через NATS JetStream и операторским интерфейсом ORION (TUI), где состояние системы должно быть понятно за секунды.

## Что это за симулятор

Система моделирует состояние аппарата/среды и публикует симуляционную правду в телеметрию и радарные потоки. Поверх этого:
- ORION показывает оператору живое состояние (без моков и “красивых нулей”).
- Q-Core/Bridge/Registrar обрабатывают события, треки, команды и аудит.
- Решения принимаются на основе реальных payload из симуляции, а не из UI-фикций.

## Актуальный статус (2026-02-09)

- Startup UX ORION переведён в compact-by-default для Tier A поверхностей:
  - `summary`: causal badges + унифицированные короткие action hints.
  - `power`: компактный signal-first вывод, приоритет критичных сигналов и dock-контекста.
  - `system`: essential-only представление с подавлением `N/A`-шума.
- В quality gate встроен anti-loop контроль:
  - `scripts/ops/anti_loop_gate.sh`
  - проверяет доказуемость изменений (Scenario / Reproduction / Before-After / Impact Metric).
- Последний checkpoint читаемости startup summary:
  - `READABILITY_SLA_SECONDS=7.49` (тренд: `7.91 -> 7.73 -> 7.49`).

Детальные доказательства:
- `TASKS/TASK_20260210_orion_telemetry_semantic_panels_tierA.md`
- `TASKS/ARTIFACT_20260210_orion_summary_weekly_before_after.md`

## Состав системы (Phase1)

- `qiki-nats-phase1`: NATS + JetStream (`4222`, `8222`).
- `q-sim-service`: источник симуляционной правды (gRPC + публикация радарных кадров).
- `qiki-faststream-bridge-phase1`: обработка кадров/команд, публикация треков/ответов.
- `qiki-dev-phase1`: контейнер разработки и запуска Q-Core логики.
- `qiki-registrar-phase1`: аудит/события.
- `qiki-operator-console`: ORION TUI.
- `qiki-nats-js-init`: one-shot инициализация stream/consumers.

LR/SR радар:
- LR: `qiki.radar.v1.frames.lr`
- SR: `qiki.radar.v1.tracks.sr`
- совместимый поток: `qiki.radar.v1.frames`

## Быстрый старт

Все команды запускайте из корня репозитория:

```bash
cd "$(git rev-parse --show-toplevel)"
```

Требования:
- Docker запущен
- есть Bash/PowerShell
- protobuf сгенерирован в `generated/` (при необходимости см. Troubleshooting)

### 1) Поднять Phase1

```bash
docker compose -f docker-compose.phase1.yml up -d --build
docker compose -f docker-compose.phase1.yml ps
```

### 2) Поднять ORION Console

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up operator-console
```

Фоновый вариант:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d operator-console
docker attach qiki-operator-console
```

### 3) Быстрые health проверки

NATS:

```bash
curl -sf http://localhost:8222/healthz
```

q-sim-service gRPC:

```bash
docker compose -f docker-compose.phase1.yml exec q-sim-service python -c "import grpc; from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub; from generated.q_sim_api_pb2 import HealthCheckRequest; ch=grpc.insecure_channel('localhost:50051'); stub=QSimAPIServiceStub(ch); print(stub.HealthCheck(HealthCheckRequest(), timeout=3.0))"
```

### 4) Основной quality gate

```bash
bash scripts/quality_gate_docker.sh
```

По умолчанию: lint + unit + anti-loop; integration/mypy включаются флагами.

## ORION compact toggles

Для сравнения compact vs verbose:

```bash
ORION_SUMMARY_COMPACT_DEFAULT=0
ORION_SYSTEM_COMPACT_DEFAULT=0
ORION_POWER_COMPACT_DEFAULT=0
```

Если не задано, используется compact-by-default startup режим.

## Troubleshooting

Если нет `generated`:

```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev bash -lc "bash tools/gen_protos.sh"
```

Логи:

```bash
docker logs qiki-sim-phase1 -f
docker logs qiki-nats-phase1 --tail 100
```

## Где правда и что читать

- Канон приоритетов: `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Текущий status snapshot: `CURRENT_STATE.md` (исторические snapshots в `CONTEXT/`)
- Архитектура: `docs/ARCHITECTURE.md`
- Индекс доков: `docs/INDEX.md`
- Правила anti-loop: `docs/ops/ANTI_LOOP_POLICY.md`
