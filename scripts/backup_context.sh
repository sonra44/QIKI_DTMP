#!/usr/bin/env bash
set -euo pipefail

umask 077

SRC_DB="${SRC_DB:-/opt/sovereign-memory/memory.db}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups}"
MEMORI_DIR="${MEMORI_DIR:-$HOME/MEMORI}"
LOG_FILE="${LOG_FILE:-$HOME/sovereign-memory-backup.log}"

mkdir -p "$BACKUP_DIR"

{
  echo "[$(date -Is)] context backup start"

  if [ ! -f "$SRC_DB" ]; then
    echo "ERROR: missing db: $SRC_DB"
    exit 1
  fi
  if [ ! -d "$MEMORI_DIR" ]; then
    echo "ERROR: missing MEMORI dir: $MEMORI_DIR"
    exit 1
  fi

  lock_file="$BACKUP_DIR/.sovereign-memory-backup.lock"
  exec 9>"$lock_file"
  if command -v flock >/dev/null 2>&1; then
    flock -n 9 || { echo "INFO: already running; exiting"; exit 0; }
  fi

  db_dest="$BACKUP_DIR/memory_$(date +%F).db"
  export SRC_DB DEST_DB="$db_dest"
  python3 - <<'PY'
import os
import sqlite3

src = os.environ["SRC_DB"]
dest = os.environ["DEST_DB"]

con = sqlite3.connect(src, timeout=30)
try:
    with sqlite3.connect(dest) as out:
        con.backup(out)
finally:
    con.close()
print(f"OK: wrote db backup: {dest}")
PY

  memori_dest="$BACKUP_DIR/memori_$(date +%F).tar.gz"
  memori_base="$(cd "$(dirname "$MEMORI_DIR")" && pwd)"
  memori_name="$(basename "$MEMORI_DIR")"
  tar -C "$memori_base" -czf "$memori_dest" "$memori_name"
  echo "OK: wrote MEMORI backup: $memori_dest"

  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'memory_*.db' -mtime +30 -print -delete || true
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'memori_*.tar.gz' -mtime +30 -print -delete || true

  echo "[$(date -Is)] context backup done"
} >>"$LOG_FILE" 2>&1

