# Skills Analysis

> REFERENCE / INSTALL INVENTORY ONLY
>
> This analysis describes the repo-local skill inventory under `QIKI_DTMP/.codex/skills`.
> It must not be treated as an active runtime authority, a sovereign-memory substitute, or a canon/status source.
> Use it only to understand project skill layout and overlap; use `~/.codex`, sovereign-memory, the active board, and current repo/runtime evidence for live execution truth.

Generated: 2026-03-29
Project focus: `QIKI_DTMP`

## Method

For each installed active skill, this audit classifies:

- `Implementation`
  - `rich`: `SKILL.md` plus scripts/references/assets or other support files
  - `guided`: meaningful `SKILL.md` plus references or substantial structure
  - `lightweight`: `SKILL.md` only, but still usable as a workflow constraint
- `Current relevance`
  - `high`: directly useful now for QIKI_DTMP execution loops
  - `medium`: useful in regular work, but not on every loop
  - `low`: specialized or unrelated unless explicitly requested

`OneContext` is excluded from the active inventory because it was disabled.

## Project Skills

- `context-persistence-health`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Useful for persistence forensics, but partially overlaps with `sovmem-health`. Keep only if you still care about context survivability audits beyond normal memory proof.

- `orion-operator-smoke`
  Implementation: `lightweight`
  Relevance: `high`
  Assessment: Strong fit for current ORION V work. It matches the project's Docker-first and Textual-first verification model.

- `orion-v-task-image-audit`
  Implementation: `guided`
  Relevance: `high`
  Assessment: Directly relevant to the current F1/F2 redesign loop because it ties visual claims to task brief plus reference images.

- `orion-v-top-zone-redesign`
  Implementation: `guided`
  Relevance: `medium`
  Assessment: Still useful, but only when work is explicitly in the top chrome/header/action zone. Not a general ORION redesign skill.

- `orion-v-ui-redesign`
  Implementation: `lightweight`
  Relevance: `high`
  Assessment: Good umbrella workflow for ORION UX cleanup. It remains relevant as the generic redesign guardrail.

- `qiki-bootstrap`
  Implementation: `lightweight`
  Relevance: `high`
  Assessment: Essential for current project startup discipline. Keep active.

- `qiki-checkpoint`
  Implementation: `lightweight`
  Relevance: `high`
  Assessment: Highly relevant because the project explicitly requires memory proof and closeout discipline.

- `qiki-doc-principles`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Useful whenever canons, dossiers, or reports move. Not mandatory for every code-only loop, but important in this repo.

- `qiki-drift-audit`
  Implementation: `lightweight`
  Relevance: `high`
  Assessment: High value because QIKI_DTMP is canon-heavy and drift-prone. Keep active.

- `qiki-intent-ownership-guardian`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Niche but important for command/intention-path changes. Relevant only when touching QIKI intent ownership.

- `qiki-record-replay-analyst`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Useful for incident reproduction and truth-path verification. Not needed every day, but valuable.

- `qiki-runtime-contour-verifier`
  Implementation: `lightweight`
  Relevance: `high`
  Assessment: One of the most practically useful QIKI skills because runtime contour confusion is a recurring failure mode.

- `qiki-sensor-plane-auditor`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Good specialized audit skill for telemetry/sensor truth questions. Useful but not universal.

- `sovmem-health`
  Implementation: `lightweight`
  Relevance: `high`
  Assessment: Still relevant because memory proof is part of the operating protocol. Strong overlap with `context-persistence-health`; for normal loops this one is the simpler default.

## Global Skills

- `commit-work`
  Implementation: `guided`
  Relevance: `medium`
  Assessment: Good general-purpose commit skill. Relevant when the user explicitly asks to commit or stage.

- `context-persistence-health`
  Implementation: `lightweight`
  Relevance: `low`
  Assessment: Redundant with the project-local copy and with `sovmem-health`. In QIKI_DTMP the project-local or narrower health path is more relevant.

- `futura-design-system`
  Implementation: `lightweight`
  Relevance: `low`
  Assessment: Not relevant to current QIKI_DTMP ORION work unless the project shifts toward FUTURA portal design.

- `futura-vpn-portal`
  Implementation: `lightweight`
  Relevance: `low`
  Assessment: Unrelated to current project.

