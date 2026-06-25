#!/usr/bin/env bash
# QIKI agent tool self-check — run as the FIRST action of any QIKI session.
# Verifies every shell-side tool actually launches. The MCP tools (sovereign / serena /
# herdr / coderabbit / ragflow) are verified by the agent with one live call each
# (printed at the end). Survives memory loss / new session / context resets: the ritual
# lives in CLAUDE.md + AGENTS.md, this script is its executable core.
set -uo pipefail
cd /home/sonra44/QIKI_DTMP 2>/dev/null || true
ok(){ printf '  [ OK ] %s\n' "$1"; }
warn(){ printf '  [WARN] %s\n' "$1"; }
bad(){ printf '  [FAIL] %s\n' "$1"; }
sandbox_blocked(){
  case "$1" in
    *"Operation not permitted"*|*"PermissionError"*|*"permission denied while trying to connect"*) return 0 ;;
    *) return 1 ;;
  esac
}
echo "=== QIKI TOOLCHECK $(date '+%F %T') ==="

# herdr (operator coordination)
if command -v herdr >/dev/null 2>&1; then ok "herdr CLI: $(herdr --version 2>/dev/null | head -1)"; else bad "herdr CLI missing"; fi

# RAGFlow / qiki-rag (canon retrieval) — SSE health + live query
if [ -x "$HOME/.local/bin/qiki-rag-mcp-smoke" ]; then
  smoke_out=$("$HOME/.local/bin/qiki-rag-mcp-smoke" 2>&1)
  smoke_rc=$?
  s=$(printf '%s\n' "$smoke_out" | grep -o 'MCP_SSE_STATUS [0-9]*' | head -1)
  if [ "$smoke_rc" -eq 0 ] && [ "$s" = "MCP_SSE_STATUS 200" ]; then
    ok "RAGFlow SSE: $s"
  elif sandbox_blocked "$smoke_out"; then
    warn "RAGFlow SSE blocked by sandbox; verify via native MCP or unsandboxed qiki-rag"
  else
    bad "RAGFlow SSE: ${s:-no response}"
  fi
else bad "qiki-rag-mcp-smoke missing"; fi
if [ -x "$HOME/.local/bin/qiki-rag" ]; then
  rag_err=$(timeout 60 "$HOME/.local/bin/qiki-rag" "module passport canon" --top 1 --max-chars 80 2>&1 >/dev/null)
  rag_rc=$?
  if [ "$rag_rc" -eq 0 ]; then
    ok "qiki-rag query returns canon"
  elif sandbox_blocked "$rag_err"; then
    warn "qiki-rag CLI blocked by sandbox; native ragflow MCP must be checked by the agent"
  else
    bad "qiki-rag query failed/timeout"
  fi
else bad "qiki-rag CLI missing"; fi

# RAGFlow MCP registered as native tool? (presence only, no secret printed)
if command -v claude >/dev/null 2>&1; then
  if timeout 8 claude mcp get ragflow 2>&1 | grep -q 'Connected' \
    || (cd /home/sonra44 && timeout 8 claude mcp get ragflow 2>&1 | grep -q 'Connected'); then
    ok "ragflow MCP connected in Claude config"
  else
    echo "  [WARN] ragflow MCP not connected via claude mcp (CLI still works)"
  fi
else
  echo "  [WARN] claude CLI missing; skip Claude MCP registration check"
fi
python3 - <<'PY' 2>/dev/null || echo "  [FAIL] cannot read ~/.codex/config.toml"
import os
from pathlib import Path
import tomllib

p = Path(os.path.expanduser("~/.codex/config.toml"))
d = tomllib.loads(p.read_text())
server = (d.get("mcp_servers") or {}).get("ragflow") or {}
cmd = server.get("command") or ""
env = server.get("env") or {}
has = bool(cmd and "qiki_rag_mcp_stdio.py" in cmd and "RAGFLOW_API_KEY_FILE" in env)
print("  [ OK ] ragflow MCP registered in ~/.codex/config.toml" if has else "  [WARN] ragflow MCP NOT registered in Codex (CLI still works)")
PY

# Docker-first runtime (qiki-dev)
docker_state=$(docker compose -f docker-compose.phase1.yml ps --format json qiki-dev 2>&1)
docker_rc=$?
if [ "$docker_rc" -eq 0 ] && printf '%s\n' "$docker_state" | python3 -c '
import json
import sys

raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(1)
rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
if any((row.get("State") == "running") or ("Up" in str(row.get("Status", ""))) for row in rows):
    raise SystemExit(0)
raise SystemExit(1)
'; then
  ok "Docker qiki-dev up (pytest runtime)"
elif sandbox_blocked "$docker_state"; then
  warn "Docker qiki-dev check blocked by sandbox"
else
  bad "Docker qiki-dev not Up"
fi

# Canon corpus present (repo verification layer)
[ -d docs/design/hardware_and_physics/qiki_body_v0_2_2 ] && ok "QIKI Body v0.2.2 canon docs present" || bad "canon docs missing"

# git context
b=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) && ok "git branch: $b" || bad "not a git repo"

echo "--- agent must ALSO do one live MCP call each at session start: ---"
echo "    sovereign recall  |  serena find_symbol  |  herdr read  |  (ragflow if registered)"
echo "=== END TOOLCHECK ==="
