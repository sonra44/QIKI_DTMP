from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_test_gate_and_handoff_docs_are_present() -> None:
    gate = ROOT / "scripts" / "release_test_gate.sh"
    handoff = ROOT / "docs" / "TESTING_HANDOFF.md"
    tui_guide = ROOT / "docs" / "TUI_GUIDE.md"

    assert gate.exists()
    assert gate.stat().st_mode & 0o111
    assert handoff.exists()
    assert tui_guide.exists()


def test_final_handoff_preserves_datatable_operator_features() -> None:
    tui_app = (ROOT / "src" / "project_introspector" / "tui_app.py").read_text(encoding="utf-8")
    table_model = (ROOT / "src" / "project_introspector" / "tui_table_model.py").read_text(encoding="utf-8")
    tui_text = (ROOT / "src" / "project_introspector" / "tui_text.py").read_text(encoding="utf-8")

    assert "DataTable" in tui_app
    assert "overview-data-table" in tui_app
    assert "filter_operator_modules" in table_model
    assert "operator_module_table_headers" in table_model
    assert "operator_module_table_col_module" in tui_text
