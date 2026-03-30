#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"

src_root="$repo_root/.codex/skills"
dst_root="$HOME/.codex/skills"

if [ ! -d "$src_root" ]; then
  echo "ERROR: missing repo skills dir: $src_root" >&2
  exit 1
fi

mkdir -p "$dst_root"

link_skill() {
  local name="$1"
  local src="$src_root/$name"
  local dst="$dst_root/$name"
  if [ ! -f "$src/SKILL.md" ]; then
    echo "ERROR: missing skill: $src/SKILL.md" >&2
    exit 1
  fi
  ln -sfn "$src" "$dst"
  echo "OK: linked $dst -> $src"
}

link_skill "qiki-bootstrap"
link_skill "qiki-checkpoint"
link_skill "qiki-drift-audit"
link_skill "sovmem-health"
link_skill "orion-operator-smoke"
link_skill "context-persistence-health"

echo
cfg="$HOME/.codex/config.toml"
if [ -f "$cfg" ]; then
  if ! rg -Fq "[mcp_servers.sovereign-memory]" "$cfg"; then
    echo "WARN: missing [mcp_servers.sovereign-memory] in $cfg"
  fi
  if ! rg -Fq "[mcp_servers.serena]" "$cfg"; then
    echo "WARN: missing [mcp_servers.serena] in $cfg"
  fi
else
  echo "WARN: missing $cfg"
fi

if command -v codex >/dev/null 2>&1; then
  echo
  codex mcp get sovereign-memory || true
else
  echo
  echo "NOTE: 'codex' is not on PATH; skipping 'codex mcp get'."
fi
