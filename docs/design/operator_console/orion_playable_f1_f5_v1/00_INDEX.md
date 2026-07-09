# ORION Playable F1–F5 v1 — Documentation Package

Статус пакета: **target spec / documentation package** (не канон, не runtime-задача).
Дата: 2026-07-09
Автор: web-агент (Claude, облачная сессия), по решению оператора.
Получатель: CLI-агент (Codex / Claude Code, локальная машина).

Canon is not implemented. Ни один документ пакета не заявляет `implemented`
или `verified`: любое такое заявление возможно только после исполнения этапа
из `09_WORK_SEQUENCE.md` с evidence в досье `TASKS/`.

## Назначение

Пакет — утверждаемая конкретизация предложения
`docs/design/operator_console/F1_GAME_FIELD_REWORK.md` плюс обязательный
дефектный базис из `docs/dev/AUDIT_2026-07-09_GLOBAL.md`. Цель: довести
консоль оператора ORION (зоны F1–F5) до состояния «playable v1» по
определению `01_PLAYABLE_CANON.md`.

## Подчинение канону

Пакет подчинён (при конфликте канон побеждает):

1. `docs/design/canon/G1_QIKI_OPERATOR_LOOP_CANON.md` — игровой цикл
   «Наблюдение → Запрос/Команда QIKI → Legality/Trust → Consequence».
2. `docs/design/operator_console/F5_QIKI_DIALOG_SYSTEM_DESIGN.md`
   (утверждён оператором) — CaMeL-граница, 4 сущности, лестница исполнения.
3. ADR-0014..0020, `docs/design/operator_console/DISPLAY_CANON.md`.
4. QIKI Body v0.2.2 (`docs/design/hardware_and_physics/qiki_body_v0_2_2/`).

## Порядок чтения

| # | Документ | Что это |
|---|----------|---------|
| 01 | `01_PLAYABLE_CANON.md` | Определение «playable v1»: 5 проверяемых критериев |
| 02 | `02_BLOCK0_DEFECT_BASELINE.md` | Блок 0: обязательные фиксы аудита 2026-07-09 (in/out scope) |
| 03 | `03_F1_COCKPIT_SPEC.md` | F1 по зонам Z1–Z9: текущее → целевое |
| 04 | `04_F2_F3_F4_ZONES_SPEC.md` | F2/F3/F4: минимальные обязательные изменения |
| 05 | `05_F5_QIKI_DIALOG_SPEC.md` | F5: дельта к утверждённому дизайну + контекстный вход с F1 |
| 06 | `06_COMMAND_SURFACE_CONTROL_PATH.md` | Центральное решение: путь команды, клавиши |
| 07 | `07_ACCEPTANCE_CRITERIA.md` | Приёмка по зонам в формате anti-loop gate |
| 08 | `08_VERIFICATION_PLAN.md` | Тесты, смоки, quality gate, 30-мин runtime smoke |
| 09 | `09_WORK_SEQUENCE.md` | Этапы для CLI-агента: 1 этап = 1 ветка = 1 PR |
| 10 | `10_RISKS_CANON_CONFLICTS.md` | Риски R1–R6 и протокольные обязательства |

Поддержка (`_support/`):

- `AGENT_HANDOFF_ORION_PLAYABLE_V1.md` — handoff-инструкция CLI-агенту.
- `CLARIFICATION_REQUEST_001.md` — вопросы Q1–Q9 CLI-агенту, конвенция ответа.
- `REPO_PATCH_CHECKLIST.md` — чеклист внесения docs-only коммита.

## Приоритет источников внутри пакета

`01 > 02 > 03/04/05 > 06 > 07/08/09`; `10` — риски, читается всегда.
При противоречии между зонными спеками и `06` — побеждает `06`
(центральное решение о пути команды).

## Легенда статусов (перенос из QIKI Body v0.2.2 §4)

- **canon** — принято как правило; не означает наличие в runtime.
- **target-only** — целевое состояние, источник данных ещё не существует.
- **implemented-требует-evidence** — заявлять можно только с командой
  воспроизведения и записанным выводом в досье `TASKS/`.

## Решения по форме пакета

- `_json/`-компаньон **не делается**: у QIKI Body он обслуживал RAG-инжест;
  для рабочей спеки это оверхед. Machine-readable слой — не цель пакета.
- Отметка «конкретизирован пакетом» в `F1_GAME_FIELD_REWORK.md` вносится
  CLI-агентом на этапе 0 (см. `09_WORK_SEQUENCE.md`), не этим коммитом.

## Trust note

Пакет составлен по состоянию репозитория на коммит `64dbe0c`
(«Глобальный код-аудит 2026-07-09») плюс незакоммиченное рабочее дерево
(«блок 1», см. `_support/CLARIFICATION_REQUEST_001.md`, Q1). Все file:line
проверялись на этом срезе; при дрейфе строк искать по якорным идентификаторам
(имена функций/констант), а не по номерам.
