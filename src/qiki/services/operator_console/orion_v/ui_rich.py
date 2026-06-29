"""Semantic Rich text helpers for ORION V operator surfaces.

The helpers in this module restore the old ORION semantic highlighting layer
without parsing runtime text as Rich/Textual markup.  Runtime values are appended
as plain text and only known operator status tokens receive styles.  Use
``style_orion_markup`` only for trusted local UI markup that must keep Textual
links or tags.
"""
from __future__ import annotations

import os
import re
from typing import Any

from rich.text import Text

ORION_UI_COLORS: dict[str, str] = {
    "text": "#d8ded8",
    "muted": "#7f8f92",
    "separator": "#2b3f45",
    "label": "#65a7b4",
    "radar": "#64c7d8",
    "body": "#8fbf78",
    "qiki": "#d6b35f",
    "proof": "#8aa0c8",
    "ok": "#55c878",
    "warn": "#e0a13a",
    "crit": "#e05a4f",
    "nodata": "#667276",
    "active": "#7de3f2",
}

_STATUS_RE = re.compile(
    r"(?P<token>"
    r"OK|READY|fresh|TRUSTED|trusted|healthy|nominal|validated|attached|audit[-_ ]backed|"
    r"DEGRADED|degraded|WARN|WARNING|ВНИМ|pending|limited|PEAK_LIMITED|seed_only|seed-only|"
    r"target-only|calculation-required|not claimed|not_evaluated|not-evaluated|"
    r"CRIT|CRITICAL|FAILED|ERROR|BLOCKED|denied|rejected|CAP_LOW|CAP_HOT|BAT_LOW|"
    r"PDU_PEAK_DENIED|PDU_NOT_IMPLEMENTED|THERMAL_BLOCK|POWER_TELEM_MISSING|POWER_TELEM_STALE|"
    r"RTG_NOT_PEAK_SOURCE|REACTOR_EXTERNAL_ONLY|SAFE_LOCKED|BUS_UNSTABLE|LOAD_SHED_ACTIVE|"
    r"SOURCE_UNAVAILABLE|bus_unstable|load_shedding|overcurrent|stale|conflicting|"
    r"NO_LIVE_POWER_SOURCE|"
    r"MODULE_PASSPORT_MISSING|MODULE_PASSPORT_INVALID|MOUNT_POINT_UNKNOWN|"
    r"MOUNT_POINT_OCCUPIED|MODULE_MOUNT_CLASS_FORBIDDEN|"
    r"NODATA|NO DATA|Нет данных|UNKNOWN|unknown|absent|missing|TBD|not implemented|"
    r"ACTIVE|inactive|STANDBY|STOPPED|RUNNING|PAUSED|"
    r"NEXT|Действие|ПОСЛЕДСТВИЕ|Proof|PROOF|Truth|BOUNDARY|Boundary|RAW FACTS|WARNINGS|SENSOR ROWS"
    r")",
    re.IGNORECASE,
)

_DOMAIN_STYLE = {
    "left": f"bold {ORION_UI_COLORS['radar']}",
    "right": f"bold {ORION_UI_COLORS['body']}",
    "qiki": f"bold {ORION_UI_COLORS['qiki']}",
    "status": f"bold {ORION_UI_COLORS['active']}",
    "evidence": f"bold {ORION_UI_COLORS['proof']}",
    "power": f"bold {ORION_UI_COLORS['qiki']}",
}


def semantic_style_enabled() -> bool:
    """Return whether semantic MFD coloring is enabled.

    The flag mirrors the old console behavior.  Set ``ORIONV_VISUAL_STYLE=plain``
    to force pure strings in environments that cannot render Rich Text.
    """
    value = os.getenv("ORIONV_VISUAL_STYLE", "semantic").strip().lower()
    return (value or "semantic") == "semantic"


