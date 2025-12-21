"""
Legacy MetricsPanel widget used by the operator_console test-suite.

No-mocks policy: this widget never fabricates values. It can display:
- real collected metrics via `MetricsClient`, or
- honest empty/disabled states.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from textual.widgets import Static


class MetricsPanel(Static):
    """Metrics panel that renders a textual dashboard into the widget content."""

    def __init__(
        self,
        metrics_client: Optional[Any] = None,
        *,
        refresh_interval: float = 2.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(id="metrics_panel", **kwargs)
        self.title = "System Metrics"
        self.can_focus = True

        self.metrics_client = metrics_client
        self._auto_refresh: bool = False
        self.refresh_interval: float = float(refresh_interval)
        self.view_mode: str = "summary"  # summary -> graphs -> raw

        self._refresh_task: Optional[asyncio.Task] = None

    @property
    def auto_refresh(self) -> bool:
        # Do not use Textual's built-in auto_refresh timer here: tests construct the widget
        # outside a running event loop.
        return self._auto_refresh

    @auto_refresh.setter
    def auto_refresh(self, value: bool) -> None:
        self._auto_refresh = bool(value)

    def _format_value(self, value: float, unit: Optional[str]) -> str:
        text = f"{value:.2f}"
        if not unit:
            return text
        if unit in {"%", "ms"}:
            return f"{text}{unit}"
        return f"{text} {unit}"

    def _format_bytes(self, value: float) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        v = float(value)
        unit_index = 0
        while v >= 1024.0 and unit_index < len(units) - 1:
            v /= 1024.0
            unit_index += 1
        return f"{v:.2f} {units[unit_index]}" if units[unit_index] != "B" else f"{v:.2f} B"

    def _create_bar_chart(self, values: List[float], width: int) -> str:
        if not values:
            return "No data"
        max_val = max(values) if values else 1.0
        max_val = max(max_val, 1e-9)

        lines: List[str] = []
        for v in values[-5:]:
            ratio = max(0.0, min(1.0, v / max_val))
            filled = max(1, int(ratio * (width - 6)))
            bar = "▓" * filled + "░" * max(0, (width - 6) - filled)
            pct = int(ratio * 100)
            lines.append(f"{bar} {pct:3d}%")
        return "\n".join(lines)

    def _create_line_graph(self, values: List[float], width: int) -> str:
        if not values:
            return "No data"
        if len(values) == 1:
            return "*"

        chars = "*-+|"
        min_v = min(values)
        max_v = max(values)
        span = max(max_v - min_v, 1e-9)
        normalized = [(v - min_v) / span for v in values[-width:]]

        out = []
        for n in normalized:
            idx = int(n * (len(chars) - 1))
            out.append(chars[idx])
        return "".join(out)

    def _create_summary_table(self, summaries: Dict[str, Any]) -> str:
        if not summaries:
            return "No metrics available"

        lines = ["Summary", "------"]
        for name, s in sorted(summaries.items()):
            if not isinstance(s, dict) or "error" in s:
                lines.append(f"{name}: N/A")
                continue
            unit = s.get("unit") or ""
            latest = s.get("latest")
            if latest is None:
                lines.append(f"{name}: N/A")
                continue
            lines.append(f"{name}: {self._format_value(float(latest), unit)}")
        return "\n".join(lines)

    def _create_recent_metrics(self, recent: List[Dict[str, Any]]) -> str:
        if not recent:
            return "No recent metrics"

        lines = ["Recent Values", "------------"]
        for item in recent:
            name = str(item.get("name", "unknown"))
            unit = item.get("unit")
            value = item.get("value")
            ts = item.get("timestamp")
            ts_text = ts.isoformat() if isinstance(ts, datetime) else (str(ts) if ts else "—")
            if isinstance(value, (int, float)):
                lines.append(f"{name}: {self._format_value(float(value), unit)} @ {ts_text}")
            else:
                lines.append(f"{name}: N/A @ {ts_text}")
        return "\n".join(lines)

    def _get_content(self) -> str:
        if not self.metrics_client:
            summary = self._create_summary_table({})
            recent = self._create_recent_metrics([])
            return (
                f"{self.title}\n"
                "Metrics Collection: Disabled\n\n"
                f"{summary}\n\n"
                f"{recent}\n"
            )

        summaries: Dict[str, Any] = {}
        for name in self.metrics_client.get_metric_names():
            summaries[name] = self.metrics_client.get_metric_summary(name)

        latest = self.metrics_client.get_latest_values()
        recent_rows: List[Dict[str, Any]] = []
        for name, value in latest.items():
            series = self.metrics_client.get_metric(name)
            unit = getattr(series, "unit", "") if series else ""
            ts = series.points[-1].timestamp if series and getattr(series, "points", None) else None
            recent_rows.append({"name": name, "value": value, "unit": unit, "timestamp": ts})

        if self.view_mode == "summary":
            return (
                f"{self.title}\n"
                "Metrics Collection: Active\n\n"
                f"{self._create_summary_table(summaries)}\n"
            )

        if self.view_mode == "graphs":
            lines = [self.title, "Metrics Collection: Active", "", "Graphs", "------"]
            for name in self.metrics_client.get_metric_names():
                series = self.metrics_client.get_metric(name)
                if not series or not getattr(series, "points", None):
                    continue
                desc = getattr(series, "description", "") or name
                values = [p.value for p in list(series.points)[-30:]]
                lines.append(desc)
                lines.append(self._create_line_graph(values, 40))
                lines.append("")
            return "\n".join(lines).rstrip()

        # raw
        return (
            f"{self.title}\n"
            "Metrics Collection: Active\n\n"
            f"{self._create_recent_metrics(recent_rows)}\n"
        )

    def _toggle_refresh(self) -> None:
        self.auto_refresh = not self.auto_refresh
        if self.auto_refresh:
            self._start_refresh_task()
        else:
            self._stop_refresh_task()

    def _cycle_view_mode(self) -> None:
        self.view_mode = {"summary": "graphs", "graphs": "raw", "raw": "summary"}.get(
            self.view_mode,
            "summary",
        )

    def _export_metrics(self, format: str) -> str:
        if not self.metrics_client:
            return "No metrics client available"
        try:
            return self.metrics_client.export_metrics(format=format)
        except Exception as e:
            return str(e)

    def _start_refresh_task(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # Called from sync code/tests without an event loop.
            return
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    def _stop_refresh_task(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        self._refresh_task = None

    async def _refresh_loop(self) -> None:
        try:
            while self.auto_refresh:
                self.update(self._get_content())
                await asyncio.sleep(self.refresh_interval)
        except asyncio.CancelledError:
            return
