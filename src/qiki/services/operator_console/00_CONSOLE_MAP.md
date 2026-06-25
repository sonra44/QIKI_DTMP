# 00 — OPERATOR CONSOLE MAP — READ THIS FIRST

> Single source of truth for **which operator console is which**.
> Purpose: a fresh agent (even after full memory loss) must, from this file alone,
> never confuse the LIVE operator console with a legacy/archive contour.
> Enforced by `tests/structure/test_operator_console_contours.py`.

## The ONE live console

**ORION V is THE operator console (LIVE / PRODUCTION).**

**LIVE_CONSOLE:** ORION V — `orion_v/` — `main_orion_v.py`  <!-- exactly one; machine-checked -->

| | |
|---|---|
| Code | `src/qiki/services/operator_console/orion_v/` (`OrionVApp`) |
| Entry point | `src/qiki/services/operator_console/main_orion_v.py` |
| Runtime | container `qiki-operator-console`, `command: python main_orion_v.py` |
| Launched by | `docker-compose.yml`, `docker-compose.operator.yml` |

If you change "the operator console", you change **ORION V**. Nothing else.

## Every other contour (NOT the live console)

| Contour | Path / entry | Class | Notes |
|---|---|---|---|
| **Legacy ORION (monolith)** | `main_orion.py` (~440 KB, `OrionApp`) | LEGACY | old contour, NOT production |
| **Legacy launcher** | `legacy/main_orion.py` | LEGACY | prints `LEGACY MODE — NOT FOR PRODUCTION`; only via `docker-compose.operator_legacy.yml`, profile `legacy`, `LEGACY_MODE=1` |
| **Archive entrypoint** | `main.py` | ARCHIVE | requires `ALLOW_LEGACY_OPERATOR_CONSOLE=1`; not production |
| **Prototypes** | `main_full.py`, `main_enhanced.py`, `main_integrated.py`, `main_live.py` | DEAD / PROTOTYPE (manual-only) | old Rich prototypes, 0 compose references; manually runnable via `__main__` — **NOT** assumed safe to delete without a test/import inventory |
| **shell_os** | `qiki.services.shell_os.main` | SEPARATE | support surface, not ORION V |

## Hard rules (never break)

1. **ORION V ≠ legacy.** They are two independent code contours: `orion_v/` does **not** import `main_orion`/`legacy`; the dependency runs the other way (legacy imports the monolith).
2. **Never label `orion_v/` (app.py / screens / collector) "legacy."** The internal architecture choice "evidence projection via `*_evidence.py`, not extending `collector.build_*`" (route a) is an improvement **inside ORION V** — it is NOT a legacy boundary.
3. **No contour mixing.** Do not let legacy and the live console share a compose service name, a data path, or a display surface. Contour confusion duplicates data → catastrophe.
4. The machine guards in `tests/structure/test_operator_console_contours.py` enforce 1–3. If that test is red, the boundary is at risk — fix the boundary, do not weaken the test.
