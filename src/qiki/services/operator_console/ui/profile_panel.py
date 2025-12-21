"""Bot profile panel (single source of truth).

Shows consolidated bot structure and hardware profile from repository docs/configs.

This panel is intentionally read-only: it only displays files that exist on disk.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, Markdown, Static


def _resolve_repo_root() -> Optional[Path]:
    for env_name in ("QIKI_REPO_ROOT", "QIKI_WORKSPACE", "WORKSPACE"):
        raw = os.getenv(env_name)
        if not raw:
            continue
        candidate = Path(raw).expanduser().resolve()
        if (candidate / "shared" / "specs" / "BotSpec.yaml").exists():
            return candidate

    cwd = Path.cwd().resolve()
    for parent in (cwd, *cwd.parents):
        if (parent / "shared" / "specs" / "BotSpec.yaml").exists():
            return parent

    return None


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _extract_botspec_id(botspec_yaml: str) -> Optional[str]:
    # Best-effort parser: avoid extra deps inside operator console.
    # Expected shape:
    # metadata:
    #   id: QIKI-DODECA-01
    match = re.search(r"(?m)^\s*id\s*:\s*([A-Za-z0-9_.-]+)\s*$", botspec_yaml)
    return match.group(1) if match else None


def _load_json(path: Path) -> Optional[Any]:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _build_summary(repo_root: Optional[Path]) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()

    if repo_root is None:
        table.add_row("Repo root", "NOT FOUND (set QIKI_REPO_ROOT)")
        return Panel(table, title="Profile Summary", border_style="red")

    table.add_row("Repo root", str(repo_root))

    botspec_path = repo_root / "shared" / "specs" / "BotSpec.yaml"
    botspec_text = _read_text(botspec_path)
    botspec_id = _extract_botspec_id(botspec_text) if botspec_text else None
    table.add_row("BotSpec", str(botspec_path))
    table.add_row("BotSpec id", botspec_id or "(unavailable)")

    thrusters_path = repo_root / "config" / "propulsion" / "thrusters.json"
    thrusters = _load_json(thrusters_path)
    if isinstance(thrusters, list):
        clusters = sorted({str(t.get("cluster_id", "?")) for t in thrusters})
        fmax_values = [float(t.get("f_max_newton", 0.0)) for t in thrusters if "f_max_newton" in t]
        fmax_min = min(fmax_values) if fmax_values else 0.0
        fmax_max = max(fmax_values) if fmax_values else 0.0
        table.add_row("RCS thrusters", f"{len(thrusters)} (clusters: {', '.join(clusters)})")
        table.add_row("F_max (N)", f"min={fmax_min:.1f} max={fmax_max:.1f}")
    else:
        table.add_row("RCS thrusters", f"unavailable ({thrusters_path})")

    bot_config_path = (
        repo_root
        / "src"
        / "qiki"
        / "services"
        / "q_core_agent"
        / "config"
        / "bot_config.json"
    )
    bot_cfg = _load_json(bot_config_path)
    if isinstance(bot_cfg, dict):
        hw = bot_cfg.get("hardware_profile", {}) if isinstance(bot_cfg.get("hardware_profile"), dict) else {}
        actuators = hw.get("actuators", []) if isinstance(hw.get("actuators"), list) else []
        sensors = hw.get("sensors", []) if isinstance(hw.get("sensors"), list) else []
        table.add_row("Hardware profile", str(bot_config_path))
        table.add_row("Actuators", str(len(actuators)))
        table.add_row("Sensors", str(len(sensors)))
    else:
        table.add_row("Hardware profile", f"unavailable ({bot_config_path})")

    return Panel(table, title="Profile Summary", border_style="blue")


def _load_source_of_truth_markdown(repo_root: Optional[Path]) -> str:
    if repo_root is None:
        return "# Bot Profile\n\nRepo root not found. Set `QIKI_REPO_ROOT` (e.g. `/workspace`)."

    doc_path = repo_root / "docs" / "design" / "hardware_and_physics" / "bot_source_of_truth.md"
    text = _read_text(doc_path)
    if text is None:
        return (
            "# Bot Profile\n\n"
            f"File not found or unreadable: `{doc_path}`\n"
        )

    return text


class ProfilePanel(VerticalScroll):
    """Scrollable bot profile view (real files only)."""

    def compose(self) -> ComposeResult:
        yield Label("🧩 Bot Profile", classes="panel-title")
        yield Static(id="profile-summary")
        yield Markdown("", id="profile-doc", open_links=False)

    async def on_mount(self) -> None:
        await self.refresh_profile()

    async def refresh_profile(self) -> None:
        repo_root = _resolve_repo_root()
        summary = _build_summary(repo_root)
        self.query_one("#profile-summary", Static).update(summary)
        markdown = _load_source_of_truth_markdown(repo_root)
        await self.query_one("#profile-doc", Markdown).update(markdown)
