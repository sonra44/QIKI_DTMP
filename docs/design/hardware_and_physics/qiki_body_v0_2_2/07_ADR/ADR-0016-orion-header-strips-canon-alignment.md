# ADR-0016 — ORION header strips align to MISSION CONTROL / SAFETY & HEALTH canon

## Status
Accepted.

## Date
2026-07-03

## Context
The two ORION-V header strips currently render ad-hoc, human-prose layouts that
diverge from their canon specs and mix engineering codes with Russian prose on
the primary row:

- **MISSION CONTROL STRIP** (`widgets/header.py`): shows
  `ORION V операторский контур | L: F1 Кокпит | P: … | M: … | A: operator` and
  `СВЯЗЬ … | СВЕЖ unknown | ЗАДЕРЖ n/a | ПОТЕРИ n/a | СОБЫТ N`.
  Freshness (`СВЕЖ`) reads `unknown` even under a live world (`M LIVE`,
  `СОБЫТ 280`, `СВЯЗЬ установлена`) — telemetry age is not turned into a
  freshness code.
- **SAFETY & HEALTH STRIP** (`widgets/status_bars.py`): shows
  `КР0/ПР0/ВН0 | контур nominal | риск nominal` + chips `▸ Power | NODATA`.
  `nominal`/`Power` are English words on the primary row; `риск` triple-restates
  the alert state.

Both canons (`docs/design/operator_console/MISSION_CONTROL_STRIP_CANON.md`,
`SAFETY_HEALTH_STRIP_CANON.md`) carry a **HARD language rule**: the primary strip
row uses **engineering/technical status codes only**; human/operator wording
lives in tooltip / F9 glossary / F-screens. A QA localization pass tried to
Russify `nominal`/`Power`, which is *against* this canon — hence this ADR to fix
the target, not the translation.

## Decision
Migrate both strips to their canon field contracts. The primary row is codes +
severity colour; RU/human wording moves to tooltip/F9.

### MISSION CONTROL STRIP — canonical fields
| key | label EN/RU | codes | colour | source | click | no-data |
|---|---|---|---|---|---|---|
| world | WORLD/МИР | RUN / PAUSE / STOP (+REPLAY cyan, WAIT yellow) | green/yellow/red | sim/world run-state | F7 | WAIT (never «Нет данных») |
| link | LINK/СВЯЗЬ | OK / WARN / LOST (+REPLAY) | green/yellow/red | always_on.link_status (+lat/loss) | F7 | LOST (red) |
| data | DATA/АКТУАЛ | OK / LAG / STALE / NODATA (age→tooltip) | green/yellow/red/yellow | always_on.telemetry_age_ms + derived.data_freshness_state | F7 | NODATA/STALE |
| sensors | SENS/СЕНС | OK / WARN / FAIL | green/yellow/red | derived.sensor_trust_state | F3 | raw→F3 |
| control | CTRL/УПР | SAFE / HOLD / CONFIRM / QIKI (only when != OPERATOR) | red/cyan/cyan/green | control_authority | F6 | n/a |

`data` closes the F-4b gap: telemetry_age_ms → OK/LAG/STALE/NODATA, exact age in
tooltip. SENS follows `sensor_trust_model._STATE_SEVERITY` (trusted→OK,
degraded/conflicting/blind→WARN, lottery→FAIL); the strip does not override the
model.

### SAFETY & HEALTH STRIP — canonical row
`ALRT C# W# A# · SAFE <code> · PWR <c> · THRM <c> · PROP <c> · HULL <c> · CPU <c> · QIKI <c>`
- `alerts` → label `ALRT`, `C# W# A#`; colour: crit>0 red · warn>0 yellow · else green.
- `envelope` → label `SAFE`, codes `OK / CONSTR / BREACH / SMODE`; no-data `UNKNOWN`.
- `chips` → labels `PWR/THRM/PROP/HULL/CPU/QIKI`, each `<label> <code>` (+one numeric anchor when non-nominal); colour by `chip.severity`; no-data `NODATA`.
- **CUT from primary:** `риск {mission_risk_state}` → tooltip/F3/F7; the nominal
  `Алерты: чисто | контур готов` overlay (shows only on actionable non-nominal);
  the `SENS` chip (MCS owns sensor-trust) until a distinct hardware source exists.

### Migration is phased (each phase: tested + live-verified + committed)
1. **SAFETY title**: `КР/ПР/ВН | контур nominal | риск nominal` → `ALRT C# W# A# · SAFE <code>`; cut `риск` to tooltip. (#25 core)
2. **SAFETY chips**: `Power/Thermal/…` → `PWR/THRM/PROP/HULL/CPU`; keep QIKI; cut SENS; verbose → tooltip.
3. **MCS data/freshness**: derive `data_freshness_state` from `telemetry_age_ms`, render `DATA OK/LAG/STALE/NODATA` + age tooltip. (#23 F-4b)
4. **MCS world/link/sensors/control**: replace prose header with WORLD/LINK/SENS/CTRL codes.
5. Tooltips + F9 glossary (RU expansion) + density modes (`MFD_SCALABLE_LAYOUT`).

## Rejected alternatives
- **Russify the primary row** (`nominal`→«норма», `Power`→«Питание`): violates
  the HARD language rule (strip = codes; prose in tooltip). This is why QA
  task #25 was reclassified from localization to canon-alignment.
- **Keep the ad-hoc prose header**: contradicts both strip canons and the
  single-owner rule (риск/overlay/SENS were triple-representations).
- **Build a parallel new АКТУАЛ element**: the `data`/`СВЕЖ` slot already exists;
  F-4b is "compute freshness into the existing field", not a new widget.

## Consequences
- Primary rows become code-only; operators read severity by colour, detail by
  tooltip/F-screen (keyboard parity preserved: F7/F3/F6/F2 click targets).
- Tests that asserted prose (`"риск nominal"`, `"F1 Мостик"`, chip label
  `"Power"`) migrate to the canonical codes.
- `data_freshness_state` gains a real derivation (age thresholds) shared by the
  strip; thresholds are an operator-console decision, not a telemetry-schema one.
- Human wording is not lost — it relocates to tooltip / F9 glossary, per canon.

## Related
- `MISSION_CONTROL_STRIP_CANON.md`, `SAFETY_HEALTH_STRIP_CANON.md` (design specs).
- ADR-0014 (ORION evidence station), ADR-0015 (ACK != effect confirmation).
- `06_INTERFACE_CONTROL §19` (source/freshness/trust display rules).
- QA tasks #25 (SAFETY align), #23 (F-4b freshness).
