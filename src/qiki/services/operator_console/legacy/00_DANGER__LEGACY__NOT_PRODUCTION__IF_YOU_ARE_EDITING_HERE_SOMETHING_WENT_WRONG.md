# ⛔ STOP — LEGACY — NOT FOR PRODUCTION

**If you are reading or editing files in this `legacy/` directory, something probably went wrong.**

This is the **old** operator-console contour. It is **not** the live console.

- The **live** operator console is **ORION V** → `src/qiki/services/operator_console/orion_v/`,
  entry point `main_orion_v.py`, container `qiki-operator-console`.
- This directory (`legacy/main_orion.py` → `main_orion.py` monolith) runs **only** under
  `docker-compose.operator_legacy.yml` (profile `legacy`, `LEGACY_MODE=1`) and prints
  `LEGACY MODE — NOT FOR PRODUCTION`.

## What to do

- Want to change "the operator console"? → go to `orion_v/`. **Not here.**
- Arrived here by a search/grep hit? → you are in the wrong contour. The full map is
  `src/qiki/services/operator_console/00_CONSOLE_MAP.md`.
- Do **not** wire this contour into the live data path, a shared compose service name,
  or the ORION V display surface. Contour mixing duplicates data → catastrophe.

Boundary enforced by `tests/structure/test_operator_console_contours.py`.
