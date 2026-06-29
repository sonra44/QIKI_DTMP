from __future__ import annotations

from pathlib import Path

from qiki.services.operator_console.orion_v.mfd_layout import (
    MFD_DEFAULT_LEFT_PAGE,
    MFD_DEFAULT_RIGHT_PAGE,
    mfd_button_class,
    mfd_button_selection_from_id,
    mfd_button_specs,
    mfd_page_label,
    normalize_mfd_page,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ORION_V = REPO_ROOT / "src/qiki/services/operator_console/orion_v"
SCREENS = ORION_V / "screens"


def test_mfd_page_normalization_and_labels_are_stable() -> None:
    assert MFD_DEFAULT_LEFT_PAGE == "radar"
    assert MFD_DEFAULT_RIGHT_PAGE == "systems"
    assert normalize_mfd_page("left", "nav") == "nav"
    assert normalize_mfd_page("right", "thermal") == "thermal"
    assert normalize_mfd_page("left", "missing") == "radar"
    assert normalize_mfd_page("right", "missing") == "systems"
    assert mfd_page_label("left", "mission") == "МИССИЯ"
    assert mfd_page_label("right", "power") == "ПИТ"


def test_mfd_button_id_parser_handles_cockpit_and_systems_ids() -> None:
    assert mfd_button_selection_from_id("orionv-mfd-left-nav") == ("left", "nav")
    assert mfd_button_selection_from_id("orionv-mfd-right-power") == ("right", "power")
    assert mfd_button_selection_from_id("systems-orionv-mfd-left-target") == ("left", "target")
    assert mfd_button_selection_from_id("systems-orionv-mfd-right-thermal") == ("right", "thermal")
    assert mfd_button_selection_from_id("orionv-cockpit-jump-power") is None


def test_mfd_button_active_class_is_page_state_driven() -> None:
    left_nav = next(spec for spec in mfd_button_specs("left") if spec.page == "nav")
    left_radar = next(spec for spec in mfd_button_specs("left") if spec.page == "radar")
    right_power = next(spec for spec in mfd_button_specs("right") if spec.page == "power")
    assert mfd_button_class(left_nav, active_left="nav", active_right="systems") == "mfd-active"
    assert mfd_button_class(left_radar, active_left="nav", active_right="systems") == ""
    assert mfd_button_class(right_power, active_left="nav", active_right="power") == "mfd-active"


def test_app_routes_mfd_buttons_to_page_state_without_runtime_actions() -> None:
    app = (ORION_V / "app.py").read_text()
    assert "mfd_button_selection_from_id(button_id)" in app
    assert "self._select_mfd_page(side=side, page=page)" in app
    assert "self._active_mfd_left_page" in app
    assert "self._active_mfd_right_page" in app
    mfd_page_selector = app[
        app.index("def _select_mfd_page") : app.index("def _handle_action_bar_action")
    ]
    assert "run_attach_pipeline" not in mfd_page_selector


def test_cockpit_and_systems_accept_active_mfd_page_state() -> None:
    cockpit = (SCREENS / "cockpit.py").read_text()
    systems = (SCREENS / "systems.py").read_text()

    assert "active_left_mfd_page" in cockpit
    assert "active_right_mfd_page" in cockpit
    assert 'normalize_mfd_page("left"' in cockpit
    assert 'normalize_mfd_page("right"' in cockpit
    assert "mfd_button_class(" in cockpit

    assert "active_left_mfd_page" in systems
    assert "active_right_page" in systems
    assert "render_left_mfd_page(" in systems
    assert "render_right_mfd_page(" in systems
    assert "inspector_lines=format_subsystem_inspector(selected_view)" in systems
