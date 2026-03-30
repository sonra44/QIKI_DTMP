# TASK: Docs audit — radar visualization conflicts + canon strategy

Date: 2026-02-04  
Scope: documentation only (no code changes)  
Source of truth for this audit: **git tracked files** (git history is truth)

## Goal

1) Find documentation conflicts (“parity of canon”) related to radar visualization and operator-console plans.
2) Explain: “we planned to implement it like X because it’s reflected in doc A; doc B proposes Y; we choose X/Y because …”.
3) Fix the root cause by creating a **canonical RFC + ADR** (see “Result”).

## Method

- Only tracked markdown files are considered evidence.
- Untracked local transcripts (e.g. black-box logs) are excluded from “truth”, but may be treated as external context.
- Conflicts are evaluated against the real operator environment: **SSH → tmux → multiple terminals**.

## Result (canon artifacts created)

- RFC: `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`
- ADR: `docs/design/canon/ADR/ADR_2026-02-04_radar_visualization_strategy.md`

## Conflict table (meaning-level)

| Topic / question | Canon statement (doc) | Competing statement (doc) | Why it’s a problem | Decision | Rationale |
|---|---|---|---|---|---|
| Terminal graphics: do we assume Kitty/SIXEL works? | Baseline policy focuses on what is real now and includes `Radar PPI (ASCII)` as the current visualization: `docs/operator_console/REAL_DATA_MATRIX.md` | “Verified approach” claims Sixel via `textual-image` is the right integration path: `docs/design/operator_console/TDE_DESIGN_ORION.md` | Without an explicit environment policy, these read as mutually exclusive: “ASCII-only now” vs “Sixel is verified” | Adopt a multi-backend strategy with a mandatory baseline | Real environment is SSH+tmux; bitmap protocols may fail; we need an always-visible mode and a best-effort upgrade. Canonized in ADR+RFC. |
| Is web visualization an option? | No web radar (terminal-first project): RFC + ADR | A backlog doc suggests web panels as an option: `docs/radar_summary/README.md` | If not clarified, this can send the project into a second UI track | Web sidecar is out of scope | Explicitly excluded in RFC/ADR; terminal remains the cockpit. |
| “3D radar” vs practical terminal views | Canonized: 3D truth data + 2D views (Top/Side/Front) with optional ISO: `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md` | Some documents talk about “3D visualization” without locking the view model (various roadmap/backlog text) | Endless redesign risk: no decision on what “3D” means in a terminal | Fix the space model | 3D truth + multiple 2D projections is decision-complete and debuggable; ISO is optional future. |
| Operator console plan: NATS/Textual-first vs gRPC panels | ORION canon is NATS/Textual-first and lives under `docs/design/operator_console/` | Alternate/legacy plan proposes Warp agent mode + gRPC panels: `docs/agents/operator_console_new_plan.md` | If treated as canon, it creates a second console track | Keep it reference-only | That doc is already labeled as alternate/legacy; no ADR is needed unless we explicitly revive it. |

## Follow-up actions (future work; not done in this task)

1) DONE: `docs/operator_console/REAL_DATA_MATRIX.md` now references the radar visualization RFC/ADR and clarifies baseline vs future.
2) DONE: `docs/design/operator_console/TDE_DESIGN_ORION.md` now includes a status note pointing to RFC/ADR to avoid canon ambiguity.
3) TODO (future): add a short doc section describing tmux/SSH limitations for Kitty/SIXEL and how we detect capabilities.
