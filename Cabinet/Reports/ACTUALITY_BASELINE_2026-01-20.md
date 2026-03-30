# Актуальность (baseline) — 2026-01-20

Цель: зафиксировать “что правда сейчас” по проекту, чтобы не прыгать между параллельными планами/доками.

## Канон задач

- Каноническая доска: `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md` (Last update: 2026-01-20)
- Текущий фокус: ORION Operator Console (Docker/tmux) + QIKI integration hooks + систематизация (triage untracked без второго “канона задач”).

## Факты по репозиторию (локальная рабочая копия)

- `git status --porcelain` показывает только untracked (все изменения по ORION/QIKI и чеклистам закоммичены).
- Примеры untracked на момент фиксации (требуют triage отдельными коммитами):
  - `Cabinet/` (организационный портал + отчёты по фактам)
  - `TASKS/00_INDEX.md`, `TASKS/TEMPLATE_TASK.md` (правила исполнения задач без второй доски)
  - `src/qiki/services/operator_console/tests/*` (юнит‑тесты operator_console)
  - `.pre-commit-config.yaml`

## Факты по техдолгу в коде (TODO)

По `rg "TODO|FIXME|XXX|HACK" src` найдено 2 TODO в одном файле:
- `src/qiki/services/q_core_agent/core/ship_fsm_handler.py`
  - TODO про проверку данных сенсоров
  - TODO про логику успешной стыковки

## Документы, которые уже являются “организационным слоем” (не дублировать)

- `DOCUMENTATION_UPDATE_PROTOCOL.md`
- `TASK_EXECUTION_SYSTEM.md`
- `AI_DEVELOPER_PRINCIPLES.md`
- `docs/QIKI_DTMP_METHODOLOGICAL_PRINCIPLES_V1.md`
- ORION-канон: `docs/design/operator_console/ORION_OS_VALIDATION_CHECKLIST.md`
