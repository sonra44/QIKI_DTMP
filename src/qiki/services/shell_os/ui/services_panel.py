from __future__ import annotations

import os
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.widgets import Static


def _has_active_textual_app() -> bool:
    try:
        from textual._context import active_app  # type: ignore

        active_app.get()
        return True
    except Exception:
        return False


def _tcp_check(host: str, port: int, timeout_s: float = 1.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True, "ok"
    except Exception as e:
        return False, str(e)


class ServicesPanel(Static):
    """Best-effort services/stack status (no-mocks)."""

    def __init__(self) -> None:
        super().__init__(id="services-panel")
        self._table_initialized = False

    def compose(self) -> ComposeResult:
        from textual.widgets import Label, DataTable

        yield Label("🧩 Services", classes="panel-title")
        if not _has_active_textual_app():
            return

        table = DataTable(id="services-table")
        table.add_columns("Service", "Status", "Details")
        self._table_initialized = True
        yield table

    def refresh_data(self) -> None:
        if not _has_active_textual_app():
            return
        if not self._table_initialized:
            return

        from textual.widgets import DataTable

        try:
            table = self.query_one("#services-table", DataTable)
        except Exception:
            return

        rows: list[tuple[str, str, str]] = []
        rows.append(("Updated (UTC)", "ok", datetime.now(timezone.utc).strftime("%H:%M:%SZ")))

        # NATS reachability (best-effort)
        nats_url = os.getenv("NATS_URL", "")
        if nats_url:
            parsed = urlparse(nats_url)
            host = parsed.hostname or ""
            port = parsed.port or 4222
            if host:
                ok, detail = _tcp_check(host, port, timeout_s=1.0)
                rows.append(("NATS", "ok" if ok else "down", f"{host}:{port} ({detail})"))
            else:
                rows.append(("NATS", "unknown", f"bad url: {nats_url!r}"))
        else:
            rows.append(("NATS", "unknown", "NATS_URL not set"))

        # Docker status (best-effort)
        docker_path = shutil.which("docker")
        if not docker_path:
            rows.append(("Docker", "unknown", "docker CLI not found"))
        else:
            try:
                result = subprocess.run(
                    [docker_path, "ps", "--format", "{{.Names}}\t{{.Status}}"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                )
                if result.returncode != 0:
                    rows.append(("Docker", "error", (result.stderr or result.stdout).strip()[:200]))
                else:
                    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
                    rows.append(("Docker", "ok", f"containers: {len(lines)}"))
                    for line in lines[:8]:
                        try:
                            name, status = line.split("\t", 1)
                        except ValueError:
                            name, status = line, ""
                        rows.append((f"  {name}", "—", status[:120]))
            except Exception as e:
                rows.append(("Docker", "error", str(e)[:200]))

        try:
            table.clear(columns=False)
        except Exception:
            try:
                table.clear()
            except Exception:
                pass

        for svc, status, detail in rows:
            table.add_row(svc, status, detail)

