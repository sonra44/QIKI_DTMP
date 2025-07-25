Ты — инженер-исполнитель в репозитории QIKI_DTMP. Задача: автоматически привести проект к инженерному состоянию (M0) и зафиксировать архитектуру/контракты/DSL (M1), создавая маленькие независимые PR-ы (≤500 строк дельты). Работай итеративно: сделал шаг → открыл PR → дождался зелёного CI → следующий шаг.

### ОБЩИЕ ПРАВИЛА

1. Не смешивай несвязанные изменения. Каждый PR решает одну маленькую задачу.
2. Коммиты строго в стиле Conventional Commits.
3. Ветки: feature/<milestone>-<task-short>, fix/<...>.
4. После каждого PR опиши в теле PR:
   - Что сделано и почему.
   - Дерево изменённых файлов (`tree -a`).
   - Команды для локального запуска (lint/mypy/tests).
   - Acceptance Criteria (что должно быть зелёным).
5. Если не можешь создать Issues/PR — создай `TODO.md` с чеклистами, структурой Milestones и пошаговым планом. Затем всё равно выполни изменения по шагам.
6. Все print() заменить на структурированное логирование позже, в рамках M1-4.
7. Всё, что можешь — автоматизируй в CI (GitHub Actions).
8. Если что-то непонятно — создай `OPEN_QUESTIONS.md` и сам предложи ответ/варианты.

### MILESTONES

M0 — Repo Sanity & CI (7 задач)
M1 — Архитектура, Контракты, DSL (6 задач)

(Позже мы добавим M2+.)

---------------------------------
M0 — Repo Sanity & CI
---------------------------------

Задачи (создавай отдельные PR-ы в этом порядке):

[M0-1] Репозитория санитария и метафайлы  
  - Создай: README.md, CONTRIBUTING.md, CODEOWNERS, LICENSE (MIT), CHANGELOG.md (Keep a Changelog + SemVer), .editorconfig, .gitignore.
  - README: краткое описание, структура, план Milestones, placeholder под CI badge.
  - CHANGELOG: начни с 0.0.1.

[M0-2] Переезд в src/ layout  
  - Весь код должен лежать в `src/qiki_dtmp/...`
  - Тесты — в `tests/`.
  - Импорты поправь.
  - Добавь минимальный `tests/test_smoke.py` (пустой, но запускаемый).

[M0-3] Инструментарий через pyproject.toml  
  - Добавь `pyproject.toml` со следующими dev-зависимостями: ruff, black, isort, mypy, pytest, pytest-cov, pre-commit, grpcio, grpcio-tools, pydantic>=2, structlog, prometheus-client.
  - Настрой инструментов: ruff/black/isort/mypy/pytest (строгий mypy: strict=true, ignore_missing_imports=true ок).
  - requirements-dev.txt не нужен, если используем `pip install .[dev]`. Если нельзя — добавь requirements-dev.txt.

[M0-4] pre-commit  
  - Добавь `.pre-commit-config.yaml` с хуками: ruff (—fix), black, isort, mypy.
  - Добавь цель `precommit` в Makefile.
  - В README покажи, как поставить: `pre-commit install`.

[M0-5] CI (GitHub Actions)  
  - `.github/workflows/ci.yml`: steps — checkout, setup-python 3.11, `pip install uv`, `uv pip install .[dev]`, ruff, black --check, mypy, pytest с coverage.
  - Добавь бейдж статуса CI в README.

[M0-6] Smoke-тесты  
  - Добавь хотя бы 1-2 реальных простых теста (не падают).
  - CI должен быть зелёный.

[M0-7] Документация-скелет  
  - `docs/ARCHITECTURE.md` (черновик): 3 сервиса (Q-Sim Service, Q-Core Agent, Q-Operator Console), шина обмена, логирование, метрики.
  - `docs/ROADMAP.md`: Milestones (M0, M1, M2, M3, ...), список задач.
  - (Опционально) MkDocs + GitHub Pages workflow; можно оставить TODO.

---------------------------------
M1 — Архитектура, Контракты, DSL
---------------------------------

Задачи (по очереди отдельными PR-ами):

