#!/usr/bin/env bash
set -euo pipefail

strict=0
max_age_smoke_minutes="${MAX_AGE_SMOKE_MINUTES:-120}"
max_age_smoke_write_minutes="${MAX_AGE_SMOKE_WRITE_MINUTES:-1500}" # 25h
max_age_backup_minutes="${MAX_AGE_BACKUP_MINUTES:-1500}" # 25h

while [ $# -gt 0 ]; do
  case "$1" in
    --strict) strict=1 ;;
    --max-age-smoke-minutes) max_age_smoke_minutes="$2"; shift ;;
    --max-age-smoke-write-minutes) max_age_smoke_write_minutes="$2"; shift ;;
    --max-age-backup-minutes) max_age_backup_minutes="$2"; shift ;;
    *)
      echo "Usage: $0 [--strict] [--max-age-smoke-minutes N] [--max-age-smoke-write-minutes N] [--max-age-backup-minutes N]" >&2
      exit 1
      ;;
  esac
  shift
done

warn=0
warn_msg() {
  warn=1
  printf 'WARN: %s\n' "$1" >&2
}

ok_msg() {
  printf 'OK: %s\n' "$1"
}

now_epoch="$(date +%s)"

age_minutes() {
  local path="$1"
  local mtime
  if ! mtime="$(stat -c '%Y' "$path" 2>/dev/null)"; then
    return 1
  fi
  echo $(( (now_epoch - mtime) / 60 ))
}

smoke_bin="$HOME/bin/sovereign-memory-smoke.sh"
if [ -x "$smoke_bin" ]; then
  if SMOKE_NO_WRITE=1 "$smoke_bin" >/tmp/qiki_sovmem_smoke.out 2>/tmp/qiki_sovmem_smoke.err; then
    ok_msg "MCP smoke (no-write): PASS"
  else
    warn_msg "MCP smoke (no-write): FAIL (see /tmp/qiki_sovmem_smoke.err)"
  fi
else
  warn_msg "missing smoke script: $smoke_bin"
fi

smoke_log="$HOME/logs/sovereign-memory-smoke.log"
if [ -f "$smoke_log" ]; then
  a="$(age_minutes "$smoke_log")"
  if [ "$a" -le "$max_age_smoke_minutes" ]; then
    ok_msg "smoke log fresh (${a}m): $smoke_log"
  else
    warn_msg "smoke log stale (${a}m > ${max_age_smoke_minutes}m): $smoke_log"
  fi
else
  warn_msg "missing smoke log: $smoke_log"
fi

smoke_write_log="$HOME/logs/sovereign-memory-smoke-write.log"
if [ -f "$smoke_write_log" ]; then
  a="$(age_minutes "$smoke_write_log")"
  if [ "$a" -le "$max_age_smoke_write_minutes" ]; then
    ok_msg "smoke-write log fresh (${a}m): $smoke_write_log"
  else
    warn_msg "smoke-write log stale (${a}m > ${max_age_smoke_write_minutes}m): $smoke_write_log"
  fi
else
  warn_msg "missing smoke-write log: $smoke_write_log"
fi

backup_dir="/opt/backups"
today="$(date +%F)"
db_backup="$backup_dir/memory_${today}.db"
memori_backup="$backup_dir/memori_${today}.tar.gz"

check_backup_fresh() {
  local label="$1"
  local preferred_path="$2"
  local glob="$3"
  local path="$preferred_path"
  local age

  if [ ! -f "$path" ]; then
    path="$(ls -1t $glob 2>/dev/null | head -n 1 || true)"
    if [ -z "$path" ]; then
      warn_msg "missing ${label} backup: expected $preferred_path (or any $glob)"
      return
    fi
  fi

  age="$(age_minutes "$path")"
  if [ "$age" -le "$max_age_backup_minutes" ]; then
    ok_msg "${label} backup fresh (${age}m): $path"
  else
    warn_msg "${label} backup stale (${age}m > ${max_age_backup_minutes}m): $path"
  fi
}

check_backup_fresh "DB" "$db_backup" "$backup_dir/memory_*.db"
check_backup_fresh "MEMORI" "$memori_backup" "$backup_dir/memori_*.tar.gz"

if [ "$warn" = "1" ] && [ "$strict" = "1" ]; then
  exit 2
fi
exit 0
