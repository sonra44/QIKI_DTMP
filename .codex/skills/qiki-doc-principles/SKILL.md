---
name: qiki-doc-principles
description: Documentation/principles truth gate for QIKI_DTMP. Use when changing board, dossiers, artifacts, canons, ADR-adjacent docs, or when auditing whether docs still match product truth, evidence, and current execution slice.
---

# QIKI_DTMP — Documentation & Principles Truth Gate

## Goal

Не давать документам и “принципам работы” убегать вперёд или в сторону от фактов.

Этот skill нужен для изменений в:
- `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- `TASKS/TASK_*.md`
- `TASKS/ARTIFACT_*.md`
- `docs/design/canon/**`
- `docs/INDEX.md`, `docs/ORION_V_RUNBOOK.md`, `docs/RESTART_CHECKLIST.md`
- bootstrap / protocol / operational docs

## Use when

- пользователь просит обновить docs / board / dossier / artifact
- пользователь просит критический аудит документального состояния
- меняется поведение, контракт, execution slice или operational path
- есть риск drift между кодом, evidence и текстом

## Procedure

1) Определи режим:
   - если задача про продукт/канон/board/dossier -> `project mode`
   - если задача про host/tmux/systemd/docker/MCP -> сначала `ops mode`, затем только при необходимости возвращайся к docs

2) Подними truth sources:
   - `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
   - текущий `TASKS/TASK_*.md`
   - связанный `TASKS/ARTIFACT_*.md`
   - нужный ADR / canon
   - последние `STATUS / TODO_NEXT / DECISIONS`

3) Проверь 5 обязательных соответствий:
   - board header и `Now` совпадают с реальным execution slice
   - dossier status/DoD совпадают с фактическим proof
   - artifact не утверждает больше, чем доказано командами/логами/тестами
   - operational paths совпадают с текущим каноном запуска
   - product wording не скатывается из sim-game/QIKI/operator truth обратно в vague “platform” язык

4) Проверь принципы:
   - no second source of truth
   - no demo/random mission data
   - no `v2`/duplicate contracts
   - docs-as-code: поведение меняется -> docs sync обязателен
   - ADR/MADR: если решение становится долгоживущим architectural rule, оно должно быть либо в ADR, либо в `DECISIONS`, а не только в prose

5) Выдай результат в формате:
   - `Mismatch:` что расходится
   - `Risk:` почему это опасно
   - `Fix:` минимальная правка

6) Если пользователь просит применить изменения:
   - сначала правь самые верхние truth-entrypoints:
     - board
     - active dossier
     - acceptance artifact
   - потом уже secondary docs

7) После правок обязательно:
   - сохранить `STATUS`
   - сохранить `TODO_NEXT`
   - сохранить `DECISIONS` если появилось новое долгоживущее правило
   - сделать recall-proof с ID

## Rules

- Не создавать второй канон вместо починки существующего.
- Не писать `PASS`, если canonical proof не зелёный.
- Не расширять mission scope в документах раньше, чем появился новый dossier.
- Если live proof использует другой идентификатор, чем operator scenario, это нужно явно нормализовать в тексте.
- Если board header устарел, это не “косметика”, а drift entrypoint’а.

## Output

Короткий результат должен отвечать на 4 вопроса:
- что сейчас истинно
- что задокументировано неверно
- что нужно исправить первым
- какой один следующий документальный или продуктовый шаг остаётся после sync
