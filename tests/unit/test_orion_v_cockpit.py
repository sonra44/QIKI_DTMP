from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from qiki.services.operator_console.orion_v.screens.cockpit import OrionVCockpitScreen
from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatResponseV1,
    QikiConsequenceV1,
    QikiLegalityV1,
    QikiMode,
    QikiReplyV1,
    QikiTrustSignalV1,
)


class _CaptureCockpit(OrionVCockpitScreen):
    def __init__(self) -> None:
        super().__init__()
        self.last_render: str = ""

    def update(self, renderable) -> None:  # noqa: ANN001
        self.last_render = str(renderable)


def _render_text(screen: OrionVCockpitScreen) -> str:
    if isinstance(screen, _CaptureCockpit):
        return screen.last_render
    return ""


class _CockpitApp(App[None]):
    def compose(self) -> ComposeResult:
        yield OrionVCockpitScreen(id="cockpit")


def test_mfd_fallback_render_is_russian_and_useful() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={
            "power": {"soc_pct": 18.0, "bus_v": 27.8, "bus_a": 2.3},
            "temp_core_c": 86.0,
            "comms": {"link": "online", "latency_ms": 120.0},
        },
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "ТЕЛЕМЕТРИЯ" in text
    assert "ЛЕВЫЙ MFD" not in text
    assert "ЭНЕРГИЯ" in text
    assert "ТЕПЛО" in text
    assert "QIKI / ОПЕРАТОР" not in text
    assert "Следующий шаг" in text
    assert "qiki.telemetry" in text
    assert "N/A" not in text


def test_mfd_sensor_page_has_inventory_without_fake_spectrometer() -> None:
    screen = _CaptureCockpit()
    screen._right_page = "sensors"
    screen.set_state(
        telemetry={"thermal": {"nodes": [{"id": "core", "temp_c": 72.0}]}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "Спектрометр" in text
    assert "runtime source не подтверждён" in text
    assert "Нет данных" in text
    assert "сенсоры" not in text.lower() or "маг" not in text.lower()


def test_mfd_qiki_block_renders_legality_trust_and_consequence() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000001",
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Command blocked", ru="Команда заблокирована"),
                body=BilingualText(en="No auto-action.", ru="Автодействие не выполняется."),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="protocol",
                reason_code="MVP_NO_AUTO_ACTIONS",
                reason=BilingualText(en="Auto-actions are disabled.", ru="Автодействия отключены."),
                allowed_when=BilingualText(en="Use approval flow.", ru="Используйте подтверждение оператора."),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Execution policy", ru="Политика исполнения"),
                    state="healthy",
                    source="policy",
                    confidence=1.0,
                    reason_code="MVP_POLICY_ACTIVE",
                    reason=BilingualText(en="Policy active.", ru="Политика активна."),
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(en="Nothing was sent.", ru="Ничего не отправлено."),
                telemetry_confirmation=BilingualText(en="State unchanged.", ru="Состояние не изменилось."),
            ),
        ),
    )
    text = _render_text(screen)
    assert "Команда заблокирована" in text
    assert "Решение: blocked | домен=protocol | причина=MVP_NO_AUTO_ACTIONS" in text
    assert "Политика исполнения" in text
    assert "Последствие: not_sent | Ничего не отправлено." in text
    assert "Подтверждение: Состояние не изменилось." in text


@pytest.mark.asyncio
async def test_mfd_live_layout_has_two_screens_buttons_and_chat() -> None:
    pytest.importorskip("textual")
    app = _CockpitApp()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        cockpit = app.query_one("#cockpit", OrionVCockpitScreen)
        cockpit.set_state(
            telemetry={"power": {"soc_pct": 80.0}, "temp_core_c": 25.0},
            nats_connected=True,
            active_incidents=0,
            incidents=[],
        )
        await pilot.pause()
        assert app.query_one("#orionv-mfd-status", Static)
        assert app.query_one("#orionv-cockpit-body", Static)
        assert app.query_one("#orionv-mfd-right-screen", Static)
        assert app.query_one("#orionv-cockpit-intervention", Static)
        assert app.query_one("#orionv-mfd-left-radar", Button)
        assert app.query_one("#orionv-mfd-right-sensors", Button)
        assert app.query_one("#orionv-cockpit-qiki-confirm", Button).display is False