def semantic_update(widget: Any, text: str, *, domain: str = "status") -> None:
    """Update a Static-like widget with semantic highlighting when enabled.

    This helper intentionally never treats runtime text as markup.  It is safe
    for source-backed ORION text panes where values may contain brackets or user
    / telemetry supplied strings.
    """
    if semantic_style_enabled():
        widget.update(style_orion_text(text, domain=domain))
    else:
        widget.update(text)


def style_orion_markup(value: str) -> str:
    """Inject status-token colors into a trusted Textual markup string.

    Bracketed markup chunks are passed through untouched.  Use this only for
    local UI markup where Textual actions/links must be preserved.
    """
    out: list[str] = []
    pos = 0
    for match in re.finditer(r"\[[^\]]*\]", value):
        out.append(_inject_status_tokens(value[pos : match.start()]))
        out.append(match.group(0))
        pos = match.end()
    out.append(_inject_status_tokens(value[pos:]))
    return "".join(out)


def style_orion_text(value: str, *, domain: str = "status") -> Text:
    """Return safe Rich Text styling for ORION MFD surfaces."""
    rendered = Text()
    for index, line in enumerate(str(value or "").splitlines()):
        if index:
            rendered.append("\n")
        _append_styled_line(rendered, line, domain=domain)
    return rendered


def _inject_status_tokens(segment: str) -> str:
    parts: list[str] = []
    pos = 0
    for match in _STATUS_RE.finditer(segment):
        start, end = match.span()
        prev_ch = segment[start - 1] if start > 0 else ""
        next_ch = segment[end] if end < len(segment) else ""
        if prev_ch.isalnum() or prev_ch == "_" or next_ch.isalnum() or next_ch == "_":
            continue
        token = match.group("token")
        style = _style_for_token(token)
        if style == ORION_UI_COLORS["text"]:
            continue
        parts.append(segment[pos:start])
        parts.append(f"[{style}]{token}[/]")
        pos = end
    parts.append(segment[pos:])
    return "".join(parts)


def _append_styled_line(rendered: Text, line: str, *, domain: str) -> None:
    stripped = line.strip()
    if not stripped:
        return

    if _is_panel_heading(stripped):
        _append_panel_heading(rendered, line, domain=domain)
        return

    if stripped.endswith(":") and len(stripped) <= 32:
        rendered.append(line, style=_DOMAIN_STYLE.get(domain, _DOMAIN_STYLE["status"]))
        return

    proof_prefixes = (
        "PROOF:",
        "Proof:",
        "BOUNDARY:",
        "Boundary:",
        "Truth:",
        "source:",
        "trust:",
        "evidence:",
        "read_only:",
    )
    if stripped.startswith(proof_prefixes):
        _append_label_value(
            rendered,
            line,
            label_style=f"bold {ORION_UI_COLORS['proof']}",
            value_style=ORION_UI_COLORS["muted"],
        )
        return

    if stripped.startswith(("NEXT:", "Действие:", "ПОСЛЕДСТВИЕ", "Последствие:")):
        _append_label_value(
            rendered,
            line,
            label_style=f"bold {ORION_UI_COLORS['qiki']}",
            value_style=ORION_UI_COLORS["text"],
        )
        return

    if ":" in stripped and _starts_with_label(line):
        _append_label_value(
            rendered,
            line,
            label_style=ORION_UI_COLORS["label"],
            value_style=ORION_UI_COLORS["text"],
        )
        return

    if stripped.startswith(("-", "–", "#", "•", "◆")):
        indent = len(line) - len(line.lstrip())
        marker = line[indent]
        rendered.append(line[:indent])
        rendered.append(marker, style=ORION_UI_COLORS["separator"])
        _append_status_highlighted(
            rendered,
            line[indent + 1 :],
            default_style=ORION_UI_COLORS["muted"],
        )
        return

    _append_status_highlighted(rendered, line, default_style=ORION_UI_COLORS["text"])


def _is_panel_heading(stripped: str) -> bool:
    return stripped.startswith(
        (
            "LEFT MFD",
            "RIGHT MFD",
            "ЛЕВЫЙ MFD",
            "ПРАВЫЙ MFD",
            "ORION V",
            "МОСТИК",
            "ЧАТ QIKI",
        )
    )


