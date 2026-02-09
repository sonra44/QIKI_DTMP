# TASK (placeholder restored for canon evidence link integrity)

**ID:** TASK_20260127_ORION_UI_INPUT_NO_SILENT  
**Status:** needs_verification  
**Date restored:** 2026-02-09  

## Why this file exists

`~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md` referenced this dossier as evidence, but it was missing in the repository tree at the time of the 2026-02-09 audit.
This placeholder restores the link target without claiming the underlying behavior is implemented in the current `main`.

## Verification note (must do before treating as 'done')

Run a code-backed verification for this claim (Docker-first where applicable).
Examples of safe checks:
- locate implementation: `rg -n "<expected token>" src`
- locate tests: `rg -n "TASK_20260127_orion_ui_input_no_silent" -S tests TASKS`
- confirm no silent-swallow patterns (if relevant): `rg -U -n "except Exception:\\s*\\n\\s*pass" <area>`

## Next

1) Replace this placeholder with a real dossier (template sections + Docker-first evidence).
2) Update the canon board entry to point at the verified evidence (commit/tests/output).