- `gh-address-comments`
  Implementation: `rich`
  Relevance: `medium`
  Assessment: Useful when fixing PR comments. Not currently central, but clearly implemented.

- `gh-fix-ci`
  Implementation: `rich`
  Relevance: `medium`
  Assessment: Useful when CI breaks. Not part of the current ORION loop.

- `notion-knowledge-capture`
  Implementation: `guided`
  Relevance: `low`
  Assessment: Only relevant when documentation is being pushed into Notion.

- `notion-meeting-intelligence`
  Implementation: `guided`
  Relevance: `low`
  Assessment: Unrelated to current code/runtime work.

- `notion-research-documentation`
  Implementation: `guided`
  Relevance: `low`
  Assessment: Useful only for Notion-heavy research tasks.

- `notion-spec-to-implementation`
  Implementation: `guided`
  Relevance: `low`
  Assessment: Useful if QIKI planning moves into Notion; otherwise dormant.

- `orion-operator-smoke`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Good reusable skill, but duplicated by the project-local version. Prefer the project-local one inside QIKI_DTMP.

- `qiki-bootstrap`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Duplicated by the project-local version. Prefer local.

- `qiki-canon-passport`
  Implementation: `guided`
  Relevance: `medium`
  Assessment: Strong specialized analysis skill with supporting references. Useful when you need subsystem passports, not for routine execution.

- `qiki-checkpoint`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Duplicated by the project-local version. Prefer local.

- `qiki-command-policy-map`
  Implementation: `guided`
  Relevance: `medium`
  Assessment: Valuable when analyzing legality and command path ownership. Not always needed, but definitely meaningful.

- `qiki-drift-audit`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Duplicated by the project-local version. Prefer local.

- `qiki-legacy-split-audit`
  Implementation: `guided`
  Relevance: `medium`
  Assessment: Useful for deliberate legacy cleanup. Not on the current critical path.

- `qiki-provenance-map`
  Implementation: `guided`
  Relevance: `medium`
  Assessment: Useful for truth-source tracing. Relevant when payload/field provenance becomes the task.

- `reducing-entropy`
  Implementation: `guided`
  Relevance: `low`
  Assessment: Explicitly opt-in. Not relevant unless user asks for deletion/minification work.

- `security-best-practices`
  Implementation: `guided`
  Relevance: `low`
  Assessment: Relevant only for explicit security review requests.

- `security-ownership-map`
  Implementation: `rich`
  Relevance: `low`
  Assessment: Strong implementation, but very specialized and not currently relevant.

- `security-threat-model`
  Implementation: `guided`
  Relevance: `low`
  Assessment: Useful only for explicit AppSec work.

- `session-handoff`
  Implementation: `rich`
  Relevance: `medium`
  Assessment: Very useful for long QIKI sessions and probably one of the better-maintained global skills.

- `sovmem-health`
  Implementation: `lightweight`
  Relevance: `medium`
  Assessment: Duplicated by the project-local version. Prefer local in QIKI_DTMP.

- `space-sim-builder`
  Implementation: `rich`
  Relevance: `medium`
  Assessment: Broadly relevant to a space-sim project, but more useful for simulator architecture changes than for current ORION F1 work.

- `writing-clearly-and-concisely`
  Implementation: `guided`
  Relevance: `medium`
  Assessment: Useful whenever writing docs, reports, UI wording, or task artifacts.

## Consolidated Recommendations

- Prefer project-local versions when a skill exists in both scopes:
  `context-persistence-health`, `orion-operator-smoke`, `qiki-bootstrap`, `qiki-checkpoint`, `qiki-drift-audit`, `sovmem-health`
- Keep active and current for QIKI_DTMP:
  `qiki-bootstrap`, `qiki-checkpoint`, `qiki-drift-audit`, `qiki-runtime-contour-verifier`, `orion-operator-smoke`, `orion-v-task-image-audit`, `orion-v-ui-redesign`
- Keep active but situational:
  `qiki-doc-principles`, `qiki-record-replay-analyst`, `qiki-sensor-plane-auditor`, `qiki-intent-ownership-guardian`, `qiki-canon-passport`, `qiki-command-policy-map`, `qiki-provenance-map`, `qiki-legacy-split-audit`, `session-handoff`, `space-sim-builder`
- Installed but currently low-value for this project loop:
  `futura-*`, `notion-*`, `security-*`, `reducing-entropy`
