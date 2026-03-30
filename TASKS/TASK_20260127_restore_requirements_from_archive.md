# TASK: Restore requirements files for Docker build reproducibility

**ID:** TASK_20260127_RESTORE_REQUIREMENTS_FROM_ARCHIVE  
**Status:** completed (verified 2026-02-09)  

## Goal

Ensure Docker build has stable, present dependency lock entrypoints (requirements files exist and are referenced).

## Evidence

- Files present in repo root:
  - `requirements.txt`
  - `requirements-dev.txt`
  - `requirements-faststream.txt`
## Operator Scenario (visible outcome)
- Developer builds Docker from clean clone; requirements files must exist at repo root.

## Reproduction Command
```bash
ls -la requirements*.txt
```

## Before / After
- Before: Docker COPY requirements*.txt could fail on clean checkout.
- After: Root requirements files exist and are discoverable by Dockerfiles.

## Impact Metric
- Metric: missing root requirements files
- Baseline: missing
- Actual: present (requirements*.txt)
