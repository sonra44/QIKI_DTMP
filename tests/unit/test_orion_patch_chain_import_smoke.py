from __future__ import annotations

import importlib


def test_body_structure_face_map_exports_legacy_and_textual_api_names() -> None:
    mod = importlib.import_module("qiki.services.operator_console.orion_v.body_structure_face_map")

    for name in (
        "BodyStructureFaceRow",
        "BodyStructureFaceView",
        "build_body_structure_face_rows",
        "build_face_views",
        "format_body_structure_face_map",
        "format_face_map_lines",
        "normalize_selected_face_id",
        "default_selected_face_id",
        "selected_face_row",
        "selected_face_view",
    ):
        assert hasattr(mod, name), name


def test_orion_body_and_power_view_model_import_smoke() -> None:
    importlib.import_module("qiki.services.operator_console.orion_v.body_structure_view_model")
    importlib.import_module("qiki.services.operator_console.orion_v.body_physics_view_model")
    importlib.import_module("qiki.services.operator_console.orion_v.power_thermal_view_model")
    importlib.import_module("qiki.services.operator_console.orion_v.evidence_card")
    importlib.import_module("qiki.services.operator_console.orion_v.evidence_card_mapping")


def test_textual_screen_import_smoke_when_textual_is_installed() -> None:
    import pytest

    pytest.importorskip("textual")
    importlib.import_module("qiki.services.operator_console.orion_v.screens.systems")
    importlib.import_module("qiki.services.operator_console.orion_v.screens.evidence_stream")
    importlib.import_module("qiki.services.operator_console.orion_v.screens.body_structure_textual")
    importlib.import_module("qiki.services.operator_console.orion_v.screens.power_thermal_textual")
    importlib.import_module("qiki.services.operator_console.orion_v.widgets.body_physics_panel")
