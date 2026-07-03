"""ORION V evidence-card stream panel (route a, IF-NBL-001 step 1c).

A read-only vertical stream of evidence cards built from ONE telemetry snapshot via the
console-side adapters and the canon ``*_evidence`` projections — never from the legacy
contour and never by extending collector.build_*. v1 shows the NBL card; more slices
append here. Follows the existing ORION V idiom: a ``Static`` level-panel (not a Textual
Screen), shown/hidden by the app.
"""
from __future__ import annotations

from typing import Any, Mapping

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Static

from qiki.services.operator_console.orion_v.evidence_adapters import snapshot_to_nbl_record
from qiki.services.operator_console.orion_v.evidence_card_vm import EvidenceCardVM, nbl_evidence_to_card_vm
from qiki.services.operator_console.orion_v.nbl_evidence import nbl_to_evidence
from qiki.services.operator_console.orion_v.body_physics_view_model import (
    build_body_physics_evidence_card_vms,
)
from qiki.services.operator_console.orion_v.body_structure_view_model import (
    build_body_structure_evidence_card_vms,
)
from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    build_power_thermal_console_view_model_from_telemetry,
    build_power_thermal_evidence_card_vms,
)
from qiki.services.operator_console.orion_v.i18n_ru import state_ru
from qiki.services.operator_console.orion_v.widgets.evidence_card_view import OrionVEvidenceCard
from qiki.services.operator_console.orion_v.mfd_layout import clipped_lines, softkey_bar
from qiki.services.operator_console.orion_v.ui_rich import semantic_update

POWER_ACCUMULATOR_EVIDENCE_SUBSYSTEM = "POWER/ACCUMULATOR"
BODY_EVIDENCE_SUBSYSTEM = "BODY"


def _normalize_evidence_subsystem(value: str | None) -> str:
    return str(value or "").strip().upper()


def _clamp_evidence_index(cards: list[EvidenceCardVM], index: int) -> int:
    if not cards:
        return 0
    return max(0, min(index, len(cards) - 1))


def _find_evidence_card_index(cards: list[EvidenceCardVM], subsystem: str | None) -> int | None:
    wanted = _normalize_evidence_subsystem(subsystem)
    if not wanted:
        return None
    for index, card in enumerate(cards):
        if _normalize_evidence_subsystem(card.subsystem) == wanted:
            return index
    return None


def build_evidence_card_vms(snapshot: Mapping[str, Any]) -> list[EvidenceCardVM]:
    """Build read-only evidence-card VMs for one console snapshot.

    BODY cards are surfaced first so the operator sees the visible attach-lifecycle
    seed immediately. NBL remains visible below it. Each card is a projection of
    an evidence object; the view layer does not invent facts.
    """
    snapshot = snapshot or {}
    return [
        *build_body_structure_evidence_card_vms(),
        *build_body_physics_evidence_card_vms(),
        *build_power_thermal_evidence_card_vms(
            build_power_thermal_console_view_model_from_telemetry(snapshot)
        ),
        nbl_evidence_to_card_vm(nbl_to_evidence(snapshot_to_nbl_record(snapshot))),
    ]


def build_evidence_cards(snapshot: Mapping[str, Any]) -> list[OrionVEvidenceCard]:
    """Build the read-only evidence cards for one telemetry snapshot."""
    return [OrionVEvidenceCard(vm) for vm in build_evidence_card_vms(snapshot)]


def _render_evidence_list_mfd(cards: list[EvidenceCardVM], selected_index: int = 0) -> str:
    lines = [
        "ЛЕВЫЙ MFD / СПИСОК УЛИК",
        "источник: карточки-проекции | только чтение",
        "клавиши: ↑/↓ — выбор карточки | F1 — кокпит",
        "",
    ]
    selected_index = _clamp_evidence_index(cards, selected_index)
    if not cards:
        lines.append("улик пока нет")
    for index, card in enumerate(cards):
        marker = ">" if index == selected_index else " "
        human_index = index + 1
        lines.append(
            f"{marker}{human_index:02d}. {card.subsystem} | "
            f"{state_ru(card.state_key)} | {card.reason_text or '-'}"
        )
        lines.append(f"    {card.headline}")
    return "\n".join(clipped_lines(lines, limit=32))


