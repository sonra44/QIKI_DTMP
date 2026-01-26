# QIKI_DTMP — индекс документации (порядок чтения)

Цель: быстро понять **что такое QIKI**, зачем создаётся бот, как он управляется и где искать детали (без “утонуть” в сотнях файлов).

## 1) Must-read (концепция и смысл, 30–60 мин)

1. `START_HERE_FOR_CONTEXT.md` — “куда смотреть вначале”.
2. `docs/NEW_QIKI_PLATFORM_DESIGN.md` — зачем платформа и какие принципы (“суперплан”).
3. `README.md` — как поднять Phase1 и что считается рабочим стеком.
4. `docs/ARCHITECTURE.md` — фактическая архитектура Phase1 и потоки данных.
5. `docs/design/q-core-agent/neuro_hybrid_core_design.md` — что такое Q-Mind (Rule+Neural+Arbiter) и почему “мозг” устроен так.
6. `docs/design/q-core-agent/bot_core_design.ru.md` — что считается “ботом” как сущностью (ID, конфиг, raw I/O).
7. `docs/design/hardware_and_physics/bot_physical_specs_design.md` — физический контракт (что “железо” означает в Digital Twin).
8. `docs/design/game/qiki_operator_lore_notes.md` — текущие зафиксированные тезисы по лору “QIKI ↔ оператор”.

## 2) Should-read (как реально работает поведение/безопасность, 1–3 часа)

9. `CONTEXT/CURRENT_STATE.md` — архивный срез (2025-09-27); актуальный snapshot — `CURRENT_STATE.md`.
10. `CURRENT_STATE.md` — актуальный snapshot (не канон приоритетов; сверять с ним).
11. `docs/CONTRACT_POLICY.md` — правила эволюции контрактов (proto/gRPC/NATS/AsyncAPI).
12. `docs/design/q-core-agent/bios_design.md` — концепт BIOS/POST (низкий уровень vs FSM).
13. `docs/design/q-core-agent/proposal_evaluator.md` — как выбираются предложения (приоритет/уверенность).
14. `docs/radar_phase2_roadmap.md` — куда развивается радар после v1.
15. `docs/STEP_A_ROADMAP.md` — Step-A (propulsion/energy/docking) — если обсуждаем “бортовые подсистемы”.
16. `docs/operator_console/REAL_DATA_MATRIX.md` — что Operator Console показывает и откуда (политика no-mocks).

## 3) Радар и безопасность (читать по задаче)

- `src/qiki/resources/radar/guard_rules.yaml` — guard rules (триггеры безопасности → события/FSM).
- `LOG_ANALYSIS_2025-09-22.md` / `DEEP_DATA_ANALYSIS_2025-09-22.md` / `DEEP_CODE_ANALYSIS_2025-09-22.md` — глубокие разборы (когда нужно спорить фактами).

## 4) История, аудит и “не переанализировать”

- `PALTCR_SESSION_2025-09-22_15-30.md` — “что уже доказано/понято” и что повторно не копать.
- `CLAUDE_MEMORY.md` — накопленная память и эволюция решений.
- `DOCUMENTATION_UPDATE_PROTOCOL.md` — как обновлять документацию (если вносим изменения).

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
