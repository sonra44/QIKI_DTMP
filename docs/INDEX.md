# QIKI_DTMP — индекс документации (порядок чтения)

Цель: быстро понять, что QIKI_DTMP — это симулятор и операторская платформа, где “истина мира” идёт из симуляции, а не из UI.

## Актуальный срез (2026-02-09)

- Текущая активная работа по ORION startup readability и anti-loop guardrails:
  - `TASKS/TASK_20260210_orion_telemetry_semantic_panels_tierA.md`
  - `TASKS/ARTIFACT_20260210_orion_summary_weekly_before_after.md`
  - `TASKS/TASK_20260209_antiloop_guardrails.md`
- Операционные правила anti-loop:
  - `docs/ops/ANTI_LOOP_POLICY.md`
  - `scripts/ops/anti_loop_gate.sh`
- Если нужно быстро понять “где мы сейчас”:
  - сначала `README.md` (что это за симулятор, как поднять и проверить),
  - затем блок задач выше (текущий execution slice и доказательства).

## 1) Must-read (войти в контекст за 30–60 мин)

1. `README.md` — что это за симулятор, quick start, quality gate.
2. `docs/ARCHITECTURE.md` — контейнеры, dataflow, Radar LR/SR, health/readiness.
3. `START_HERE_FOR_CONTEXT.md` — быстрый маршрут по проекту.
4. `docs/NEW_QIKI_PLATFORM_DESIGN.md` — продуктовые принципы и направление.
5. `docs/operator_console/REAL_DATA_MATRIX.md` — no-mocks матрица реальных данных в ORION.

## 2) Should-read (углубление, 1–3 часа)

9. `CONTEXT/CURRENT_STATE.md` — архивный срез (2025-09-27); актуальный snapshot — `CURRENT_STATE.md`.
10. `CURRENT_STATE.md` — актуальный snapshot (не канон приоритетов; сверять с ним).
11. `docs/CONTRACT_POLICY.md` — правила эволюции контрактов (proto/gRPC/NATS/AsyncAPI).
12. `docs/design/q-core-agent/bios_design.md` — концепт BIOS/POST (низкий уровень vs FSM).
13. `docs/design/q-core-agent/proposal_evaluator.md` — как выбираются предложения (приоритет/уверенность).
14. `docs/radar_phase2_roadmap.md` — куда развивается радар после v1.
15. `docs/STEP_A_ROADMAP.md` — Step-A (propulsion/energy/docking) — если обсуждаем “бортовые подсистемы”.
16. `docs/operator_console/REAL_DATA_MATRIX.md` — что Operator Console показывает и откуда.

## 3) Радар и безопасность (читать по задаче)

- `src/qiki/resources/radar/guard_rules.yaml` — guard rules (триггеры безопасности → события/FSM).
- `LOG_ANALYSIS_2025-09-22.md` / `DEEP_DATA_ANALYSIS_2025-09-22.md` / `DEEP_CODE_ANALYSIS_2025-09-22.md` — глубокие разборы (когда нужно спорить фактами).
- Radar visualization canon:
  - `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`
  - `docs/design/canon/ADR/ADR_2026-02-04_radar_visualization_strategy.md`

## 4) История, аудит и “не переанализировать”

- `PALTCR_SESSION_2025-09-22_15-30.md` — “что уже доказано/понято” и что повторно не копать.
- `CLAUDE_MEMORY.md` — накопленная память и эволюция решений.
- `DOCUMENTATION_UPDATE_PROTOCOL.md` — как обновлять документацию (если вносим изменения).
- `docs/agents/context_persistence.md` — протокол “контекст не потеряется” (skills/backup/restore).

## 5) Планирование и задачи

- Канон приоритетов: `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Задачи по исполнению (dossier): `TASKS/`
- Исторические справки (не канон): `TASK_LIST.md`, `TASK_DETAILS.md`, `UPDATED_PRIORITIES_2025.md`

## 6) Много документов: как не утонуть

В репозитории есть большие “архивные” массивы:
- `roadmap/` и `analysis/` — автоген/аналитические файлы (обычно читать точечно).
- `TASKS/` — история тасков и ретро-планы.
- `journal/` — журналы работ по датам.

Рекомендация: сначала пройти `Must-read`, затем выбирать “Should-read” по текущей теме (UI, радар, Step-A, QoS и т.д.).
