#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# This script enforces the canon:
# - Priority board is ONLY in ~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md
# - Repo may contain historical/reference plans, but they MUST be clearly marked.

header_marker="HISTORICAL/REFERENCE ONLY (NOT CANON)"

# Files that look like task boards / priority lists.
suspect_files=()
tmp="$(mktemp)"
set +e
rg -l -S \
  -g '*.md' \
  -g '!README*.md' \
  -g '!Cabinet/README.md' \
  '(^\*\*Статус:\*\*\s*АКТИВНЫЙ\b|^#\s*(Critical|High Priority|Medium Priority|Low Priority)\s+Tasks\s+\(P[1-4]\)|^#\s*NEXT TASKS ROADMAP\b|\bАКТУАЛЬНЫЙ\s+СПИСОК\s+ЗАДАЧ\b)' \
  . >"$tmp"
rg_status=$?
set -e

if [ "$rg_status" -eq 2 ]; then
  echo "FAIL: rg execution error while scanning repo." >&2
  rm -f "$tmp"
  exit 2
fi

if [ "$rg_status" -eq 1 ]; then
  rm -f "$tmp"
  echo "OK: no suspect task-board-like files found."
  exit 0
fi

while IFS= read -r f; do
  [ -n "${f:-}" ] || continue
  suspect_files+=("$f")
done <"$tmp"
rm -f "$tmp"

fail=0
for f in "${suspect_files[@]}"; do
  # Allow genuine non-board docs; only enforce marker when the file matches patterns above.
  if ! head -n 40 "$f" | rg -q -F "$header_marker"; then
    echo "FAIL: '$f' looks like a task/priority board but is not marked as reference-only."
    echo "      Add header '$header_marker' + link to ~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md."
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "OK: all suspect task-board-like files are marked as reference-only."
