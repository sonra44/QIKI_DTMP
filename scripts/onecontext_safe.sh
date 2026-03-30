#!/usr/bin/env bash
set -euo pipefail

# OneContext can fail with:
# "Error searching: unable to open database file"
# in restricted environments when SQLite needs temp files for heavy queries.
# Force temp files into writable /tmp.
export SQLITE_TMPDIR="${SQLITE_TMPDIR:-/tmp}"

exec onecontext "$@"
