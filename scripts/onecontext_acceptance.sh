#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAFE="$ROOT_DIR/scripts/onecontext_safe.sh"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/onecontext_acceptance.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

if [[ ! -x "$SAFE" ]]; then
  echo "ERROR: missing executable wrapper: $SAFE" >&2
  exit 1
fi

echo "[1/6] watcher status"
"$SAFE" watcher status >"$TMP_DIR/watcher_status.txt"
grep -q "Watcher Status: Running" "$TMP_DIR/watcher_status.txt"

echo "[2/6] worker status"
"$SAFE" worker status >"$TMP_DIR/worker_status.txt"
grep -q "Worker: Running" "$TMP_DIR/worker_status.txt"

echo "[3/6] context show"
"$SAFE" context show >"$TMP_DIR/context_show.txt"
grep -q "Context Title:" "$TMP_DIR/context_show.txt"

echo "[4/6] turn search smoke"
"$SAFE" search "worker|watcher|database" -t turn --limit 3 >"$TMP_DIR/turn_smoke.txt"
grep -q "Regex Search:" "$TMP_DIR/turn_smoke.txt"

echo "[5/6] content search reliability (10x)"
for i in 1 2 3 4 5 6 7 8 9 10; do
  CONTENT_FILE="$TMP_DIR/content_smoke_$i.txt"
  "$SAFE" search "database" -t content --limit 1 --snippet-context 40 >"$CONTENT_FILE"
  [[ -s "$CONTENT_FILE" ]]
  grep -Eq "Snippet:|Regex Search:" "$CONTENT_FILE"
done

echo "[6/6] db path policy"
DB_PATH="$("$SAFE" config get sqlite_db_path | awk -F'= ' '{print $2}')"
if [[ -z "$DB_PATH" ]]; then
  echo "ERROR: sqlite_db_path is empty" >&2
  exit 1
fi

EXPECTED_DB_PATH="${EXPECTED_DB_PATH:-$ROOT_DIR/.onecontext/aline.db}"
if [[ "$DB_PATH" != "$EXPECTED_DB_PATH" ]]; then
  echo "ERROR: unexpected sqlite_db_path: $DB_PATH (expected: $EXPECTED_DB_PATH)" >&2
  exit 1
fi
if [[ ! -r "$DB_PATH" ]]; then
  echo "ERROR: sqlite_db_path is not readable: $DB_PATH" >&2
  exit 1
fi

echo "ACCEPTANCE_OK"
