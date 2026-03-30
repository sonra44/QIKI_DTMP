import pytest


def test_orion_summary_uses_tier_a_semantic_blocks() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()

    blocks = app._build_summary_blocks()
    ids = [str(getattr(b, "block_id", "")) for b in blocks]
    assert ids == [
        "health",
        "energy",
        "motion_safety",
        "threats",
        "actions_incidents",
    ]