def _render_evidence_detail_mfd(cards: list[EvidenceCardVM], selected_index: int = 0) -> str:
    selected_index = _clamp_evidence_index(cards, selected_index)
    lines = ["ПРАВЫЙ MFD / ДЕТАЛИ УЛИКИ"]
    if not cards:
        lines.extend(["выбрано: нет", "", "Деталей улики нет."])
        return "\n".join(lines)
    card = cards[selected_index]
    lines.extend(
        [
            f"выбрано: {selected_index + 1:02d}/{len(cards):02d} {card.subsystem}",
            "",
            f"подсистема: {card.subsystem}",
            f"состояние: {state_ru(card.state_key)}",
            f"заголовок: {card.headline}",
            f"причина: {card.reason_text or '-'}",
            "детали:",
            *[f"  {line}" for line in card.detail_lines],
            "",
            "граница:",
            "панель улик не исполняет команды и не создаёт runtime-состояние.",
        ]
    )
    return "\n".join(clipped_lines(lines, limit=34))


class OrionVEvidenceScreen(Static):
    """Read-only evidence-card stream level-panel for ORION V."""

    BINDINGS = [
        ("up", "select_previous_evidence_card", "Evidence previous"),
        ("down", "select_next_evidence_card", "Evidence next"),
        ("left", "select_previous_evidence_card", "Evidence previous"),
        ("right", "select_next_evidence_card", "Evidence next"),
    ]

    DEFAULT_CSS = """
    OrionVEvidenceScreen { height: 1fr; layout: vertical; }
    OrionVEvidenceScreen #orionv-evidence-title {
        height: auto; color: $text-muted; padding: 0 1;
    }
    OrionVEvidenceScreen #orionv-evidence-mfd-root {
        height: 1fr;
        layout: vertical;
    }
    OrionVEvidenceScreen #orionv-evidence-mfd-status {
        height: auto;
        max-height: 4;
        border: round #4f747c;
        background: #10181b;
        padding: 0 1;
    }
    OrionVEvidenceScreen #orionv-evidence-mfd-main {
        height: 1fr;
        layout: horizontal;
    }
    OrionVEvidenceScreen #orionv-evidence-mfd-left-screen,
    OrionVEvidenceScreen #orionv-evidence-mfd-right-screen {
        width: 1fr;
        height: 1fr;
        border: round #3a8294;
        background: #0d1417;
        padding: 0 1;
        margin: 0 1 0 0;
    }
    OrionVEvidenceScreen #orionv-evidence-mfd-right-screen {
        border: round #5f8a4a;
    }
    OrionVEvidenceScreen #orionv-evidence-mfd-softkeys {
        height: auto;
        border: round #617078;
        background: #0f1518;
        padding: 0 1;
        margin: 1 0 0 0;
    }
    OrionVEvidenceScreen #orionv-evidence-stream {
        display: none;
        height: 0;
    }
    """

    def __init__(
        self,
        snapshot: Mapping[str, Any] | None = None,
        *,
        preferred_card_type: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._snapshot = snapshot or {}
        self._selected_evidence_index = 0
        self._selected_evidence_subsystem = ""
        self._pending_preferred_evidence_subsystem = _normalize_evidence_subsystem(preferred_card_type)

    def compose(self) -> ComposeResult:
        yield Static("ORION · EVIDENCE (read-only)", id="orionv-evidence-title")
        with Container(id="orionv-evidence-mfd-root"):
            yield Static("", id="orionv-evidence-mfd-status")
            with Container(id="orionv-evidence-mfd-main"):
                yield Static("", id="orionv-evidence-mfd-left-screen")
                yield Static("", id="orionv-evidence-mfd-right-screen")
            yield Static("", id="orionv-evidence-mfd-softkeys")
        with VerticalScroll(id="orionv-evidence-stream"):
            for card in build_evidence_cards(self._snapshot):
                yield card

    def on_mount(self) -> None:
        self._refresh_mfd()

    @property
    def selected_evidence_index(self) -> int:
        """Zero-based selected evidence-card index for tests and app-level routing."""
        return self._selected_evidence_index

    @property
    def selected_evidence_subsystem(self) -> str:
        """Selected evidence subsystem name, for example ``POWER/ACCUMULATOR``."""
        return self._selected_evidence_subsystem

    def update_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        preferred_card_type: str | None = None,
    ) -> None:
        """Rebuild the stream from a fresh snapshot (stable IDs / point-update come later)."""
        self._snapshot = snapshot or {}
        if preferred_card_type is not None:
            self._pending_preferred_evidence_subsystem = _normalize_evidence_subsystem(preferred_card_type)
        stream = self.query_one("#orionv-evidence-stream", VerticalScroll)
        stream.remove_children()
        stream.mount(*build_evidence_cards(self._snapshot))
        self._refresh_mfd()

    def prefer_evidence_card(self, subsystem: str | None) -> None:
        """Prefer a detail card by subsystem on the next MFD refresh.

        The preference is consumed once when a matching card exists. After that,
        manual UP/DOWN selection remains stable across ordinary snapshot refreshes.
        """
        self._pending_preferred_evidence_subsystem = _normalize_evidence_subsystem(subsystem)
        self._refresh_mfd()

    def select_next_evidence_card(self) -> None:
        cards = build_evidence_card_vms(self._snapshot)
        if not cards:
            self._selected_evidence_index = 0
            self._selected_evidence_subsystem = ""
        else:
            self._selected_evidence_index = min(self._selected_evidence_index + 1, len(cards) - 1)
            self._selected_evidence_subsystem = cards[self._selected_evidence_index].subsystem
        self._pending_preferred_evidence_subsystem = ""
        self._refresh_mfd()

    def select_previous_evidence_card(self) -> None:
        cards = build_evidence_card_vms(self._snapshot)
        if not cards:
            self._selected_evidence_index = 0
            self._selected_evidence_subsystem = ""
        else:
            self._selected_evidence_index = max(0, self._selected_evidence_index - 1)
            self._selected_evidence_subsystem = cards[self._selected_evidence_index].subsystem
        self._pending_preferred_evidence_subsystem = ""
        self._refresh_mfd()

    def action_select_next_evidence_card(self) -> None:
        self.select_next_evidence_card()

    def action_select_previous_evidence_card(self) -> None:
        self.select_previous_evidence_card()

    def _resolve_selected_index(self, cards: list[EvidenceCardVM]) -> int:
        preferred_index = _find_evidence_card_index(cards, self._pending_preferred_evidence_subsystem)
        if preferred_index is not None:
            self._pending_preferred_evidence_subsystem = ""
            return preferred_index
        current_index = _find_evidence_card_index(cards, self._selected_evidence_subsystem)
        if current_index is not None:
            return current_index
        return _clamp_evidence_index(cards, self._selected_evidence_index)

    def _refresh_mfd(self) -> None:
        cards = build_evidence_card_vms(self._snapshot)
        self._selected_evidence_index = self._resolve_selected_index(cards)
        if cards:
            self._selected_evidence_subsystem = cards[self._selected_evidence_index].subsystem
        else:
            self._selected_evidence_subsystem = ""
        semantic_update(
            self.query_one("#orionv-evidence-mfd-status", Static),
            f"ORION V / F8 УЛИКИ | карточек: {len(cards)} | режим: только чтение | "
            f"выбрано: {self._selected_evidence_subsystem or 'нет'} | источник: аудит/посевные проекции",
            domain="evidence",
        )
        semantic_update(
            self.query_one("#orionv-evidence-mfd-left-screen", Static),
            _render_evidence_list_mfd(cards, self._selected_evidence_index),
            domain="evidence",
        )
        semantic_update(
            self.query_one("#orionv-evidence-mfd-right-screen", Static),
            _render_evidence_detail_mfd(cards, self._selected_evidence_index),
            domain="evidence",
        )
        semantic_update(
            self.query_one("#orionv-evidence-mfd-softkeys", Static),
            softkey_bar(("UP/DOWN select", "read-only")),
            domain="evidence",
        )