def _append_panel_heading(rendered: Text, line: str, *, domain: str) -> None:
    heading_style = _DOMAIN_STYLE.get(domain, _DOMAIN_STYLE["status"])
    for part_index, part in enumerate(line.split(" / ")):
        if part_index:
            rendered.append(" / ", style=ORION_UI_COLORS["separator"])
        rendered.append(part, style=heading_style if part_index == 0 else ORION_UI_COLORS["text"])


def _starts_with_label(line: str) -> bool:
    label = line.lstrip().split(":", 1)[0]
    return 1 <= len(label) <= 32 and not label.startswith(("http", "qiki."))


def _append_label_value(rendered: Text, line: str, *, label_style: str, value_style: str) -> None:
    indent_len = len(line) - len(line.lstrip())
    if indent_len:
        rendered.append(line[:indent_len])
    body = line[indent_len:]
    label, sep, rest = body.partition(":")
    rendered.append(label, style=label_style)
    rendered.append(sep, style=ORION_UI_COLORS["separator"])
    _append_status_highlighted(rendered, rest, default_style=value_style)


def _append_status_highlighted(rendered: Text, value: str, *, default_style: str) -> None:
    pos = 0
    for match in _STATUS_RE.finditer(value):
        start, end = match.span()
        prev_ch = value[start - 1] if start > 0 else ""
        next_ch = value[end] if end < len(value) else ""
        if prev_ch.isalnum() or prev_ch == "_" or next_ch.isalnum() or next_ch == "_":
            continue
        if start > pos:
            rendered.append(value[pos:start], style=default_style)
        token = match.group("token")
        rendered.append(token, style=_style_for_token(token))
        pos = end
    if pos < len(value):
        rendered.append(value[pos:], style=default_style)


def _style_for_token(token: str) -> str:
    normalized = token.strip().lower().replace("_", "-")
    if normalized in {
        "ok",
        "ready",
        "fresh",
        "trusted",
        "healthy",
        "nominal",
        "running",
        "validated",
        "attached",
        "audit-backed",
    }:
        return f"bold {ORION_UI_COLORS['ok']}"
    if normalized in {
        "degraded",
        "warn",
        "warning",
        "вним",
        "pending",
        "paused",
        "limited",
        "peak-limited",
        "power-telem-stale",
        "seed-only",
        "target-only",
        "calculation-required",
        "not claimed",
        "not-evaluated",
    }:
        return f"bold {ORION_UI_COLORS['warn']}"
    if normalized in {
        "crit",
        "critical",
        "failed",
        "error",
        "blocked",
        "denied",
        "rejected",
        "cap-low",
        "cap-hot",
        "bat-low",
        "pdu-peak-denied",
        "pdu-not-implemented",
        "thermal-block",
        "safe-locked",
        "bus-unstable",
        "load-shed-active",
        "module-passport-missing",
        "module-passport-invalid",
        "mount-point-unknown",
        "mount-point-occupied",
        "module-mount-class-forbidden",
    }:
        return f"bold {ORION_UI_COLORS['crit']}"
    if normalized in {
        "nodata",
        "no data",
        "нет данных",
        "unknown",
        "absent",
        "missing",
        "tbd",
        "not implemented",
        "power-telem-missing",
        "no-live-power-source",
    }:
        return ORION_UI_COLORS["nodata"]
    if normalized in {"active"}:
        return f"bold {ORION_UI_COLORS['active']}"
    if normalized in {"inactive", "standby", "stopped"}:
        return f"bold {ORION_UI_COLORS['warn']}"
    if normalized in {"next", "действие", "последствие"}:
        return f"bold {ORION_UI_COLORS['qiki']}"
    if normalized in {"proof", "truth", "boundary", "raw facts", "warnings", "sensor rows"}:
        return f"bold {ORION_UI_COLORS['proof']}"
    return ORION_UI_COLORS["text"]
