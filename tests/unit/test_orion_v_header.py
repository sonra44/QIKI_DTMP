from __future__ import annotations

import time

from qiki.services.operator_console.orion_v.widgets.header import OrionVHeader
from qiki.services.operator_console.orion_v.operator_state import build_operator_shell_state
from qiki.services.operator_console.orion_v.ui_rich import ORION_UI_COLORS

# UI P3 (пост-ревью): стрип красит коды палитрой пульта, не ANSI-именами.
_OK = ORION_UI_COLORS["ok"]
_WARN = ORION_UI_COLORS["warn"]
_CRIT = ORION_UI_COLORS["crit"]
_ACTIVE = ORION_UI_COLORS["active"]


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
    # DISPLAY_CANON решение №1: строка стрипа = только коды; бренд ORION V — над
    # рамками (console brand), имя экрана — якорем в титуле зоны.
    assert "ORION V" not in text
    assert "F1 Кокпит" not in text
    assert str(header.border_title) == "[F1] КОНТУР МИССИИ"
    assert f"РЕПЛИКА [{_OK}]RUN[/{_OK}]" in text
    assert f"СВЯЗЬ [{_OK}]OK[/{_OK}]" in text
    assert f"АКТУАЛ [{_OK}]OK[/{_OK}]" in text
    assert f"СЕНС [{_WARN}]WARN[/{_WARN}]" in text  # no SensorFrameSnapshot → degraded → WARN
    assert f"УПР [{_ACTIVE}]CONFIRM[/{_ACTIVE}]" in text  # pending action → operator-confirm gate
    # absorbed/cut from primary: prose fields, events, raw freshness label
    assert "P: " not in text
    assert "M: " not in text
    assert "A: " not in text
    assert "СОБЫТ" not in text
    assert "СВЕЖ" not in text
    assert "операторский контур" not in text
    # detail lives in the tooltip (canon) with click parity
    tooltip = str(header.tooltip)
    assert "РЕПЛИКА: RUNNING 1.00x" in tooltip
    assert "СОБЫТ: 12" in tooltip
    assert "режим: AUTO" in tooltip
    assert "СЕНС: degraded" in tooltip
    assert "F7" in tooltip and "F3" in tooltip and "F6" in tooltip


def test_header_hides_ctrl_when_operator_holds_authority() -> None:
    header = _CaptureHeader()
    header.set_state(
        build_operator_shell_state(
            hardware_model=None,
            telemetry={"sim_state": {"fsm_state": "running", "speed": 1.0}},
            nats_state="connected",
            last_telemetry_received_wall=time.time(),
        )
    )
    # canon: УПР is shown ONLY when the permission contour is not with the operator
    assert "УПР" not in header.last_render


def test_header_link_ok_with_live_comms_link_state() -> None:
    # live-telemetry path: _link_status_label passes comms.link_state through
    # ("online"), which must map to OK — regression for СВЯЗЬ LOST under flow
    header = _CaptureHeader()
    header.set_state(
        build_operator_shell_state(
            hardware_model=None,
            telemetry={
                "sim_state": {"fsm_state": "RUNNING"},
                "comms": {"link": "online", "link_state": "online"},
            },
            nats_state="connected",
            last_telemetry_received_wall=time.time(),
        )
    )
    assert f"СВЯЗЬ [{_OK}]OK[/{_OK}]" in header.last_render


def test_header_world_wait_and_link_lost_without_sources() -> None:
    header = _CaptureHeader()
    header.set_state(build_operator_shell_state(hardware_model=None, telemetry={}))
    text = header.last_render
    assert f"РЕПЛИКА [{_WARN}]WAIT[/{_WARN}]" in text  # canon: never «Нет данных»
    assert f"СВЯЗЬ [{_CRIT}]LOST[/{_CRIT}]" in text  # nats_state lost → no-data is LOST (red)
    assert f"АКТУАЛ [{_WARN}]NODATA[/{_WARN}]" in text
