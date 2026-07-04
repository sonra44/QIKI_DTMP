from __future__ import annotations

from pathlib import Path

from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    reset_body_structure_interactive_state,
    select_next_body_structure_face,
    select_previous_body_structure_face,
)
from qiki.services.operator_console.orion_v.body_structure_view_model import (
    get_body_structure_console_view_model,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ORION_V = REPO_ROOT / "src/qiki/services/operator_console/orion_v"
WIDGETS = ORION_V / "widgets"
SCREENS = ORION_V / "screens"


def test_previous_face_navigation_cycles_back_without_mutating_body() -> None:
    reset_body_structure_interactive_state()
    vm0 = get_body_structure_console_view_model()
    assert vm0.selected_face_id == "F06"
    assert vm0.attached_modules_count == 0

    select_next_body_structure_face()
    vm1 = get_body_structure_console_view_model()
    assert vm1.selected_face_id == "F07"
    assert vm1.attached_modules_count == 0

    select_previous_body_structure_face()
    vm2 = get_body_structure_console_view_model()
    assert vm2.selected_face_id == "F06"
    assert vm2.attached_modules_count == 0
    assert vm2.after_mount_state == "free"


def test_textual_body_dashboard_files_are_present_and_use_widgets() -> None:
    dashboard = (SCREENS / "body_structure_textual.py").read_text()
    assert "BodyStructureTextualDashboard" in dashboard
    assert "BodyStatusBar" in dashboard
    assert "FaceMapTable" in dashboard
    assert "SelectedFacePanel" in dashboard
    assert "BodyEvidencePanel" in dashboard
    assert "ComposeResult" in dashboard
    assert "Horizontal" in dashboard
    assert "Vertical" in dashboard

    face_table = (WIDGETS / "face_map_table.py").read_text()
    assert "from textual.widgets import DataTable" in face_table
    assert "class FaceMapTable(DataTable)" in face_table
    assert "add_columns" in face_table
    assert "add_row" in face_table
    assert "face_id" in face_table
    assert "occupancy" in face_table


def test_systems_screen_mounts_textual_body_dashboard() -> None:
    systems = (SCREENS / "systems.py").read_text()
    assert "BodyStructureTextualDashboard" in systems
    assert 'id="orionv-body-structure-dashboard"' in systems
    assert "update_view_model(" in systems
    assert "get_body_structure_console_view_model()" in systems


def test_orion_app_has_textual_body_previous_hotkey_and_action() -> None:
    app = (ORION_V / "app.py").read_text()
    assert "BODY face prev" in app
    assert '("p,P", "select_previous_body_structure_face"' in app  # обе раскладки: подсказки пульта пишут P заглавной
    assert "action_select_previous_body_structure_face" in app
    assert "select_previous_body_structure_face" in app


def test_textual_panels_keep_runtime_ready_and_evidence_semantics_visible() -> None:
    selected_panel = (WIDGETS / "selected_face_panel.py").read_text()
    evidence_panel = (WIDGETS / "body_evidence_panel.py").read_text()
    status_bar = (WIDGETS / "body_status_bar.py").read_text()

    assert "runtime_ready" in selected_panel
    assert "capability" in selected_panel
    assert "read_only" in evidence_panel
    assert "audit_event_id" in evidence_panel
    assert "evidence_card_id" in evidence_panel
    assert "QIKI BODY" in status_bar


def test_textual_dashboard_imports_when_textual_dependency_is_installed() -> None:
    import pytest

    pytest.importorskip("textual")
    from qiki.services.operator_console.orion_v.screens.body_structure_textual import (  # noqa: PLC0415
        BodyStructureTextualDashboard,
    )

    reset_body_structure_interactive_state()
    dashboard = BodyStructureTextualDashboard(get_body_structure_console_view_model())
    assert dashboard is not None
