from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psutil
from textual.app import ComposeResult
from textual.widgets import Static


def _has_active_textual_app() -> bool:
    try:
        from textual._context import active_app  # type: ignore

        active_app.get()
        return True
    except Exception:
        return False


def _read_os_release() -> str:
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "unknown"


@dataclass(frozen=True)
class SystemInfo:
    pretty_os: str
    kernel: str
    hostname: str
    python: str
    uptime_seconds: int | None
    now_utc: str


def get_system_info() -> SystemInfo:
    uname = platform.uname()
    pretty_os = _read_os_release()
    hostname = uname.node or platform.node() or "unknown"
    kernel = f"{uname.system} {uname.release}"
    python = platform.python_version()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    uptime_seconds: int | None
    try:
        uptime_seconds = int(datetime.now(timezone.utc).timestamp() - psutil.boot_time())
    except Exception:
        uptime_seconds = None

    return SystemInfo(
        pretty_os=pretty_os,
        kernel=kernel,
        hostname=hostname,
        python=python,
        uptime_seconds=uptime_seconds,
        now_utc=now_utc,
    )


class SystemPanel(Static):
    """System information panel (no-mocks)."""

    def __init__(self) -> None:
        super().__init__(id="system-panel")
        self._table_initialized = False

    def compose(self) -> ComposeResult:
        # Lazy import for test patching and to avoid NoActiveAppError in direct compose() tests.
        from textual.widgets import Label, DataTable

        yield Label("🧠 System", classes="panel-title")
        if not _has_active_textual_app():
            return

        table: Any = DataTable(id="system-table")
        table.add_columns("Key", "Value")
        self._table_initialized = True
        yield table

    def refresh_data(self) -> None:
        if not _has_active_textual_app():
            return
        if not self._table_initialized:
            return

        from textual.widgets import DataTable

        try:
            table: Any = self.query_one("#system-table", DataTable)
        except Exception:
            return

        info = get_system_info()
        rows = [
            ("OS", info.pretty_os),
            ("Kernel", info.kernel),
            ("Hostname", info.hostname),
            ("Python", info.python),
            ("Now (UTC)", info.now_utc),
            ("Uptime (s)", "N/A" if info.uptime_seconds is None else str(info.uptime_seconds)),
            ("PID", str(os.getpid())),
        ]

        try:
            table.clear(columns=False)
        except Exception:
            # Older Textual versions may not support clear(columns=...); fallback to best-effort.
            try:
                table.clear()
            except Exception:
                pass

        for key, value in rows:
            table.add_row(key, value)
