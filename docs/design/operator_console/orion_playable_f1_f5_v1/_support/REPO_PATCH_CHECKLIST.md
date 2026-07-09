# REPO_PATCH_CHECKLIST — внесение пакета (этап 0)

Docs-only коммит. Перед commit проверить:

- [ ] Все файлы пакета существуют:
      `find docs/design/operator_console/orion_playable_f1_f5_v1 -type f | sort`
      → `00_INDEX.md` … `10_RISKS_CANON_CONFLICTS.md` +
      `_support/` (handoff, clarification 001, этот чеклист).
- [ ] `git status --short` — только `A docs/design/operator_console/orion_playable_f1_f5_v1/...`,
      `M docs/INDEX.md` (+ `M docs/design/operator_console/F1_GAME_FIELD_REWORK.md`,
      если добавлена note «конкретизирован пакетом»); никаких `.py`, `.proto`,
      `.yaml`, `.toml`, generated.
- [ ] `docs/INDEX.md` содержит указатель на `00_INDEX.md` пакета.
- [ ] Статусные слова: в пакете нет `implemented`/`verified` как утверждений
      о текущем runtime (допустимы только в формулировках правил/легенды).
- [ ] Ссылки на канон валидны: G1-канон, F5-дизайн, аудит, TEMPLATE_TASK,
      qiki_body_v0_2_2 — файлы существуют по указанным путям.
- [ ] `bash scripts/check_no_second_task_board.sh` — зелёный.
- [ ] `bash scripts/check_reference_truth_boundaries.sh` — зелёный.
- [ ] Commit message: `docs: add ORION playable F1-F5 v1 documentation package`.
- [ ] После commit: следующая работа — ответ на CLARIFICATION_REQUEST_001,
      затем этап 1. Runtime-правки раньше этапа 1 запрещены.
