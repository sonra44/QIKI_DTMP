# ORION V UI UX Redesign Technical Assignment

## Goal

Redesign ORION V so it reads as a real operator console, not as a dense technical memo inside terminal frames.

The redesign must improve:

- glanceability
- hierarchy
- subsystem separation
- action relevance
- visual rhythm
- status readability

without breaking:

- truth-first runtime semantics
- Docker-first validation path
- current operator loop logic
- QIKI legality/trust/consequence meaning

## Core Problem

The current ORION V implementation already has a good console skeleton.
The main problem is visual and semantic density.

Current issues:

1. Too much prose in F1 nominal state.
2. Labels, values, and explanations visually collapse into a single mass.
3. Too many lines use the same visual weight.
4. Normal state still spends too much visual energy on explanation.
5. Right lane is useful in concept but still too wordy.
6. F2 cards are correct structurally but read more like mini-reports than operator cards.
7. F7 is technically useful but visually too close to a raw metrics dump.

## Redesign Principles

### 1. Status first

Every zone must answer in this order:

1. what is the state
2. why it matters
3. what the operator should do next

### 2. Calm nominal state

Normal state must be visually quiet.

Rules:

- neutral chrome in nominal state
- bright accents only for `WARN`, `CRIT`, active selection, or operator-required actions
- avoid “everything highlighted” syndrome

### 3. One line, one job

Inside the main screens, each line should be one of:

- status line
- fact line
- next-action line

Avoid mixed narrative lines that do two or three jobs at once.

### 4. Stable spatial memory

Keep strong named zones:

- `MISSION CONTROL STRIP`
- `SAFETY & HEALTH STRIP`
- named main panels
- `ACTION RAIL`

Do not flatten the screen into anonymous text blocks.

### 5. Short control labels

Controls should be short and operator-grade.

Prefer:

- `Power`
- `Comms`
- `Route`
- `Incidents`

Avoid:

- long bilingual button sentences
- long explanatory button labels

### 6. QIKI must be visually distinct from subsystem health

QIKI is not just another subsystem chip.
It represents recommendation, legality, trust, and operator confirmation state.

Use a distinct visual identity:

- separate color family from alarm states
- separate block semantics from power/thermal/comms chips
- no duplication of dead QIKI controls when no action is pending

## Required Visual System

## Palette

Use a restrained terminal palette.

Base:

- background:
  dark graphite / charcoal
- border:
  muted steel gray
- primary text:
  soft light gray
- secondary text:
  muted slate / cool gray

States:

- `OK`:
  cold green
- `WARN`:
  amber
- `CRIT`:
  warm red-orange
- `INFO/NAV`:
  cool cyan
- `QIKI`:
  teal / electric sea-green

Rules:

- status color is for state, not decoration
- nominal screen should remain mostly monochrome
- borders should not compete with data

## Typography Strategy For Terminal UI

Terminal does not provide real font families.
Typography must be simulated through structure.

Use:

- uppercase for strip titles and severe status words only
- short section titles
- aligned label-first lines
- explicit rhythm between blocks
- reduced bilingual duplication inside dense operational lines

Prefer:

- `COMMS | OK | 90 ms | fresh`
- `THERMAL | WARN | core 86 C | rising`
- `QIKI | HOLD | confirm required`

Avoid:

- long paragraph-like lines
- repeated English gloss on every dense line
- mixed labels and explanation in the same line

## Required Screen Changes

## F1 Bridge

Target role:
- 3-second mission picture

Required changes:

1. Reduce body text volume by at least 30 to 40 percent in nominal state.
2. Keep named sections, but shorten section subtitles or move them out of dense render areas.
3. Convert more lines into `LABEL | STATE | VALUE` format.
4. Keep right lane action-oriented:
   - next actions
   - QIKI state
   - operator intervention
   - process state
5. Hide dead confirm/cancel controls when no pending QIKI action exists.
6. Keep observation/objective facts, but compress them.

Desired F1 reading order:

1. global state
2. mission context
3. guidance
4. incident focus
5. route / target context
6. immediate action

## F2 Systems

Target role:
- decision screen by subsystem

Required changes:

1. Preserve card model.
2. Tighten each card:
   - `Status`
   - `Effect`
   - `Next`
3. De-emphasize long `Hint` text in normal state.
4. Make severity visually stronger than prose.
5. Ensure selected subsystem is much more visually obvious.

Optional future scope:
- add dedicated shields card only if gameplay/runtime truth requires it

## F3 Deep Dive

Target role:
- incident and event analysis

Required changes:

1. Stronger separation between:
   - selected incident
   - safe mode authority
   - event stream
2. Make selected incident stand out more clearly.
3. Reduce generic framing text.

## F4 Console

Target role:
- literal operator command history

Required changes:

1. Preserve literal rendering.
2. Improve readability of command/response alternation.
3. Consider stronger spacing or prefixes for request vs response vs QIKI.

## F6 Audit

Target role:
- operator action timeline

Required changes:

1. Make filter state more visible.
2. Distinguish:
   - operator commands
   - QIKI actions
   - acknowledgements
   - system events

## F7 System Health

Target role:
- runtime diagnostics

Required changes:

1. Reorganize into grouped runtime blocks:
   - transport
   - queue/store
   - procedure/ack timing
   - process health
2. Reduce plain list feeling.
3. Make abnormal metrics pop faster.

## Required Engineering Constraints

1. Do not change product meaning while redesigning visuals.
2. Do not introduce fake values or decorative demo numbers.
3. Keep named zone boundaries.
4. Keep tests aligned with the new visual contract.
5. Validate in Docker and live tmux after each meaningful pass.

## Acceptance Criteria

The redesign is acceptable only if all of the following are true:

1. F1 looks visibly different at first glance.
2. Nominal state feels calmer and less cluttered.
3. Sections are easier to scan without losing screen identity.
4. Operator can identify:
   - system state
   - mission state
   - next action
   in under a few seconds.
5. No loss of truth-first semantics.
6. No regression in current runtime screens/tests.

## Recommended Implementation Order

### Phase 1

- F1 hierarchy pass
- right lane simplification
- header and strip visual rhythm tuning

### Phase 2

- F2 systems card tightening
- stronger selected-card emphasis
- severity-to-prose rebalance

### Phase 3

- F3 / F6 / F7 cleanup
- command/audit/readability alignment

## Explicit Non-Goals

- no rewrite of ORION V runtime logic
- no new product canon in this task
- no random neon styling
- no “sci-fi skin” that weakens status readability
- no removal of named structural zones

