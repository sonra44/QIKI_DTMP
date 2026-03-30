#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"

src_dir="$repo_root/infra/systemd/user"
dst_dir="$HOME/.config/systemd/user"

mkdir -p "$dst_dir"

install_unit() {
  local name="$1"
  local src="$src_dir/$name"
  local dst="$dst_dir/$name"
  if [ ! -f "$src" ]; then
    echo "ERROR: missing unit: $src" >&2
    exit 1
  fi
  ln -sfn "$src" "$dst"
  echo "OK: installed $dst -> $src"
}

install_unit "qiki-context-backup.service"
install_unit "qiki-context-backup.timer"

systemctl --user daemon-reload
systemctl --user enable --now qiki-context-backup.timer

echo
echo "Timers:"
systemctl --user list-timers --all | sed -n '1,200p'

echo
echo "NOTE: If you still have cron jobs for /home/sonra44/bin/sovereign-memory-backup.sh, consider removing them to avoid duplicate backups."

