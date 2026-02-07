from __future__ import annotations

import os
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


def _fmt_bytes(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    try:
        size = float(value)
    except Exception:
        return "N/A"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024.0:
            return f"{size:0.1f} {unit}"
        size /= 1024.0
    return f"{size:0.1f} PiB"


class ResourcesPanel(Static):
    """CPU/RAM/Disk/Net panel (no-mocks)."""

    def __init__(self) -> None:
        super().__init__(id="resources-panel")
        self._table_initialized = False

    def compose(self) -> ComposeResult:
        from textual.widgets import Label, DataTable

        yield Label("📊 Resources", classes="panel-title")
        if not _has_active_textual_app():
            return

        table: Any = DataTable(id="resources-table")
        table.add_columns("Metric", "Value")
        self._table_initialized = True
        yield table

    def refresh_data(self) -> None:
        if not _has_active_textual_app():
            return
        if not self._table_initialized:
            return

        from textual.widgets import DataTable

        try:
            table: Any = self.query_one("#resources-table", DataTable)
        except Exception:
            return

        now_utc = datetime.now(timezone.utc).strftime("%H:%M:%SZ")

        rows: list[tuple[str, str]] = [("Updated (UTC)", now_utc)]

        # CPU
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
            rows.append(("CPU %", f"{cpu_pct:0.1f}%"))
        except Exception as e:
            rows.append(("CPU %", f"unavailable: {e}"))

        try:
            load1, load5, load15 = os.getloadavg()
            rows.append(("Load avg", f"{load1:0.2f} {load5:0.2f} {load15:0.2f}"))
        except Exception as e:
            rows.append(("Load avg", f"unavailable: {e}"))

        # Memory
        try:
            vm = psutil.virtual_memory()
            rows.append(("RAM total", _fmt_bytes(vm.total)))
            rows.append(("RAM used", _fmt_bytes(vm.used)))
            rows.append(("RAM available", _fmt_bytes(vm.available)))
        except Exception as e:
            rows.append(("RAM", f"unavailable: {e}"))

        try:
            sm = psutil.swap_memory()
            rows.append(("Swap total", _fmt_bytes(sm.total)))
            rows.append(("Swap used", _fmt_bytes(sm.used)))
        except Exception as e:
            rows.append(("Swap", f"unavailable: {e}"))

        # Disk
        try:
            du = psutil.disk_usage("/")
            rows.append(("Disk / total", _fmt_bytes(du.total)))
            rows.append(("Disk / used", _fmt_bytes(du.used)))
            rows.append(("Disk / free", _fmt_bytes(du.free)))
        except Exception as e:
            rows.append(("Disk /", f"unavailable: {e}"))

        # Network
        try:
            net = psutil.net_io_counters()
            rows.append(("Net sent", _fmt_bytes(net.bytes_sent)))
            rows.append(("Net recv", _fmt_bytes(net.bytes_recv)))
        except Exception as e:
            rows.append(("Network", f"unavailable: {e}"))

        try:
            table.clear(columns=False)
        except Exception:
            try:
                table.clear()
            except Exception:
                pass

        for key, value in rows:
            table.add_row(key, value)
