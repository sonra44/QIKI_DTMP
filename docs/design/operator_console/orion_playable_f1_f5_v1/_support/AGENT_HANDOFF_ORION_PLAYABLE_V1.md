# ORION Playable F1–F5 v1 — Agent Handoff

Дата: 2026-07-09

## 0. Назначение

Этот документ предназначен для CLI-агента (Codex, Claude Code, локальный
агент) или человека, который будет исполнять этапы пакета
`docs/design/operator_console/orion_playable_f1_f5_v1/`.

Это handoff-инструкция. Она не является новым каноном. Она подчинена
G1-канону и утверждённому F5-дизайну. Сама по себе она не разрешает
менять код: код меняется только в рамках этапа из `09_WORK_SEQUENCE.md`
с досье TASKS и гейтами.

## 1. Главная задача агента

Довести консоль ORION (зоны F1–F5) до состояния «playable v1» по
`01_PLAYABLE_CANON.md`, этап за этапом по `09_WORK_SEQUENCE.md`:
одна ветка `task-<id>-<slug>` = один PR = одно досье `TASKS/`.

Перед этапом 1 — ответить на `_support/CLARIFICATION_REQUEST_001.md`
(файлом `_support/CLARIFICATION_REPLY_001.md`, docs-only коммит).
Вопросы с меткой [BLOCKING] обязаны быть отвечены до старта этапа 1.

## 2. Используемые источники

- Пакет: `docs/design/operator_console/orion_playable_f1_f5_v1/` (этот).
- Аудит: `docs/dev/AUDIT_2026-07-09_GLOBAL.md`.
- Канон: `docs/design/canon/G1_QIKI_OPERATOR_LOOP_CANON.md`,
  `docs/design/operator_console/F5_QIKI_DIALOG_SYSTEM_DESIGN.md`,
  ADR-0014..0020.
- Досье-шаблон: `TASKS/TEMPLATE_TASK.md`.

## 3. Что разрешено

- Правки строго в объёме текущего этапа:
  `src/qiki/services/operator_console/**`, `src/qiki/services/q_sim_service/**`,
  `src/qiki/services/q_core_agent/**`, `src/qiki/shared/**`.
- Новые тесты, смоки `tools/orion_v_*_smoke.py`, prove-скрипты `scripts/`.
- Новые view-model-файлы по образцу `cockpit_playable_view_model.py`.
- Досье `TASKS/TASK_*.md`; обновление `CURRENT_STATE.md`, `docs/INDEX.md`,
  борда `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.
- Правка пин-теста `test_orion_f1_first_playable_loop.py` — ТОЛЬКО на
  этапах 5/9, синхронно с `03`/`06`.

## 4. Что запрещено

- Новые NATS-сабжекты, enum-значения, proto-поля без ADR.
- Автоисполнение мимо пломбы `CommandDecision`; публикация команд телу с F1.
- Фейковая телеметрия; `N/A` как штатный игровой статус; выдуманные
  числовые пороги (пороги — только `qiki/shared` / канон / расчёт).
- Удаление или ослабление m5-спуф-тестов и теста отклонения
  неспрошенных ответов.
- Декомпозиция/рефакторинг `app.py` сверх объёма этапа.
- Второй task board; смешение этапов в одной ветке.
- Заявления `implemented`/`verified` без evidence в досье.
- Правки в `F3` (глубокий анализ) в рамках v1.

## 5. Stop conditions

Остановиться и написать CLARIFICATION_REPLY/запрос оператору, если:

- quality gate красный после 2 попыток фикса;
- пин-тест требует изменения, не описанного в `03`/`06`;
- в `git status --short` файлы вне объёма текущего этапа;
- нужно выдумать числовой порог;
- дефект Блока 0 оказался уже исправлен иначе (не скипать молча);
- этап требует security-контура Д1/Д2;
- задача начала превращаться в декомпозицию app.py.

## 6. Expected paths

Пакет должен существовать по пути
`docs/design/operator_console/orion_playable_f1_f5_v1/` с файлами
`00_INDEX.md` … `10_RISKS_CANON_CONFLICTS.md` и `_support/`
(handoff, clarification, checklist). Изменяемые файлы кодовых этапов —
по таблице `09_WORK_SEQUENCE.md` и зонным спекам `03`–`06`.

## 7. Expected git status

Этап 0 (docs-only), нормальный результат:

```text
A  docs/design/operator_console/orion_playable_f1_f5_v1/...
M  docs/INDEX.md
M  docs/design/operator_console/F1_GAME_FIELD_REWORK.md
```

Кодовые этапы: только файлы из объёма этапа + `TASKS/TASK_*.md`
(+ `CURRENT_STATE.md` при изменении поведения). Плохой результат —
любые прочие `M`/`A`: остановиться (§5).

## 8. Команды проверки

```bash
find docs/design/operator_console/orion_playable_f1_f5_v1 -type f | sort
git status --short
bash scripts/branch_policy_check.sh
bash scripts/quality_gate_docker.sh
bash scripts/qiki_drift_audit.sh --strict
bash scripts/ops/anti_loop_gate.sh
# для docs-этапов:
bash scripts/check_no_second_task_board.sh
bash scripts/check_reference_truth_boundaries.sh
```

## 9. Commit message

Этап 0:

```text
docs: add ORION playable F1-F5 v1 documentation package
```

Ответ на clarification:

```text
docs: reply to orion playable clarification 001
```

Кодовые этапы — в стиле репо, со ссылкой на TASK-id в теле:

```text
fix(block0): guard attach procedure status after await
f1(radar-page): tracks table + derived approach risk
```

## 10. После commit

- Обновить досье (`## Evidence (commands → output)`), `CURRENT_STATE.md`,
  борд `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.
- Открыть PR по шаблону с секциями `## Visible Delta for Operator`,
  `## Before / After Command Transcript`, `## Impact Metric`;
  запросить `@codex review`.
- Следующий этап — только после зелёных гейтов текущего.

## 11. Главная память для агента

ACK — не подтверждение эффекта.

Canon is not implemented.

F1 наблюдает и решает — исполняет только F5-пломба.

Интент — не команда телу.

`N/A` — ошибка реализации, не игровой статус.

Пороги живут в `qiki/shared`.

Пин-тест меняется только вместе со спекой.

Молчаливый провал запрещён: любое «не получилось» видно оператору.
