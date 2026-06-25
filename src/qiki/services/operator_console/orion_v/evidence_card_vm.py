"""Presentation view-model + renderer for ORION evidence cards (route a).

Maps a read-only ``*_evidence`` projection (e.g. ``NblPacketEvidence``) into a
slice-agnostic ``EvidenceCardVM`` and renders honest, decision-first card text.
Honesty (ADR-0014, §17.10): missing / target-only are shown explicitly; nothing is
invented here — the card only re-presents what the evidence already states.

Pure module (no Textual import) so the rendering logic is unit-testable in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# state_key -> (glyph, Textual theme color). Glyphs are 1-cell-safe: ◌ ✓ ✗ are
# East-Asian-Width Neutral; ⚠ is used bare (no U+FE0F variation selector). '●'
# (U+25CF) is Ambiguous-width and breaks monospace alignment — deliberately NOT used.
STATE_STYLE: dict[str, tuple[str, str]] = {
    "ok":       ("✓", "$success"),
    "degraded": ("⚠", "$warning"),
    "blocked":  ("✗", "$error"),
    "missing":  ("◌", "$text-muted"),
    "target":   ("◌", "$accent"),
}

_RU = {"missing": "нет данных", "unknown": "неизвестно", "": "нет данных"}


@dataclass(frozen=True, slots=True)
class EvidenceCardVM:
    subsystem: str
    state_key: str               # key into STATE_STYLE
    headline: str                # decision-first one-liner
    reason_text: str             # reason_codes joined (identifiers; not translated)
    detail_lines: tuple[str, ...]


def _ru(value: Any) -> str:
    text = str(value or "").strip()
    return _RU.get(text, text)


def nbl_evidence_to_card_vm(ev: Any) -> EvidenceCardVM:
    """``NblPacketEvidence`` -> ``EvidenceCardVM``. NBL is rules-only / target-only
    (§17.10); the card is never "ok"/sent unless the evidence truly says so."""
    state_key = "ok" if getattr(ev, "is_sent", False) else "target"
    headline = "пакет отправлен" if state_key == "ok" else "не реализовано · target-only"
    return EvidenceCardVM(
        subsystem="NBL",
        state_key=state_key,
        headline=headline,
        reason_text=", ".join(ev.reason_codes),
        detail_lines=(
            f"критичность: {_ru(ev.criticality)}",
            f"класс пакета: {_ru(ev.payload_class)}",
            f"стоимость: {ev.cost_label.replace('missing', 'нет данных')}",
            f"доставка: {_ru(ev.delivery_confidence)}",
        ),
    )


def render_card_text(vm: EvidenceCardVM) -> str:
    """Render an ``EvidenceCardVM`` into Textual content markup (decision-first)."""
    glyph, color = STATE_STYLE.get(vm.state_key, STATE_STYLE["missing"])
    lines = [f"[{color} b]{glyph} {vm.subsystem}[/]  {vm.headline}"]
    if vm.reason_text:
        lines.append(f"  [dim]причина:[/] {vm.reason_text}")
    for line in vm.detail_lines:
        lines.append(f"  [dim]{line}[/]")
    return "\n".join(lines)
