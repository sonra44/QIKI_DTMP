#!/usr/bin/env bash
set -euo pipefail

strict=0

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

warn=0
warn_msg() {
  warn=1
  printf 'WARN: %s\n' "$1" >&2
}

ok_msg() {
  printf 'OK: %s\n' "$1"
}

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if bash "$repo_root/scripts/qiki_sovmem_health.sh" >/tmp/qiki_sovmem_health.out 2>/tmp/qiki_sovmem_health.err; then
  ok_msg "sovmem health: PASS"
else
  warn_msg "sovmem health: FAIL (see /tmp/qiki_sovmem_health.err)"
fi

if command -v systemctl >/dev/null 2>&1; then
  if systemctl --user is-active qiki-context-backup.timer >/dev/null 2>&1; then
    ok_msg "systemd user timer active: qiki-context-backup.timer"
  else
    warn_msg "systemd user timer NOT active: qiki-context-backup.timer (run: bash QIKI_DTMP/scripts/install_context_timers.sh)"
  fi

  if systemctl --user list-timers --all >/tmp/qiki_context_timers.out 2>/tmp/qiki_context_timers.err; then
    if rg -n "qiki-context-backup\\.timer" /tmp/qiki_context_timers.out >/dev/null 2>&1; then
      ok_msg "timer listed: qiki-context-backup.timer"
    else
      warn_msg "timer missing from list-timers: qiki-context-backup.timer"
    fi
  else
    warn_msg "systemctl --user list-timers failed (see /tmp/qiki_context_timers.err)"
  fi
else
  warn_msg "missing systemctl; cannot verify systemd user timers"
fi

units_dir="$HOME/.config/systemd/user"
svc="$units_dir/qiki-context-backup.service"
tmr="$units_dir/qiki-context-backup.timer"
if [ -e "$svc" ] && [ -e "$tmr" ]; then
  ok_msg "units installed in ~/.config/systemd/user"
else
  warn_msg "units missing in ~/.config/systemd/user (expected qiki-context-backup.service + .timer)"
fi

if command -v crontab >/dev/null 2>&1; then
  if crontab -l >/tmp/qiki_crontab.out 2>/tmp/qiki_crontab.err; then
    if rg -n "sovereign-memory-backup\\.sh|sovereign-memory-smoke\\.sh" /tmp/qiki_crontab.out >/dev/null 2>&1; then
      warn_msg "cron contains sovereign-memory backup/smoke entries (preferred: systemd user timers only; see DECISIONS id=1579)"
    else
      ok_msg "cron has no sovereign-memory backup/smoke entries"
    fi
  else
    if rg -n "Permission denied" /tmp/qiki_crontab.err >/dev/null 2>&1; then
      printf 'WARN: crontab -l permission denied; cannot verify duplicate cron jobs (manual check may require sudo)\n' >&2
    else
      warn_msg "crontab -l failed (see /tmp/qiki_crontab.err)"
    fi
  fi
else
  warn_msg "missing crontab; cannot verify duplicate cron jobs"
fi

if [ "$warn" = "1" ] && [ "$strict" = "1" ]; then
  exit 2
fi
exit 0
