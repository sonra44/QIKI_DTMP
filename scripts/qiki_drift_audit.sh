#!/usr/bin/env bash
set -euo pipefail

strict=0
if [ "${1:-}" = "--strict" ]; then
  strict=1
  shift
fi

warn=0
warn_msg() {
  warn=1
  printf 'WARN: %s\n' "$1" >&2
}

ok_msg() {
  printf 'OK: %s\n' "$1"
}

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

board="$HOME/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md"
if [ -f "$board" ]; then
  ok_msg "canon board present: $board"
else
  warn_msg "missing canon board: $board"
fi

canon_index="$repo_root/docs/design/canon/INDEX.md"
if [ -f "$canon_index" ]; then
  ok_msg "design canon entrypoint present: $canon_index"
else
  warn_msg "missing design canon entrypoint: $canon_index"
fi

docs_index="$repo_root/docs/INDEX.md"
if [ -f "$docs_index" ]; then
  ok_msg "docs canon entrypoint present: $docs_index"
else
  warn_msg "missing docs canon entrypoint: $docs_index"
fi

guard="$repo_root/scripts/check_no_second_task_board.sh"
if [ -x "$guard" ]; then
  if bash "$guard"; then
    ok_msg "no second task board guard: PASS"
  else
    warn_msg "no second task board guard: FAIL (see output above)"
  fi
else
  warn_msg "missing/ non-executable guard: $guard"
fi

archive_dir="$repo_root/docs/Архив"
if [ -d "$archive_dir" ]; then
  ok_msg "archive dir exists (reference-only): $archive_dir"
else
  warn_msg "archive dir missing: $archive_dir"
fi

if [ "$warn" = "1" ] && [ "$strict" = "1" ]; then
  exit 2
fi
exit 0

