# Step-A Preparation — Infrastructure

Дата: 2025-09-28
Статус: IN PROGRESS (инфраструктурный инкремент завершён)
Исполнитель: Codex (CLI)

## Цель
Подготовить базовые артефакты для Step-A: расширенный BotSpec, конфигурации
пропульсивного контура, стыковки и антенн, геометрические данные.

## Выполнено
- Обновлён `BotSpec.yaml`: добавлены компоненты `docking`, `antenna_xpdr`,
  `sensor_mounts`, дополнительные каналы событийной шины.
- Добавлены конфиги:
  - `config/propulsion/thrusters.json` — 16 RCS (4×4 кластера) с нормализованными
    векторами тяги.
  - `config/power/hess.json` — параметры гибридного энергоблока.
  - `config/docking/ports.json` — две байонетные стыковки с профилями мостов.
  - `config/comms/antenna.json` — сектор антенны и режимы транспондера.
  - `config/sensors/mounts.json` — площадки сенсоров и LOS-маски.
- Заложены геометрические данные: `assets/geometry/hull_collision.json` и README
  с инструкциями по экспорту `dodecahedron.glb` и LOS карт.
- Создан `docs/STEP_A_ROADMAP.md` с фазами внедрения и DoD Step-A.

## Следующие шаги
- Реализация аллокатора тяги (QP/NNLS + PWPF) с поддержкой HESS ограничений.
- Подготовка юнит-тестов на full-rank матрицу и деградацию при отказе RCS.
- Интеграция стыковок, XPDR режимов и энергетических событий в WorldModel.

## Проверки
- `qiki_env/bin/python -m ruff check --select=E,F src tests` — PASS
- `qiki_env/bin/python -m mypy src` — PASS (известные легаси ошибки отсутсвуют)
- `qiki_env/bin/pytest -q tests/shared/test_bot_spec_validator.py` — PASS

## Документация
- Обновлены `CLAUDE_MEMORY.md`, `CONTEXT/CURRENT_STATE.md`, `IMPLEMENTATION_ROADMAP.md`
  ссылками на Step-A подготовительный этап.
