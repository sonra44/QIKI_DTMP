# QIKI Body v0.2.2 — Support Exports

Generated: 2026-06-21T04:25:01+00:00

## Что это

Это служебный слой вокруг QIKI Body v0.2.2 Documentation Package.

Он не является новым core canon.

Он нужен для репозиторной вставки, передачи агенту и согласования старого GDD.

## Файлы

- `OLD_GDD_ALIGNMENT_NOTE.md` — текст для согласования старого GDD с новым body canon.
- `AGENT_HANDOFF_QIKI_BODY_V0_2_2.md` — handoff-инструкция для Codex/Claude/агента.
- `REPO_PATCH_CHECKLIST.md` — короткий практический чеклист перед commit.
- `old_gdd_superseded_map.json` — машинная карта superseded-зон.
- `agent_handoff.json` — машинные правила для агента.
- `repo_patch_checklist.json` — машинный checklist вставки.

## Рекомендуемый путь, если класть в репозиторий

`docs/design/hardware_and_physics/qiki_body_v0_2_2/_support/`

## Граница

Этот support layer не должен менять runtime.

Не должен добавлять новые технологии.

Не должен подменять `00_INDEX.md`–`10_READER_MANUAL.md`.

Не должен объявлять implemented или verified.
