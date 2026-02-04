# Restore Drill — Sovereign Memory + MEMORI (QIKI_DTMP)

This drill exists to prevent the failure mode “we had backups but didn’t know how to restore”.

## Preconditions
- Backups directory: `/opt/backups/`
- Expected artifacts:
  - `memory_YYYY-MM-DD.db`
  - `memori_YYYY-MM-DD.tar.gz`

## 1) Pick a backup date
Choose the newest stable date (typically “today” or “yesterday”).

## 2) Stop the sovereign-memory service
Service name may vary by host; find it first:
```bash
systemctl --user list-units --type=service --all | rg -n "mcp|memory|sovereign"
```

Then stop the memory service (example):
```bash
systemctl --user stop mcp-memory.service
```

## 3) Restore the DB
```bash
sudo install -m 0600 -o "$USER" -g "$USER" \
  "/opt/backups/memory_YYYY-MM-DD.db" \
  "/opt/sovereign-memory/memory.db"
```

If you cannot use `sudo`, do the equivalent with permissions that match the existing file.

## 4) Restore `~/MEMORI`
Make a safety copy first:
```bash
mv "$HOME/MEMORI" "$HOME/MEMORI.bak.$(date +%s)"
mkdir -p "$HOME"
```

Restore:
```bash
tar -C "$HOME" -xzf "/opt/backups/memori_YYYY-MM-DD.tar.gz"
```

## 5) Start the service and verify
```bash
systemctl --user start mcp-memory.service
```

Verify via health script:
```bash
bash QIKI_DTMP/scripts/qiki_sovmem_health.sh --strict
```

And verify Codex sees MCP:
```bash
codex mcp get sovereign-memory
```

## 6) If the service name is unknown
Use the host’s service manager (systemd user/system) to locate which unit starts the MCP server and restart that.

