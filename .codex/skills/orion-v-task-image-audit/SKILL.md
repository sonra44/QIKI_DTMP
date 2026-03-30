---
name: orion-v-task-image-audit
description: Verify ORION V redesign work against the active task/brief, current code, and reference images before declaring a screen done. Use when the user says a redesign is not finished, asks to compare with a picture, wants proof against a task dossier, or asks for a multi-agent visual audit of F1/F2/F3/F7.
---

# ORION V Task + Image Audit

## Goal

Stop false "done" claims on ORION V redesign work.

This skill forces a three-way audit:
- task/brief requirements,
- current code or live render,
- reference image or screenshot.

Use it before declaring a redesign slice complete.

## Use when

- the user says `we did not finish F1`
- the user says `compare with the task`
- the user says `compare with the picture/image/reference`
- the user wants a proof-oriented redesign verdict instead of more polishing
- the user asks for a multi-agent audit of an ORION V screen

## Do not use when

- the task is pure backend/runtime work with no UI claim
- the request is general ORION styling with no specific acceptance disagreement

## Required invariants

- `QIKI_DTMP` project rules still apply: memory first, Docker-first, Serena-first.
- Never claim visual match from memory alone.
- If the image is not actually available to inspect, say so explicitly.
- Do not replace task acceptance with personal taste.
- Do not mark a screen done if the right lane, reading order, or density still violate the active brief.

## Read first

1. `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
2. `docs/design/operator_console/ORION_V_UI_UX_REDESIGN_TECHNICAL_ASSIGNMENT.md`
3. the most relevant current ORION task/artifact for the screen under dispute
4. `src/qiki/services/operator_console/orion_v/screens/cockpit.py` for F1

If the dispute is about another screen, read its source file before judging.

## Minimal workflow

1. State the disputed claim in one line.
   - Example: `Claim: F1 is done for Phase 1.`

2. Extract acceptance from the task/brief.
   - Write only the requirements that matter for the disputed screen.
   - For F1, usually check:
     - calmer nominal state
     - reduced prose
     - stronger hierarchy
     - action-oriented right lane
     - preserved truth-first semantics

3. Inspect the current implementation.
   - Read the actual screen source with Serena.
   - Look for residues that contradict the brief:
     - repeated detail layers
     - too many explanatory subtitles
     - prose-heavy extras
     - subsystem detail leaking into F1
     - right lane acting like a report instead of an action rail

4. Inspect the reference image if it is truly available.
   - If an attached image or usable local path is available, compare:
     - dominant layout split
     - panel hierarchy
     - visual silence in nominal state
     - how much of the screen is devoted to action vs explanation
   - If the image is not available to inspect directly:
     - state `Image proof unavailable`
     - fall back to the written redesign brief
     - do not claim visual conformance to the image

5. Run the audit in parallel when possible.
   - Sub-pass A: task/brief extraction
   - Sub-pass B: code/render residue audit
   - Sub-pass C: tooling/options for proof or screenshot comparison

6. Produce a hard verdict.
   - `Verdict: done`
   - `Verdict: not done`
   - `Verdict: blocked by missing image proof`

7. If edits are requested, change the smallest slice that closes the mismatch, then validate in Docker and checkpoint memory.

## F1-specific failure patterns

- `F1` still contains large lower diagnostics tails.
- `F1` still duplicates mission/support truth that should live in `F2/F3`.
- The right lane still reads like a secondary report.
- Detail-layer subtitles consume more attention than the operator action path.
- The screen is improved, but not yet at the `3-second mission picture` target.

## Output format

- `Claim:`
- `Task says:`
- `Current screen shows:`
- `Image says:` or `Image proof unavailable`
- `Gap:`
- `Verdict:`
- `Next smallest fix:`

Keep the verdict short and evidence-led.

## Validation after edits

Run only the smallest relevant checks first.

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_cockpit.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/screens/cockpit.py`

If the claim includes live-layout proof, add one runtime proof:
- tmux capture of live ORION V pane, or
- an existing ORION proof script that targets the disputed screen.

## Tooling notes

Read `references/tooling.md` when you need concrete methods for:
- Textual pilot/screen testing
- snapshot comparisons
- browser/screenshot visual comparisons
- image-diff helpers

## Done means

The skill is complete for a turn only when it leaves one of these outcomes:
- a proven `not done` verdict with exact gaps
- a proven `done` verdict with exact evidence
- a proven `blocked` verdict because image proof is unavailable
