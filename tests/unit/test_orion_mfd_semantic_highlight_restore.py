from __future__ import annotations

from pathlib import Path

from rich.text import Text

from qiki.services.operator_console.orion_v.ui_rich import (
    semantic_style_enabled,
    style_orion_markup,
    style_orion_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ORION_V = REPO_ROOT / "src/qiki/services/operator_console/orion_v"
SCREENS = ORION_V / "screens"


def _span_styles(text: Text) -> tuple[str, ...]:
    return tuple(str(span.style) for span in text.spans)


def test_style_orion_text_restores_semantic_status_coloring() -> None:
    rendered = style_orion_text(
        "RIGHT MFD / ПИТ\n"
        "SoC_bat: unknown\n"
        "peak_ready: limited\n"
        "reason_codes: CAP_LOW / POWER_TELEM_MISSING / MODULE_PASSPORT_INVALID\n"
        "source: audit_backed\n",
        domain="right",
    )

    assert isinstance(rendered, Text)
    assert rendered.plain.startswith("RIGHT MFD / ПИТ")
    styles = _span_styles(rendered)
    assert any("#667276" in style for style in styles)  # unknown / no-data
    assert any("#e0a13a" in style for style in styles)  # limited / warning
    assert any("#e05a4f" in style for style in styles)  # CAP_LOW / critical blocker
    assert any("#8aa0c8" in style for style in styles)  # source/proof label


def test_style_orion_text_is_markup_blind_for_runtime_values() -> None:
    rendered = style_orion_text("module: [red]fake[/] status: attached", domain="right")

    assert rendered.plain == "module: [red]fake[/] status: attached"
    assert "red" not in _span_styles(rendered)
    assert any("#55c878" in style for style in _span_styles(rendered))


def test_style_orion_markup_keeps_trusted_markup_and_styles_plain_tokens() -> None:
    rendered = style_orion_markup("[@click=x]open[/] status: BLOCKED source: audit_backed")

    assert "[@click=x]" in rendered
    assert "[/]" in rendered
    assert "BLOCKED" in rendered
    assert "#e05a4f" in rendered
    assert "#55c878" in rendered


def test_semantic_style_defaults_to_enabled(monkeypatch) -> None:
    monkeypatch.delenv("ORIONV_VISUAL_STYLE", raising=False)
    assert semantic_style_enabled() is True
    monkeypatch.setenv("ORIONV_VISUAL_STYLE", "plain")
    assert semantic_style_enabled() is False


def test_mfd_screens_use_semantic_update_on_visible_panes() -> None:
    cockpit = (SCREENS / "cockpit.py").read_text()
    systems = (SCREENS / "systems.py").read_text()
    evidence = (SCREENS / "evidence_stream.py").read_text()

    assert "from qiki.services.operator_console.orion_v.ui_rich import semantic_update" in cockpit
    assert "from qiki.services.operator_console.orion_v.ui_rich import semantic_update" in systems
    assert "from qiki.services.operator_console.orion_v.ui_rich import semantic_update" in evidence

    assert "_visual_domain(selector)" in cockpit
    assert "_semantic_static_update" in systems
    assert "#orionv-systems-mfd-left-screen" in systems
    assert "#orionv-systems-mfd-right-screen" in systems
    assert "#orionv-evidence-mfd-left-screen" in evidence
    assert "#orionv-evidence-mfd-right-screen" in evidence
