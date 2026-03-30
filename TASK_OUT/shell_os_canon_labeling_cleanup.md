# shell_os canon labeling cleanup

Date: 2026-03-24 UTC

## Scope

Narrow terminology cleanup around `shell_os` only:
- compose notes
- code docstrings/comments
- one high-signal documentation note distinguishing ORION Shell OS from standalone `shell_os`

No rename/refactor, no UI behavior change, no ORION path change.

## Status statement

`shell_os` is:
- supported diagnostic/support shell overlay
- secondary support surface
- non-canonical operator path

It is not:
- the canonical operator surface
- a competing operator UI against ORION V
- a product-truth owner

Canonical operator surface remains:
- ORION V

## Evidence used

- Existing shell status dossier:
  - `TASK_OUT/shell_os_support_status.md`
- Existing project decision:
  - Sovereign memory decision `id=3185`
- Runtime/compose evidence:
  - `docker-compose.shell_os.yml` is a separate overlay on top of Phase1
  - `src/qiki/services/shell_os/main.py` is a small local observability/support TUI
  - supported operator path remains ORION V in current canon/runbooks

## Drift found

1. `docker-compose.shell_os.yml`
   - header said only “Shell OS overlay for Phase1 stack”, which left room to read it as a primary UI overlay
2. `src/qiki/services/shell_os/main.py`
   - service docstring did not explicitly separate standalone `shell_os` from ORION Shell OS terminology
3. `src/qiki/services/shell_os/__init__.py`
   - observability wording was correct but lacked explicit non-canonical operator boundary
4. `docs/EXPORT_SYSTEM_DOSSIER.md`
   - uses `ORION Shell OS` terminology without an explicit note separating it from standalone service `shell_os`

## Changes made

### Compose / code labeling

- `docker-compose.shell_os.yml`
  - clarified that this is the standalone `shell_os` overlay
  - explicitly marked it as support diagnostics only
  - explicitly stated: not ORION V, not canonical operator path

- `src/qiki/services/shell_os/main.py`
  - docstring now says standalone `shell_os`
  - explicitly marks it as supported diagnostic/support overlay only
  - explicitly says it is not ORION V and not a competing operator UI

- `src/qiki/services/shell_os/__init__.py`
  - added concise boundary statement:
    - support overlay only
    - not ORION V
    - not canonical operator path

### Docs terminology split

- `docs/EXPORT_SYSTEM_DOSSIER.md`
  - added a terminology note:
    - `ORION Shell OS` = canonical ORION V operator surface
    - standalone `shell_os` = separate diagnostic/support overlay

## Runtime behavior

No runtime behavior changed.

Unchanged:
- service/container name and artifacts
- launch command
- overlay usage pattern
- UI structure and behavior

## Minimal verification

This task was labeling-only; no runtime semantics were touched.

Recommended narrow verification:
- `docker compose -f docker-compose.phase1.yml -f docker-compose.shell_os.yml config`
- optional existing shell_os test slice if needed later

## Done check

- `shell_os` no longer hangs in an ambiguous status in touched files
- docs/comments distinguish ORION Shell OS from standalone `shell_os`
- runtime behavior remains unchanged
