# QIKI_DTMP Agent Guidelines

Этот файл предназначен для агентных coding assistants. Инструкции должны оставаться практичными, воспроизводимыми и ориентированными на реальный код репозитория.

## 1. Что такое QIKI_DTMP

QIKI_DTMP — это хардкорная космическая игра-симулятор, сосредоточенная на управлении беспилотным космическим летательным аппаратом, представленным как управляемая платформа взаимодействующих подсистем.

Аппарат может описываться в коде и обсуждении как `bot`, `drone`, `craft`, `vehicle`, `spacecraft` или `satellite`. Эти термины описательные и не меняют архитектурного владения истиной.

Управление строится вокруг:
- чтения телеметрии,
- отправки команд,
- выполнения процедур,
- реакции на события и инциденты,
- работы с AI-слоем как частью игрового процесса.

## 2. Каноническая архитектурная цепочка

Канонический путь реализации:

**спецификация машины  
-> simulation runtime  
-> transport/events  
-> policy и command legality  
-> operator surface  
-> audit/history**

В репозитории этому соответствуют:

**bot_config.json + root config/*  
-> q_sim_service  
-> transport/events/radar frames  
-> faststream_bridge  
-> ORION V  
-> registrar**

## 3. Владельцы истины

### 3.1. Physical truth
Физическая истина рождается только:
- в спецификации машины,
- в симуляторе.

Это означает:

1. `bot_config.json` и файлы в `config/*` задают устройство аппарата, состав подсистем, ограничения, сенсоры, исполнительные контуры и конфигурацию.
2. `q_sim_service` реализует поведение этой спецификации во времени и является владельцем physical runtime truth.
3. Если мир или окружение в будущем будут вынесены в отдельный микросервис или сеть микросервисов, они тоже должны подчиняться этой физической истине и не имеют права придумывать собственную физику вне канонической спецификации.
4. Никакой другой слой не имеет права порождать или переопределять physical truth.

### 3.2. Восприятие мира
Восприятие физического мира определяется:
- спецификацией аппарата,
- его runtime-состоянием,
- телеметрией,
- сенсорами,
- ограничениями наблюдения.

Это означает:

1. Оператор, AI и policy-слой работают не с “абсолютным миром”, а с доступным аппарату представлением мира.
2. Телеметрия, сенсоры, ограничения наблюдения, доступность, точность, stale-состояния и деградации определяются конфигурацией и runtime.
3. UI может агрегировать, пояснять и визуализировать эти данные, но не может становиться вторым источником физической истины.

### 3.3. Policy / command legality
Политика допуска команд живёт в `faststream_bridge`.

Это означает:

1. Командная цепочка должна сохранять путь:

   **intention -> proposal -> legality -> command -> ack -> audit**

2. `faststream_bridge` является владельцем policy и command legality.
3. `QIKI` является intention / proposal layer и не должен становиться direct executor.
4. `q_sim_service` исполняет допустимые команды, но не является владельцем policy.
5. `ORION V` является каноническим операторским постом и не должен становиться владельцем physical truth.

## 4. Жёсткие архитектурные правила

1. Любое physical behavior должно происходить из machine spec и simulation runtime.
2. UI не должен становиться источником physical truth.
3. Cognitive / proposal / policy layers не должны превращаться во второй симулятор.
4. Operator projections должны оставаться отличимыми от raw runtime state.
5. Любое новое поле или состояние должно быть классифицируемо как одно из:
   - `raw_runtime`
   - `derived_runtime`
   - `transport_contract`
   - `policy_derived`
   - `operator_projection`
   - `legacy_or_unknown`
6. Любой новый command path должен явно указывать:
   - policy owner,
   - expected ack,
   - audit behavior.
7. Любой новый entrypoint должен быть явно помечен как:
   - `canonical`
   - `dev-only`
   - `experimental`
   - `legacy`

## 5. Legacy rules

1. Исторические модули вне канонического execution path считаются legacy по умолчанию, если их необходимость не подтверждена активным runtime.
2. Новые импорты из legacy-paths запрещены.
3. Перед изоляцией legacy-модуля нужно определить:
   - его текущую роль,
   - есть ли активная зависимость,
   - какая живая альтернатива уже существует,
   - какой тест обязателен после изоляции.
4. `operator_console` как namespace не считается legacy автоматически, если внутри него находится живой канонический слой `orion_v`.
5. Конкурирующие historical entrypoints, старые оболочки и дублирующие control-ветки должны изолироваться, если они не являются частью канонического пути.

## 6. Минимальная post-change verification

После каждого архитектурно значимого изменения проверять:

- путь `q_sim_service` жив;
- путь `ORION V` жив;
- путь `faststream_bridge` жив;
- каноническая цепочка  
  `machine spec -> runtime -> transport -> policy -> operator -> audit`
  не нарушена.

---

# 7. Project Structure (High Signal)

- `src/qiki/` — основной Python package (shared models, converters, services).
- `src/qiki/services/q_sim_service/` — simulation runtime и physical truth owner.
- `src/qiki/services/faststream_bridge/` — policy / command legality / semantic bridge.
- `src/qiki/services/operator_console/orion_v/` — ORION V, канонический operator surface.
- `src/qiki/services/operator_console/` — также содержит historical entrypoints и вспомогательные оболочки; не считать весь каталог legacy автоматически.
- `src/qiki/services/registrar/` — audit/history layer.
- `generated/` — generated protobuf stubs (`*_pb2.py`), required by runtime and tests.
- `protos/`, `proto/`, `proto_extensions/` — protobuf sources and extensions.
- `docs/design/operator_console/` — reference design documentation для ORION UX, runbook и validation.
- `docs/design/hardware_and_physics/` — reference design documentation для аппаратной и физической модели.
- `docker-compose*.yml`, `Dockerfile*` — Docker-first orchestration (dev environment uses Python 3.12).
- `scripts/`, `tools/` — quality gate, smoke tests, proto generation, helper utilities.
- `tests/` — unit / integration / UI tests.

---

# 8. Build / Lint / Test (Docker-first)

## 8.1. Start / Run

- Поднять default stack:
  `docker compose up -d --build`

- Phase1 + ORION Operator Console:
  - background:
    `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
  - foreground:
    `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up operator-console`
  - live TUI under tmux:
    `./scripts/run_orion_v_live.sh`
  - preferred local ORION V launch helper:
    `docker exec -it qiki-operator-console python main_orion_v.py`

- Не использовать `docker attach qiki-operator-console` как default live path для ORION V под tmux.

### Logs / status
- status:
  `docker compose -f docker-compose.phase1.yml ps`
- tail logs:
  `docker compose -f docker-compose.phase1.yml logs -f --tail=200 <service>`

## 8.2. Quality Gate (preferred)

- default:
  `bash scripts/quality_gate_docker.sh`

- useful toggles:
  - `QUALITY_GATE_RUFF_FORMAT_CHECK=1 bash scripts/quality_gate_docker.sh`
  - `QUALITY_GATE_RUN_INTEGRATION=1 bash scripts/quality_gate_docker.sh`
  - `QUALITY_GATE_RUN_MYPY=1 bash scripts/quality_gate_docker.sh`
  - `QUALITY_GATE_SCOPE=src/qiki/services/operator_console bash scripts/quality_gate_docker.sh`

## 8.3. Ruff (lint / format)

- lint all:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check .`
- lint one file:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check path/to/file.py`
- format check:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff format --check .`
- format write:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff format .`

Ruff config: `ruff.toml`  
(line length 120; includes `TID252`, so prefer absolute imports and avoid relative imports).

## 8.4. Pytest

Important: `pytest.ini` uses:

`addopts = -q -m "not integration"`

- run all non-integration tests:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q`
- run single test file:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_foo.py`
- run single test function:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_foo.py::test_bar`
- run by keyword:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q -k "keyword"`

Integration tests (`@pytest.mark.integration`) must override default addopts.

Preferred wrapper:
- folder:
  `./scripts/run_integration_tests_docker.sh tests/integration`
- single file:
  `./scripts/run_integration_tests_docker.sh tests/integration/test_radar_flow.py`
- single test:
  `./scripts/run_integration_tests_docker.sh tests/integration/test_radar_flow.py::test_name`

Smoke tests:
- stage 0 smoke:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash /workspace/scripts/smoke_test.sh`

## 8.5. Mypy (optional)

- run when enabled:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev mypy --config-file mypy.ini src`

Note:
`mypy.ini` currently ignores some services (`q_core_agent`, `q_sim_service`, `faststream_bridge`) to keep signal-to-noise manageable.

## 8.6. Protobuf Stubs

- generate stubs:
  `docker compose -f docker-compose.phase1.yml run --rm qiki-dev bash -lc "bash tools/gen_protos.sh"`

Output goes to:
- `generated/`

---

# 9. ORION V Rules

1. UI strings must be bilingual `EN/RU` with no spaces around `/`.
2. No-mocks: missing data must render as `N/A/—`; do not invent zeros.
3. No auto-actions: destructive or irreversible commands require explicit operator confirmation.
4. Mechanical overrides may exist, but should be hidden by default and gated by explicit env flags.
5. ORION V is the canonical operator surface. Historical operator entrypoints must not be treated as equal canonical alternatives.

Useful ORION env flags:
- `OPERATOR_CONSOLE_DEV_DOCKING_COMMANDS=1`  
  enable dev-only mechanical docking CLI commands
- `ORION_TELEMETRY_DICTIONARY_PATH=docs/design/operator_console/TELEMETRY_DICTIONARY.yaml`  
  override dictionary path

Telemetry semantics are dictionary-driven and must stay aligned with real payloads:

- canonical telemetry dictionary:
  `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml`
- drift guard:
  `tests/unit/test_telemetry_dictionary.py`
- live audit example:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc "NATS_URL=nats://nats:4222 python tools/telemetry_smoke.py --audit-dictionary --subsystems power,thermal,sensors,propulsion,comms,system,docking"`

ORION-specific specialist playbook:
- `docs/agents/orion_tui_agent.md`

---

# 10. Python Code Style

- indentation: 4 spaces
- max line length: 120
- imports:
  - prefer absolute imports (`from qiki...`)
  - prefer `qiki.radar.*`; `radar.*` is a legacy shim
- typing:
  - add type hints for public APIs and non-trivial logic
  - avoid `Any` unless working at a boundary (JSON/NATS/proto/files)
- naming:
  - modules/functions/vars: `snake_case`
  - classes: `PascalCase`
  - constants: `UPPER_SNAKE_CASE`
- errors:
  - do not swallow exceptions silently
  - for external I/O (NATS/gRPC/files), use timeouts and actionable errors
  - prefer explicit `N/A` states to misleading defaults

---

# 11. Testing Conventions

- tests live in `tests/unit/`, `tests/integration/`, `tests/ui/`
- keep tests deterministic
- avoid raw sleeps unless unavoidable
- prefer polling with timeouts
- for Textual UI, prefer headless tests (`pytest-textual` / `App.run_test`) and assert on state

---

# 12. Docs / Contracts

These documents are reference documentation, not runtime truth owners.

- operator control semantics:
  `docs/design/operator_console/SIMULATION_CONTROL_CONTRACT.md`
- ORION system model + data plane:
  `docs/design/operator_console/ORION_OS_SYSTEM.md`
- ORION canonical UX spec:
  `docs/design/operator_console/CANONICAL_SPEC_ORION_QIKI.md`

---

# 13. Git / PR Hygiene

- keep changes scoped
- do not mix refactors with functional changes
- one task = one branch = one PR
- branch naming:
  `task-<id>-<slug>`
- start every new task from fresh `main`
- do not continue work in a merged branch
- before push / PR, run:
  `bash scripts/branch_policy_check.sh`
- push to GitHub requires GitHub-side review/check handling before merge
- merge to `main` only after checks are green and findings are addressed
- required GitHub checks for merge:
  - `load`
  - `Sourcery review`
  - `CodeRabbit`
- require `@codex review` on PR and process findings before merge
- if telemetry/UI semantics change, update `TELEMETRY_DICTIONARY.yaml` and keep `tests/unit/test_telemetry_dictionary.py` green
- for ORION UI changes, include tmux evidence (`capture-pane` / screenshot) and note terminal size if layout-sensitive

---

# 14. Agent Workflow Hooks

- “ПРОЧТИ ЭТО” bootstrap:
  `~/MEMORI/ПРОЧТИ_ЭТО_QIKI_DTMP.md`
- prefer Docker-first validation before claiming something works
- ORION hotkeys:
  Events live/pause toggle is `Ctrl+Y`