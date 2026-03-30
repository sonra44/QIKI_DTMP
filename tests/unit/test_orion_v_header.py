from __future__ import annotations

import time

from qiki.services.operator_console.orion_v.widgets.header import OrionVHeader
from qiki.services.operator_console.orion_v.operator_state import build_operator_shell_state


class _CaptureHeader(OrionVHeader):
    def __init__(self) -> None:
        super().__init__()
        self.last_render: str = ""

    def update(self, renderable) -> None:  # noqa: ANN001
        self.last_render = str(renderable)


def test_header_renders_mission_strip_state() -> None:
    header = _CaptureHeader()
    header.set_state(
        build_operator_shell_state(
            hardware_model=None,
            telemetry={"sim_state": {"fsm_state": "running", "speed": 1.0}, "navigation": {"mode": "AUTO"}},
            nats_state="connected",
            current_level="f1",
            level_label="F1 Кокпит",
            events_count=12,
            last_telemetry_received_wall=time.time(),
            help_text="Bridge ready",
            qiki_pending_action={"title_ru": "Подтвердить действие"},
            last_command_status="awaiting_confirm",
            last_command_summary="Awaiting operator confirm",
        )
    )

    text = header.last_render
    assert "[b]ORION V[/b]" in text
    assert "L: [b]F1 Кокпит[/b]" in text
    assert "P: [b]RUNNING 1.00x[/b]" in text
    assert "M: [b]AUTO[/b]" in text
    assert "A: [b]operator-confirm[/b]" in text
    assert "СВЯЗЬ [green]" in text
    assert "СОБЫТ [b]12[/b]" in text
    assert "ДАННЫЕ [b]fresh[/b]" in text
