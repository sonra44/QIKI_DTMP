from __future__ import annotations

from qiki.services.operator_console.orion_v.screens.deep_dive import OrionVDeepDiveScreen


class _CaptureDeepDive(OrionVDeepDiveScreen):
    def __init__(self) -> None:
        super().__init__()
        self.last_render: str = ""

    def update(self, renderable) -> None:  # noqa: ANN001
        self.last_render = str(renderable)


def _render_text(screen: _CaptureDeepDive) -> str:
    return screen.last_render


def test_deep_dive_renders_safe_mode_block_active_with_reason() -> None:
    screen = _CaptureDeepDive()
    screen.set_state(
        lines=["WARN | qiki.events.v1.audit | check"],
        incidents=[{"id": "INC-1", "severity": "C", "description": "critical alarm"}],
        selected_incident_id="INC-1",
        filter_summary="sev=C | страница 1/1 | всего 1",
        safe_mode={
            "active": True,
            "reason": "SAFE_MODE_ENTER_TEST",
            "authority": "q-core-agent(events)",
        },
    )
    text = _render_text(screen)
    assert "[F3] Глубокий анализ" in text
    assert "> [C] INC-1 - critical alarm" in text
    assert "[@click=select_incident('INC-1')]выбрать[/]" in text
    assert "[@click=ack_incident('INC-1')]ACK[/]" in text
    assert "Безопасность (Q-Core authority):" in text
    assert "SAFE MODE: ВКЛЮЧЕН" in text
    assert "Причина: SAFE_MODE_ENTER_TEST" in text
    assert "Authority: q-core-agent(events)" in text


def test_deep_dive_renders_safe_mode_block_without_data() -> None:
    screen = _CaptureDeepDive()
    screen.set_state(
        lines=[],
        incidents=[],
        selected_incident_id=None,
        filter_summary="",
        safe_mode=None,
    )
    text = _render_text(screen)
    assert "Нет активных C/A инцидентов" in text
    assert "Безопасность (Q-Core authority):" in text
    assert "SAFE MODE: нет данных" in text
    assert "Причина: Нет данных" in text
    assert "Authority: q-core-agent(events)" in text
