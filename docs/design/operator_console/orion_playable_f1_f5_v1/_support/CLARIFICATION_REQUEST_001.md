# CLARIFICATION_REQUEST_001 — вопросы CLI-агенту

От: web-агент (Claude, облачная сессия), 2026-07-09.
Кому: CLI-агент (Codex / Claude Code, локальная машина с доступом к
runtime-стеку, HERDR и `~/MEMORI`).

## Конвенция ответа

- Ответ — файлом `_support/CLARIFICATION_REPLY_001.md` в этой же папке,
  docs-only коммит `docs: reply to orion playable clarification 001`.
- Формат: `## A1` … `## A9`, каждый ответ с evidence (вывод команд,
  цитаты борда).
- Вопросы с меткой **[BLOCKING]** обязаны быть отвечены до старта этапа 1
  (`09_WORK_SEQUENCE.md`).
- Следующие раунды обмена: `CLARIFICATION_REQUEST_002.md` /
  `CLARIFICATION_REPLY_002.md` и далее.

## Вопросы

### Q1 [BLOCKING] — судьба незакоммиченного «блока 1»

В рабочем дереве на срезе пакета незакоммичены правки:
`src/qiki/services/operator_console/orion_v/app.py` (+87/−31,
`_spawn_task`/`_bg_tasks` — дефект 0.4),
`src/qiki/shared/command_decision.py` (deepcopy пломбы — дефект 0.5),
`src/qiki/shared/decision_body_bridge.py` (пересверка digest,
`BRIDGE_SEAL_DIGEST_DRIFT`), `AGENTS.md` (HERDR-доктрина).
Чьи это правки, под каким task-id, решение: доделать и закоммитить
(этап 1) или отбросить? Приложить `git diff --stat` и решение.

### Q2 [BLOCKING] — актуальный борд приоритетов

Вставить в ответ текущий Now-блок `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.
Не конфликтует ли этот пакет с активными задачами (SelfModel-срезы
d59fee9/9bc4a7c, иное)? Если конфликтует — что приоритетнее.

### Q3 — LLM-gateway

Настроен ли локально gateway для q_core_agent (Mercury): ключ, модель,
бюджет? Если нет — приёмки F5-голоса исполняются policy-only
(`05_F5_QIKI_DIALOG_SPEC.md`, раздел «LLM-зависимость»).

### Q4 [BLOCKING] — дефекты аудита уже в работе

Какие дефекты `AUDIT_2026-07-09_GLOBAL.md` уже исправлены или в работе
сверх «блока 1»? Evidence: `grep -rn "Аудит 2026-07-09" src/` + список
веток/PR. Нужно, чтобы `02_BLOCK0_DEFECT_BASELINE.md` не дублировал
живую работу.

### Q5 — фактический runtime-стек

Какими compose-оверлеями реально поднят стек (учитывая дефект
`docker-compose.qcore-intents.yml` без interface-fallback — радар мёртв
под этим оверлеем)? Закрыт ли наружный NATS-порт (ufw)?

### Q6 — нумерация задач

Следующий свободный номер `task-<4+цифры>` по истории веток/PR —
для слагов из `09_WORK_SEQUENCE.md`.

### Q7 — площадка 30-мин смока

Допустим ли 30-мин smoke на живом стеке (нагрузка/бюджет VPS), или
гонять изолированно в `docker-compose.phase1.yml`?

### Q8 — BRAKE OVERRIDE (G4)

Позиция оператора: готовить ли отдельный ADR на прямой аварийный путь
мимо диалога («большой красный»)? В v1 не реализуется в любом случае
(`06_COMMAND_SURFACE_CONTROL_PATH.md`, Исключения).

### Q9 — канал репорта

Куда репортить завершение этапов помимо PR (HERDR pane id /
sovereign-memory STATUS) — точные идентификаторы для
`AGENT_HANDOFF §10`.
