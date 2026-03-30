---
name: qiki-record-replay-analyst
description: Use existing QIKI_DTMP record/replay tooling to capture and replay the smallest useful subject set for incident, timing, telemetry, or radar analysis. Use for offline reproduction without inventing new capture tooling.
---

# QIKI Record Replay Analyst

Study real event flow with the existing JSONL tooling instead of creating ad hoc data-study scripts.

## Use when

- incident replay is needed
- event timing or ordering is under question
- a bug should be reproduced offline from live traffic
- telemetry or radar investigation needs a minimal capture plan

## Do not use when

- the issue can be resolved by a direct unit test without runtime evidence
- the task is broad logging strategy design

## Required invariants

- Reuse existing record/replay utilities first.
- Keep capture scope minimal: only the subjects needed for the question.
- Prefer Docker-first commands for live capture on the canonical stack.
- Do not collect data "just in case" without a concrete investigation target.

## Evidence targets

- `src/qiki/shared/record_replay.py`
- `tools/nats_record_jsonl.py`
- `tools/nats_replay_jsonl.py`
- `src/qiki/services/operator_console/utils/data_export.py`
- `src/qiki/services/q_core_agent/core/trace_export.py`

## Procedure

1. State the bug or question in one line.
2. Identify the smallest subject set that could prove it.
3. Name capture duration or stopping condition.
4. Produce exact capture and replay commands using existing tools.
5. Summarize the expected timeline checkpoints to inspect in JSONL.

## Output

- `Question:` what the capture is meant to prove
- `Subjects:` minimal list
- `Capture command:` exact command
- `Replay command:` exact command
- `Checkpoints:` 3-5 timeline markers to inspect

## Rules

- Prefer fewer subjects and shorter captures.
- If an existing export path already contains the needed evidence, say so and avoid a new recording step.
- Distinguish raw captured truth from replay-side interpretation.
