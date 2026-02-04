import pytest


def test_orion_summary_mission_shows_no_data_message_when_absent() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp
    from qiki.services.operator_console.ui import i18n as I18N

    app = OrionApp()

    blocks = app._build_summary_blocks()
    mission = [b for b in blocks if getattr(b, "block_id", None) == "mission"]
    assert len(mission) == 1
    b = mission[0]
    assert b.status == "non_goal"
    assert b.value == I18N.bidi("No mission/task data", "Нет данных миссии/задач")
