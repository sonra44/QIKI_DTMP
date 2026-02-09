#!/usr/bin/env bash
set -euo pipefail

strict=0
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
warn=0

while [ $# -gt 0 ]; do
  case "$1" in
    --strict) strict=1 ;;
    *)
      echo "Usage: $0 [--strict]" >&2
      exit 1
      ;;
  esac
  shift
done

ok_msg() {
  printf 'OK: %s\n' "$1"
}

warn_msg() {
  warn=1
  printf 'WARN: %s\n' "$1" >&2
}

if bash "$repo_root/scripts/qiki_sovmem_health.sh"; then
  ok_msg "sovereign-memory checks: PASS"
else
  warn_msg "sovereign-memory checks: FAIL"
fi

if [ -f "$repo_root/.serena/project.yml" ]; then
  ok_msg "serena project config present: .serena/project.yml"
else
  warn_msg "missing serena project config: .serena/project.yml"
fi

if [ -d "$repo_root/.serena/memories" ]; then
  mem_count="$(find "$repo_root/.serena/memories" -maxdepth 1 -type f | wc -l | tr -d ' ')"
  ok_msg "serena memories dir present: .serena/memories (files=$mem_count)"
else
  warn_msg "missing serena memories dir: .serena/memories"
fi

if [ -x "$repo_root/scripts/qiki_context_persistence_health.sh" ]; then
  if bash "$repo_root/scripts/qiki_context_persistence_health.sh"; then
    ok_msg "context-persistence health: PASS"
  else
    warn_msg "context-persistence health: WARN/FAIL"
  fi
else
  warn_msg "missing script: scripts/qiki_context_persistence_health.sh"
fi

serena_size="$(du -sh "$repo_root/.serena" 2>/dev/null | awk '{print $1}')"
if [ -n "${serena_size:-}" ]; then
  ok_msg "serena footprint: $serena_size"
fi

if [ "$warn" -eq 1 ] && [ "$strict" -eq 1 ]; then
  exit 2
fi

exit 0
