# QIKI_DTMP GitHub Research Guide

This file is the public orientation layer for external review. Its purpose is to prevent a reader from treating old reports, task notes, operator projections, or local tooling artifacts as current project truth.

## One-Sentence Frame

QIKI_DTMP is a truth-first space-simulation game: simulation services create world truth, transport and contracts carry it, ORION renders the operator view, and QIKI participates as an in-world autonomous system.

It is not a generic dashboard, a marketing digital-twin demo, or a collection of independent analysis reports.

## Read In This Order

1. `README.md` for product frame, runtime path, quick start, and repository map.
2. `docs/INDEX.md` for the public documentation entrypoint.
3. `docs/ARCHITECTURE.md` for service topology and dataflow.
4. `docs/design/canon/INDEX.md` for active design canon.
5. `docs/operator_console/REAL_DATA_MATRIX.md` for ORION display provenance.
6. `TASKS/00_INDEX.md` only when checking implementation dossiers.

Do not start from old task files, generated reports, comments, archives, or historical PR context.

## Truth Order

When two files appear to disagree, use this order:

1. Runtime code, tests, schemas, and reproducible service evidence.
2. Current task dossier under `TASKS/`.
3. Active canon under `docs/design/canon/`.
4. Public architecture, operations, and runbook docs.
5. Historical task notes, reports, and analysis material.

A lower layer can explain history, but it does not override a higher layer.

## Ownership Boundaries

- Simulation truth starts in `q-sim-service`.
- Transport and routing truth moves through NATS/JetStream and bridge services.
- ORION is the operator surface. It displays and summarizes truth; it does not own the underlying world state.
- QIKI is part of the simulated operational world, not a decorative chatbot.
- `introspector/` is a developer analysis tool. It can scan and describe code, but its reports are not product canon by themselves.

## What To Treat Carefully

- `TASKS/` contains implementation dossiers. Some are current; many are historical.
- Files with dates in names are evidence or work logs unless a current index points to them.
- Generated analysis and handoff-style files may be useful background, but they are not automatic truth.
- Operator-facing text can be a projection of runtime state. Check the source field, event, schema, or test before treating it as origin truth.
- Legacy names may remain in code or docs while the project moves toward ORION and QIKI as the active contour.

## What Is Not In This Repository

The public repository intentionally excludes local agent state, virtual environments, private memory, shell history, provider keys, local databases, temporary runs, generated bundles, and scratch exports.

Examples that must stay out of git:

- `.venv/`, `.serena/`, `.qwen/`, `.codex/`, `.claude/`
- `.env`, `.env.*`, credentials, tokens, cookies, provider keys
- `_archive/`, `TASK_OUT/`, `tmp/`, local one-off reports
- `introspector/tmp/`, `introspector/analyzer/data/`, local sqlite databases
- zip, pdf, tar, and other exported bundles

If a local checkout contains those paths, they are developer-machine state, not public project source.

## How To Check A Claim

Use this checklist before making conclusions:

1. Find the runtime owner: service, schema, model, or test.
2. Check whether the claim is current behavior, design intent, or historical evidence.
3. Follow the relevant index instead of searching randomly through dated files.
4. Prefer Docker-first commands from the README or runbooks for verification.
5. Quote paths and evidence, not broad impressions.

## Safe Summary

The safe public interpretation is:

QIKI_DTMP is a Python/Docker/NATS space-simulation game system with simulation-owned truth, ORION as the primary operator interface, QIKI as an autonomous in-world entity, and `introspector/` as a supporting developer analysis tool. Current truth is established by runtime code, tests, schemas, active task dossiers, and canon indexes, not by old reports or local agent artifacts.