[M1-1] High-level архитектура (уточнение)  
  - Дополни `docs/ARCHITECTURE.md`:
    - Протоколы взаимодействия: выбери gRPC/protobuf для межсервисных вызовов, HTTP/JSON для Operator Console (если уместно).
    - Версионирование контрактов.
    - Слои: API / Application / Domain / Infrastructure.
    - Наблюдаемость (logging/metrics/healthz/readyz/trace_id).

[M1-2] Контракты (.proto) + генерация  
  - Создай `contracts/` и минимум 1 proto-файл (например, `telemetry.proto`).
  - Создай `tools/compile_protos.py` на базе grpc_tools.protoc.
  - Создай `Makefile` цели: proto, lint, type, fmt, test, precommit.
  - Подключи генерацию в CI (проверка, что сгенерированный код синхронизирован).
  - Сгенерируй код в `src/qiki_dtmp/generated`.

[M1-3] Вынесение FSM/Rules/Degradation в config/*.yaml  
  - Создай `config/fsm_transitions.yaml`, `config/rules.yaml`, `config/degradation.yaml`.
  - Создай Pydantic-схемы для их валидации.
  - Покрой тестами загрузку конфигов и 3-4 сценария FSM (юнит-тесты).

[M1-4] Структурированное логирование  
  - Введи единый init логера через structlog/json.
  - Убери все print().
  - Проброс trace_id в контексте.

[M1-5] Health/Ready endpoints + метрики  
  - Для каждого сервиса (пока можно сделать каркас/заглушки): /healthz, /readyz.
  - Prometheus metrics (requests_total, errors_total, durations).
  - Тесты эндпоинтов.

[M1-6] Контрактные тесты  
  - Для gRPC/HTTP слоёв создай тесты, которые проверяют совместимость схем/контрактов между сервисами.
  - Стабилизируй CI.

---------------------------------
Шаблоны файлов (встраивай и дорабатывай)
---------------------------------

Сгенерируй **точно такие** файлы, если их нет (дальше можешь доработать):
- pyproject.toml (см. ниже)
- .editorconfig
- .gitignore
- .pre-commit-config.yaml
- .github/workflows/ci.yml
- Makefile
- tools/compile_protos.py
- contracts/telemetry.proto
- README.md
- CONTRIBUTING.md
- CODEOWNERS
- CHANGELOG.md
- docs/ARCHITECTURE.md
- docs/ROADMAP.md

(Используй скелеты ниже. Если обнаружишь конфликты — предложи миграционный путь и фиксирующий PR.)

----- ВСТРОЙ СЛЕДУЮЩИЕ СОДЕРЖИМАЕ ФАЙЛОВ БЕЗ ИЗМЕНЕНИЙ (далее можешь адаптировать) -----

[pyproject.toml]
<ВСТАВЬ ТОЧНО ИЗ ЭТОГО БЛОКА:>
[project]
name = "qiki_dtmp"
version = "0.0.1"
description = "QIKI Digital Twin Microservices Platform"
readme = "README.md"
requires-python = ">=3.11"
authors = [{ name = "Max", email = "you@example.com" }]
license = { text = "MIT" }

dependencies = [
]

[project.optional-dependencies]
dev = [
  "ruff",
  "black",
  "isort",
  "mypy",
  "pytest",
  "pytest-cov",
  "pre-commit",
  "grpcio",
  "grpcio-tools",
  "pydantic>=2",
  "structlog",
  "prometheus-client",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.black]
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
strict = true

[tool.pytest.ini_options]
addopts = "-q --cov=src --cov-report=term-missing"
testpaths = ["tests"]

[.editorconfig]
root = true

[*]
indent_style = space
indent_size = 4
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[.gitignore]
__pycache__/
*.pyc
.venv/
.env
.mypy_cache/
.pytest_cache/
.coverage
dist/
build/
htmlcov/
.generated/

[.pre-commit-config.yaml]
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.7
    hooks:
      - id: ruff
        args: ["--fix"]
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: ["pydantic>=2"]

[.github/workflows/ci.yml]
name: CI

on:
  push:
    branches: [ main, develop, "feature/**", "fix/**" ]
  pull_request:

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install uv
        run: pip install uv
      - name: Install deps
        run: |
          uv pip install .[dev]
      - name: Lint (ruff)
        run: ruff check src tests
      - name: Format check (black)
        run: black --check src tests
      - name: Type check (mypy)
        run: mypy src
      - name: Tests
        run: pytest

[Makefile]
.PHONY: proto test lint type fmt precommit

proto:
python tools/compile_protos.py

lint:
ruff check src tests

type:
mypy src

fmt:
black src tests && isort src tests

test:
pytest

precommit:
pre-commit install
pre-commit run --all-files

[tools/compile_protos.py]
#!/usr/bin/env python
import sys
from pathlib import Path
from grpc_tools import protoc

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
OUT = ROOT / "src" / "qiki_dtmp" / "generated"

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    proto_files = list(CONTRACTS.rglob("*.proto"))
    if not proto_files:
        print("No .proto files found", file=sys.stderr)
        return 1

    for pf in proto_files:
        args = [
            "protoc",
            f"-I{CONTRACTS}",
            f"--python_out={OUT}",
            f"--grpc_python_out={OUT}",
            str(pf),
        ]
        if protoc.main(args) != 0:
            return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

[contracts/telemetry.proto]
syntax = "proto3";

package qiki.telemetry.v1;

message TelemetrySample {
  string trace_id = 1;
  int64 ts_unix_ms = 2;
  double battery_level = 3;
  double temperature_c = 4;
}

message TelemetryAck {
  string status = 1; // "ok" / "error"
}

service TelemetryService {
  rpc PushSample (TelemetrySample) returns (TelemetryAck);
}

[README.md]
# QIKI_DTMP — Digital Twin Microservices Platform

![CI](<CI_BADGE_URL>)

## Суть

Платформа цифрового двойника с разделением на 3 сервиса:

1. **Q-Sim Service** — симуляция физического мира.
2. **Q-Core Agent** — логика принятия решений, FSM, правила, деградации.
3. **Q-Operator Console** — интерфейс оператора.

## Статус

M0: Repo Sanity & CI — в работе / завершён  
См. [docs/ROADMAP.md](docs/ROADMAP.md).

## Быстрый старт

```bash
pip install uv
uv pip install .[dev]
pre-commit install
pytest
````

## Контракты

См. `contracts/` и `tools/compile_protos.py`.

## Документация

* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
* [docs/ROADMAP.md](docs/ROADMAP.md)

\[CONTRIBUTING.md]

# CONTRIBUTING

## Коммиты

Conventional Commits:

* feat:
* fix:
* refactor:
* docs:
* test:
* chore:

## Ветки

* main (защищённая)
* develop
* feature/*
* fix/*

## CI

Каждый PR обязан проходить:

* ruff, black, isort
* mypy
* pytest + coverage

\[CODEOWNERS]

* @sonra44

\[CHANGELOG.md]

# Changelog

Формат — Keep a Changelog, SemVer.

## \[0.0.1] - 2025-07-25

### Added

* Initial repository scaffolding (start of M0).

\[docs/ARCHITECTURE.md]

# Архитектура QIKI_DTMP

## Обзор

Три сервиса:

* Q-Sim Service
* Q-Core Agent
* Q-Operator Console

## Протоколы

* gRPC (protobuf) для межсервисного общения
* HTTP/JSON для Operator Console (опционально)

## Наблюдаемость

* structlog/json
* trace_id
* healthz/readyz
* Prometheus metrics

## Конфиги (DSL)

* config/fsm_transitions.yaml
* config/rules.yaml
* config/degradation.yaml

\[docs/ROADMAP.md]

# ROADMAP

## M0 — Repo Sanity & CI

* M0-1 … M0-7

## M1 — Архитектура, Контракты, DSL

* M1-1 … M1-6

(далее M2+)

\----- КОНЕЦ ВСТРОЕННЫХ СКЕЛЕТОВ -----

### После завершения M0 и M1

1. Сгенерируй SUMMARY.md с перечнем выполненных PR + ссылками.
2. Предложи план M2 (Q-Sim Service MVP), M3 (Q-Core Agent MVP), M4 (Operator Console MVP) с декомпозицией задач (по 4-5 PR на сервис).
3. Предложи, как поднять покрытие тестами и верифицировать контракты (contract tests, property-based tests).

Если где-то блокируешься — опиши проблему, предложи варианты и выбери наиболее реалистичный.

```

---

Нужно что-то ещё упростить/усилить (например, добавить автоматическое создание GitHub Issues через `gh` CLI командами)? Скажи — дам версию промта с готовыми `gh issue create …` / `gh pr create …`.
