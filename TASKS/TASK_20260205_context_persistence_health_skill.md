# TASK: Context persistence health skill (timers + backups + MCP)

**ID:** TASK_20260205_context_persistence_health_skill  
**Status:** done  
**Owner:** codex  
**Date created:** 2026-02-05  

## Goal

Add a single deterministic check that proves “context will not be lost”:
- Sovereign-memory smoke + backup freshness
- systemd user timer install/active status
- warning on potential cron duplication (without requiring cron access)

## Canon links

- `docs/agents/context_persistence.md`
- `scripts/install_context_timers.sh`
- `scripts/qiki_sovmem_health.sh`

## Changes

- New host-side health script: `scripts/qiki_context_persistence_health.sh`
- New Codex skill: `.codex/skills/context-persistence-health/SKILL.md`
- Skill installer links it: `scripts/install_codex_skills.sh`

## Evidence (commands → output)

- `bash QIKI_DTMP/scripts/qiki_context_persistence_health.sh --strict`
  - Expected: SovMem PASS + backups fresh + timer active.
  - Note: cron visibility can be restricted; script warns but does not hard-fail on permission denial.

## Definition of Done (DoD)

- [x] Script runs on host without edits to repo state
- [x] Skill exists and is linkable into `~/.codex/skills/`
- [x] Changes are committed and pushed

