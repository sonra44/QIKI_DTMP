"""Small ORION V MFD layout helpers.

This module restores the old left/right MFD shell contract without making the
MFD renderer a source of truth.  It only formats already-existing view-model
lines for Textual panes.  Runtime state still comes from the body/power/evidence
view models, audit projections, and telemetry snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MFDButtonSpec:
    page: str
    button_id: str
    label: str
    side: str


MFD_LEFT_BUTTONS: tuple[MFDButtonSpec, ...] = (
    MFDButtonSpec("radar", "orionv-mfd-left-radar", "РАДАР", "left"),
    MFDButtonSpec("nav", "orionv-mfd-left-nav", "НАВ", "left"),
    MFDButtonSpec("target", "orionv-mfd-left-target", "ЦЕЛЬ", "left"),
    MFDButtonSpec("sector", "orionv-mfd-left-sector", "СЕКТОР", "left"),
    MFDButtonSpec("mission", "orionv-mfd-left-mission", "МИССИЯ", "left"),
)

MFD_RIGHT_BUTTONS: tuple[MFDButtonSpec, ...] = (
    MFDButtonSpec("systems", "orionv-mfd-right-systems", "СИСТ", "right"),
    MFDButtonSpec("sensors", "orionv-mfd-right-sensors", "СЕНС", "right"),
    MFDButtonSpec("power", "orionv-mfd-right-power", "ПИТ", "right"),
    MFDButtonSpec("thermal", "orionv-mfd-right-thermal", "ТЕПЛО", "right"),
    MFDButtonSpec("comms", "orionv-mfd-right-comms", "СВЯЗЬ", "right"),
    MFDButtonSpec("propulsion", "orionv-mfd-right-propulsion", "ДВИГ", "right"),
    MFDButtonSpec("docking", "orionv-mfd-right-docking", "СТЫК", "right"),
    MFDButtonSpec("journal", "orionv-mfd-right-journal", "ЖУРН", "right"),
    MFDButtonSpec("procedures", "orionv-mfd-right-procedures", "ПРОЦ", "right"),
)

MFD_DEFAULT_LEFT_PAGE = "radar"
MFD_DEFAULT_RIGHT_PAGE = "systems"


def mfd_page_keys(side: str) -> tuple[str, ...]:
    return tuple(spec.page for spec in mfd_button_specs(side))


def normalize_mfd_page(side: str, page: str | None) -> str:
    normalized_side = str(side or "").strip().lower()
    keys = mfd_page_keys(normalized_side)
    default = MFD_DEFAULT_LEFT_PAGE if normalized_side == "left" else MFD_DEFAULT_RIGHT_PAGE
    candidate = str(page or "").strip().lower()
    return candidate if candidate in keys else default


def mfd_page_label(side: str, page: str | None) -> str:
    normalized_side = str(side or "").strip().lower()
    normalized_page = normalize_mfd_page(normalized_side, page)
    for spec in mfd_button_specs(normalized_side):
        if spec.page == normalized_page:
            return spec.label
    return normalized_page.upper()


def mfd_button_selection_from_id(button_id: str | None) -> tuple[str, str] | None:
    """Return (side, page) for ORION MFD button ids.

    The systems screen prefixes the same physical-button ids with ``systems-`` to
    keep Textual ids unique.  This parser intentionally ignores that prefix and
    treats both screens as the same MFD page-selection contract.
    """
    raw = str(button_id or "").strip()
    if raw.startswith("systems-"):
        raw = raw.removeprefix("systems-")
    for side in ("left", "right"):
        prefix = f"orionv-mfd-{side}-"
        if raw.startswith(prefix):
            page = raw.removeprefix(prefix).strip().lower()
            normalized = normalize_mfd_page(side, page)
            if normalized == page:
                return side, normalized
    return None


def mfd_button_class(spec: MFDButtonSpec, *, active_left: str | None, active_right: str | None) -> str:
    active = active_left if spec.side == "left" else active_right
    return "mfd-active" if spec.page == normalize_mfd_page(spec.side, active) else ""

MFD_SOFTKEYS: tuple[str, ...] = (
    "B attach self-check",
    "R reset",
    "N next face",
    "P previous face",
    "F8 evidence",
)


def mfd_button_specs(side: str) -> tuple[MFDButtonSpec, ...]:
    normalized = str(side or "").strip().lower()
    if normalized == "left":
        return MFD_LEFT_BUTTONS
    if normalized == "right":
        return MFD_RIGHT_BUTTONS
    raise ValueError(f"unknown MFD side: {side!r}")


def clipped_lines(lines: Iterable[str], *, limit: int = 16) -> tuple[str, ...]:
    """Return non-empty lines clipped for a pane.

    The function intentionally performs only display shaping.  It does not parse
    facts back out of text and does not invent missing state.
    """
    out: list[str] = []
    for raw in lines:
        line = str(raw).rstrip()
        if not line:
            continue
        out.append(line)
        if len(out) >= limit:
            break
    return tuple(out)


def section_lines(title: str, lines: Iterable[str], *, limit: int = 12) -> tuple[str, ...]:
    rows = clipped_lines(lines, limit=limit)
    return (title, "─" * min(28, max(8, len(title))), *rows) if rows else (title, "─" * min(28, len(title)), "no data")


def softkey_bar(extra: Iterable[str] = ()) -> str:
    keys = (*MFD_SOFTKEYS, *tuple(str(item) for item in extra if str(item).strip()))
    return "SOFTKEYS: " + "  ".join(f"[{key}]" for key in keys)


def render_status_strip(*, mode: str, body: str, evidence: str, source: str) -> str:
    return " | ".join(
        (
            f"MODE: {mode}",
            f"BODY: {body}",
            f"EVIDENCE: {evidence}",
            f"SOURCE: {source}",
        )
    )
