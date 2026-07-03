from __future__ import annotations

from uuid import UUID
import time

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from qiki.services.operator_console.orion_v.screens.cockpit import OrionVCockpitScreen
from qiki.services.operator_console.orion_v.operator_state import build_operator_shell_state
from qiki.services.operator_console.orion_v.i18n_ru import tr
from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatResponseV1,
    QikiConsequenceV1,
    QikiLegalityV1,
    QikiMode,
    QikiProposalV1,
    QikiProposedActionV1,
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


def _live_body_text(app: App[None]) -> str:
    return app.query_one("#orionv-cockpit-body", Static).render().plain


def _live_intervention_text(app: App[None]) -> str:
    return app.query_one("#orionv-cockpit-intervention", Static).render().plain


class _CockpitApp(App[None]):
    def compose(self) -> ComposeResult:
        yield OrionVCockpitScreen(id="cockpit")


def test_cockpit_scene_layout_shows_six_constant_zones() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "Общий статус" in text
    assert "Контекст миссии" in text
    assert "Наведение" in text
    assert "Инциденты" in text
    assert "Маршрут и цель" in text
    assert "Краткие факты:" in text
    assert "QIKI / Решение" in text
    assert "Оператор / Действие" in text
    assert "Процесс / Контур" in text
    assert "Контекст решения:" in text


@pytest.mark.asyncio
async def test_cockpit_hides_qiki_confirm_controls_without_pending_action() -> None:
    pytest.importorskip("textual")

    app = _CockpitApp()
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        cockpit = app.query_one("#cockpit", OrionVCockpitScreen)
        cockpit.set_state(
            telemetry={},
            nats_connected=True,
            active_incidents=0,
            incidents=[],
        )
        await pilot.pause()

        assert app.query_one("#orionv-cockpit-qiki-confirm", Button).display is False
        assert app.query_one("#orionv-cockpit-qiki-cancel", Button).display is False


@pytest.mark.asyncio
async def test_cockpit_live_body_compacts_nominal_quick_facts_rows() -> None:
    pytest.importorskip("textual")

    app = _CockpitApp()
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        cockpit = app.query_one("#cockpit", OrionVCockpitScreen)
        cockpit.set_state(
            telemetry={
                "power": {"soc_pct": 80.0, "bus_v": 28.0, "bus_a": 2.14},
                "thermal": {"nodes": [{"id": "core", "temp_c": 25.0, "warned": False, "tripped": False}]},
                "temp_core_c": 25.0,
                "temp_external_c": -40.0,
            },
            nats_connected=True,
            active_incidents=0,
            incidents=[],
            safe_mode={"active": False, "reason": "SAFE_MODE_EXIT_CONFIRMED"},
        )
        await pilot.pause()

        text = _live_body_text(app)
        assert "SAFETY" in text
        assert "| NOMINAL" in text
        assert "SAFE MODE: OFF | SAFE_MODE_EXIT_CONFIRMED" in text
        assert "ENERGY" in text
        assert "80.0% | crit < 15% | 28.00 В | 2.14 А" in text
        assert "THERMAL" in text
        assert "Энергия:" not in text
        assert "Температура:" not in text


@pytest.mark.asyncio
async def test_cockpit_live_intervention_panel_is_compact_in_nominal_state() -> None:
    pytest.importorskip("textual")

    app = _CockpitApp()
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        cockpit = app.query_one("#cockpit", OrionVCockpitScreen)
        cockpit.set_state(
            telemetry={},
            nats_connected=True,
            active_incidents=0,
            incidents=[],
        )
        await pilot.pause()

        text = _live_intervention_text(app)
        assert "QIKI" in text
        assert "ГОТОВ" in text
        assert "q: <команда>" in text
        assert "ДЕЙСТВИЕ" in text
        assert "ВВОД" in text
        assert "PROCESS" in text
        assert "FOCUS" in text
        assert "LEGALITY" not in text


def test_cockpit_scene_profile_docked_detected() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"docking": {"state": "docked", "connected": True}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "Профиль сцены/Scene profile: docked (Docked / Station)" in text
    assert "card: label=Запросить отстыковку/Request undock | allowed" in text


def test_cockpit_scene_profile_route_transit_detected() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        observation_objective={
            "status": "prepared",
            "route_role": "official",
            "observation_style": "safe",
            "procedure_name": "safe_pause_resume",
            "target_designator": "AST44995",
            "summary_ru": "Маршрут готов к выполнению.",
        },
    )
    text = _render_text(screen)
    assert "Профиль сцены/Scene profile: route_transit (Route Transit)" in text
    assert "Destination: AST44995" in text
    assert "Route mode: safe | role=official | scene=route_transit" in text


def test_cockpit_scene_profile_orbital_hold_detected() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"orbit": {"state": "orbital_hold", "confidence": 0.91}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "Профиль сцены/Scene profile: orbital_hold (Orbital Hold / Maneuver)" in text
    assert "card: label=Коррекция орбиты/Orbit correction | allowed" in text


def test_cockpit_marks_global_critical_when_critical_incident_exists() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"power": {"soc_pct": 75.0, "bus_v": 28.0, "bus_a": 1.2}},
        nats_connected=True,
        active_incidents=1,
        incidents=[{"severity": "C", "id": "INC-1", "description": "Перегрев"}],
    )
    text = _render_text(screen)
    assert "СИСТЕМА:" in text
    assert "КРИТИЧНО" in text
    assert "Есть критические инциденты" in text
    assert "Последний критический/Last critical: INC-1: Перегрев" in text


def test_cockpit_marks_energy_warning_for_low_soc_and_shows_interpretation() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"power": {"soc_pct": 18.0, "bus_v": 27.8, "bus_a": 2.3}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "Энергия:" in text
    assert "ПРЕДУПРЕЖДЕНИЕ" in text
    assert "Заряд/SOC: 18.0% | crit < 15%" in text


def test_cockpit_uses_no_data_marker_instead_of_na() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=False,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "Нет данных" in text
    assert "N/A" not in text


def test_cockpit_thermal_trend_is_detected() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"temp_core_c": 70.0},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    screen.set_state(
        telemetry={"temp_core_c": 72.0},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "Тренд: растет" in text


def test_cockpit_thermal_block_renders_warn_trip_from_nodes() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={
            "thermal": {
                "nodes": [
                    {
                        "id": "core",
                        "temp_c": 86.0,
                        "warned": True,
                        "tripped": False,
                        "warn_c": 80.0,
                        "trip_c": 90.0,
                        "hys_c": 5.0,
                    },
                    {
                        "id": "pdu",
                        "temp_c": 96.0,
                        "warned": False,
                        "tripped": True,
                        "warn_c": 85.0,
                        "trip_c": 95.0,
                        "hys_c": 5.0,
                    },
                ]
            },
            "temp_core_c": 86.0,
            "temp_external_c": -60.0,
        },
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)

    assert "Core: 86.0 °C | limit 90°C | state=WARN" in text
    assert "WARN nodes: core" in text
    assert "TRIP nodes: pdu" in text
    assert "Core limits: warn 80.0 °C | trip 90.0 °C | hys 5.0 °C" in text


def test_cockpit_motion_block_renders_g1_velocity_and_orbit_fields() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={
            "speed_m_s": 42.5,
            "velocity_xyz_m_s": {"x": 10.0, "y": -2.5, "z": 0.3},
            "orbit": {
                "apoapsis_km": 1100.0,
                "periapsis_km": 980.0,
                "inclination_deg": 51.6,
                "period_min": 93.4,
                "confidence": 0.82,
                "state": "healthy",
                "reason": "stable_solution",
            },
        },
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "Навигация/Nav: speed 42.50 м/с | heading Нет данных" in text
    assert "Орбита/Orbit: healthy | conf=0.82 | Apo 1100.00 км | Peri 980.00 км" in text
    assert "Причина/Reason: stable_solution" in text
    assert "Вектор/Vector XYZ" not in text
    assert "Орбита/Orbit details" not in text


def test_cockpit_comms_block_renders_extended_link_metrics() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={
            "comms": {
                "link": "online",
                "latency_ms": 120.0,
                "packet_loss_pct": 1.5,
                "rssi_dbm": -64.5,
                "snr_db": 18.0,
                "tx_power_w": 6.0,
                "data_rate_kbps": 192.0,
                "antenna_status": "lock",
            }
        },
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert f"Канал/Link: {tr('online')}" in text
    assert "SNR: 18.0 dB" in text
    assert "TX Power: 6.0 Вт" in text
    assert "Data Rate: 192.0 kbps" in text
    assert "Antenna: lock" in text


def test_cockpit_comms_uses_link_state_fallback_when_link_is_missing() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"comms": {"link_state": "online"}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert f"Канал/Link: {tr('online')}" in text


def test_cockpit_safe_mode_section_is_critical_when_active() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "PAUSED", "paused": True, "speed": 0.25}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={
            "active": True,
            "reason": "SENSORS_STALE",
            "authority": "q-core-agent(events)",
            "updated_ts": 1_700_000_000.0,
        },
    )
    text = _render_text(screen)
    assert "Безопасность: [bold #d06b4d]КРИТИЧНО[/]" in text
    assert "SAFE MODE: ВКЛЮЧЕН" in text
    assert "Причина: SENSORS_STALE" in text
    assert "Authority: q-core-agent(events)" in text


def test_cockpit_safe_mode_section_is_ok_when_inactive() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "PAUSED", "paused": True, "speed": 0.25}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={"active": False, "reason": "SAFE_MODE_EXIT_CONFIRMED"},
    )
    text = _render_text(screen)
    assert "SAFE MODE: OFF" in text
    assert "Причина: SAFE_MODE_EXIT_CONFIRMED" in text


def test_cockpit_safe_mode_section_stays_ok_when_signal_is_absent_but_shell_is_nominal() -> None:
    screen = _CaptureCockpit()
    # nominal power + thermal so this test isolates its real intent (absent
    # safe-mode signal + nominal shell must not warn) instead of leaning on
    # missing power/thermal telemetry, which §19.6 now flags as non-green.
    telemetry = {
        "sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0},
        "comms": {"link": "online", "latency_ms": 90.0, "packet_loss_pct": 0.0},
        "power": {"soc_pct": 82.0, "bus_v": 27.9, "bus_a": 3.1},
        "thermal": {"core_c": 41.0, "radiator_c": 30.0},
        "speed_m_s": 1.2,
        "heading": 90.0,
        "attitude": {"pitch_deg": 0.0, "yaw_deg": 0.0, "roll_deg": 0.0},
    }
    shell_state = build_operator_shell_state(
        hardware_model=None,
        telemetry=telemetry,
        safe_mode={},
        incidents=[],
        radar_tracks={},
        nats_state="connected",
        current_level="f1",
        level_label="F1 Кокпит",
        last_telemetry_received_wall=time.time(),
    )
    screen.set_state(
        telemetry=telemetry,
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={"active": None, "reason": "", "authority": "q-core-agent(events)", "updated_ts": None},
        operator_shell_state=shell_state,
    )
    text = _render_text(screen)
    assert "SAFE MODE: OFF" in text
    assert "signal clear" in text
    assert "СИСТЕМА:" in text
    assert "НОРМА" in text
    assert "Есть предупреждения, требуется наблюдение." not in text


def test_cockpit_energy_thermal_not_green_without_source() -> None:
    # §19.6 / ADR-0014: ORION must not show a confident green/NOMINAL indicator
    # for a subsystem whose telemetry source is missing. With empty telemetry the
    # ENERGY and THERMAL quick-fact chips must flag WARN, not NOMINAL.
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "ENERGY       | WARN" in text
    assert "THERMAL      | WARN" in text
    assert "ENERGY       | NOMINAL" not in text
    assert "THERMAL      | NOMINAL" not in text


def test_cockpit_guidance_compact_marks_partial_without_source() -> None:
    # F-3: with no guidance telemetry/derived state, the compact guidance/docking
    # rows must read "partial" (the same honest marker the verbose block uses),
    # never confident defaults, and must not present the scene profile as a real
    # docking state.
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)
    assert "ОТКЛОН       | PARTIAL" in text
    assert "МАНЁВР       | PARTIAL" in text
    assert "СТЫКОВКА     | PARTIAL" in text
    # F-2b: guidance severity is motion_severity — with no motion source the
    # НАВЕДЕНИЕ chip must not stay green either.
    assert "НАВЕДЕНИЕ    | WARN" in text
    assert "НАВЕДЕНИЕ    | NOMINAL" not in text


def test_cockpit_energy_block_renders_shed_reasons() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={
            "power": {
                "soc_pct": 45.0,
                "bus_v": 27.9,
                "bus_a": 1.8,
                "load_shedding": True,
                "shed_reasons": ["low_soc", "pdu_overcurrent"],
            }
        },
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)

    assert "Аварийное отключение нагрузки: ВКЛ" in text
    assert "Причины сброса: low_soc, pdu_overcurrent" in text


def test_cockpit_energy_block_marks_missing_shed_reasons_as_degraded() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"power": {"soc_pct": 45.0, "load_shedding": True}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
    )
    text = _render_text(screen)

    assert "Причины сброса: degraded: нет данных" in text


def test_cockpit_renders_qiki_legality_trust_and_consequence_block() -> None:
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
                body=BilingualText(
                    en="QIKI can explain docking commands, but it must not execute them automatically.",
                    ru="QIKI может объяснять команды стыковки, но не имеет права исполнять их автоматически.",
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="protocol",
                reason_code="MVP_NO_AUTO_ACTIONS",
                reason=BilingualText(
                    en="Auto-actions are disabled in the current QIKI MVP policy.",
                    ru="Автодействия отключены в текущей политике MVP для QIKI.",
                ),
                allowed_when=BilingualText(
                    en="Use explicit operator-approved control flow in a future execution phase.",
                    ru="Используйте отдельный подтверждаемый оператором контур исполнения в следующей фазе.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Execution policy", ru="Политика исполнения"),
                    state="healthy",
                    source="policy",
                    confidence=1.0,
                    reason_code="MVP_POLICY_ACTIVE",
                    reason=BilingualText(
                        en="The block is deterministic and does not depend on telemetry freshness.",
                        ru="Блокировка детерминирована и не зависит от свежести телеметрии.",
                    ),
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="No control-bus command was emitted.",
                    ru="Команда не была отправлена на control bus.",
                ),
                telemetry_confirmation=BilingualText(
                    en="Execution state remains unchanged.",
                    ru="Состояние исполнения осталось без изменений.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        ),
    )
    text = _render_text(screen)

    assert "QIKI:" in text
    assert "• Допуск/Legality: blocked [protocol] MVP_NO_AUTO_ACTIONS" in text
    assert "• Доверие/Trust: healthy | Политика исполнения/Execution policy | conf=1.00 | src=policy" in text
    assert "• Эффект/Last: not_sent | Команда не была отправлена на control bus." in text
    assert "QIKI, действие, контур." in text


def test_qiki_recommendation_trust_row_reflects_signal_state() -> None:
    # Regression: the compact QIKI recommendation TRUST row must read the trust state
    # from the response data, not by parsing the [QIKI LOOP] rendered lines (that coupling
    # silently fell back to PARTIAL when the block was reformatted with a "• " bullet).
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000009",
            ok=True,
            mode=QikiMode.FACTORY,
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="STATION_TRACK_LOW_QUALITY",
                reason=BilingualText(en="low quality", ru="низкое качество"),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="degraded",
                    source="sensor",
                    confidence=0.32,
                    reason_code="STATION_TRACK_LOW_QUALITY",
                    reason=BilingualText(en="noisy", ru="зашумлён"),
                )
            ],
        ),
    )
    rows = screen._qiki_recommendation_rows(qiki_severity="warn", qiki_lines=[])
    trust_rows = [row for row in rows if row[0] == "TRUST"]
    assert trust_rows, "TRUST row must be present when a QIKI response exists"
    assert trust_rows[0][1] == "DEGRADED"  # real signal state, not the PARTIAL fallback
    # G1 §3 (no silent failure): consequence state stays visible on the main panel even when
    # this response has no consequence — EFFECT row is shown always-when-active, honest NONE.
    effect_rows = [row for row in rows if row[0] == "EFFECT"]
    assert effect_rows and effect_rows[0][1] == "NONE"


def test_cockpit_renders_qiki_data_trust_deferred_state() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000008",
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Approach deferred", ru="Сближение отложено"),
                body=BilingualText(
                    en="QIKI cannot trust the current station track enough to clear the approach.",
                    ru="QIKI не может достаточно доверять текущему треку станции, чтобы разрешить сближение.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="STATION_TRACK_LOW_QUALITY",
                reason=BilingualText(
                    en="Station track quality 0.32 is below the minimum 0.50.",
                    ru="Качество трека станции 0.32 ниже допустимого минимума 0.50.",
                ),
                allowed_when=BilingualText(
                    en="Retry when station tracking quality recovers above the configured threshold.",
                    ru="Повторите попытку, когда качество трекинга станции восстановится выше заданного порога.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="degraded",
                    source="sensor",
                    confidence=0.32,
                    reason_code="STATION_TRACK_LOW_QUALITY",
                    reason=BilingualText(
                        en="Station track quality 0.32 is below the minimum 0.50.",
                        ru="Качество трека станции 0.32 ниже допустимого минимума 0.50.",
                    ),
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Approach execution was not started because target confidence is too low.",
                    ru="Исполнение сближения не начато, потому что доверие к цели слишком низкое.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No new guidance or control-bus command was emitted.",
                    ru="Ни новая навигационная команда, ни команда на control bus не отправлялись.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        ),
    )
    text = _render_text(screen)

    assert "• Допуск/Legality: deferred [trust] STATION_TRACK_LOW_QUALITY" in text
    assert "• Доверие/Trust: degraded | Радарный трек станции/Station radar track | conf=0.32 | src=sensor" in text
    assert "• Эффект/Last: not_sent | Исполнение сближения не начато" in text


def test_cockpit_renders_qiki_resource_blocked_state() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000011",
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Channel blocked", ru="Канал заблокирован"),
                body=BilingualText(
                    en="QIKI cannot request station contact because the communications link is offline.",
                    ru="QIKI не может запросить связь со станцией, потому что канал связи находится offline.",
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="resource",
                reason_code="COMMS_LINK_OFFLINE",
                reason=BilingualText(
                    en="The communications link is offline, so a station hail cannot be routed.",
                    ru="Канал связи находится offline, поэтому вызов станции не может быть маршрутизирован.",
                ),
                allowed_when=BilingualText(
                    en="Restore an online comms link before requesting station contact.",
                    ru="Восстановите online-канал связи перед запросом контакта со станцией.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Comms link state", ru="Состояние канала связи"),
                    state="off",
                    source="derived",
                    confidence=1.0,
                    reason_code="COMMS_LINK_OFFLINE",
                    reason=BilingualText(
                        en="The communications link is offline, so a station hail cannot be routed.",
                        ru="Канал связи находится offline, поэтому вызов станции не может быть маршрутизирован.",
                    ),
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The station hail was not started.",
                    ru="Вызов станции не был начат.",
                ),
                telemetry_confirmation=BilingualText(
                    en="Comms telemetry still reports an offline link; nothing was sent.",
                    ru="Телеметрия связи всё ещё показывает offline-канал; ничего не отправлялось.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        ),
    )
    text = _render_text(screen)

    assert "• Допуск/Legality: blocked [resource] COMMS_LINK_OFFLINE" in text
    assert "• Доверие/Trust: off | Состояние канала связи/Comms link state | conf=1.00 | src=derived" in text
    assert "• Эффект/Last: not_sent | Вызов станции не был начат." in text


def test_cockpit_renders_qiki_hostile_resource_blocked_state() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000012",
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Combat entry blocked", ru="Вход в бой заблокирован"),
                body=BilingualText(
                    en="QIKI will not continue hostile entry because the combat-entry resource contour is not ready.",
                    ru="QIKI не продолжит hostile-вход, потому что ресурсный контур combat-entry не готов.",
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="resource",
                reason_code="COMBAT_ENTRY_RCS_RESOURCE_LOW",
                reason=BilingualText(
                    en="RCS combat-entry contour is not ready.",
                    ru="RCS-контур входа в бой не готов.",
                ),
                allowed_when=BilingualText(
                    en="Retry when the RCS contour is ready again.",
                    ru="Повторите попытку, когда контур RCS снова будет готов.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Hostile target track", ru="Трек враждебной цели"),
                    state="healthy",
                    source="sensor",
                    confidence=0.95,
                    reason_code="HOSTILE_TARGET_TRACKED",
                    reason=BilingualText(
                        en="Target remains tracked with sufficient confidence.",
                        ru="Цель остаётся отслеживаемой с достаточным уровнем доверия.",
                    ),
                ),
                QikiTrustSignalV1(
                    label=BilingualText(en="RCS resource contour", ru="RCS ресурсный контур"),
                    state="degraded",
                    source="sensor",
                    confidence=0.30,
                    reason_code="COMBAT_ENTRY_RCS_RESOURCE_LOW",
                    reason=BilingualText(
                        en="RCS combat-entry contour is not ready.",
                        ru="RCS-контур входа в бой не готов.",
                    ),
                ),
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Combat-entry continuation was not started because the resource contour is not ready.",
                    ru="Продолжение combat-entry не запускалось, потому что ресурсный контур не готов.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No hostile combat-entry procedure was prepared or emitted.",
                    ru="Hostile combat-entry процедура не подготавливалась и не отправлялась.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        ),
    )
    text = _render_text(screen)

    assert "• Допуск/Legality: blocked [resource] COMBAT_ENTRY_RCS_RESOURCE_LOW" in text
    assert "RCS ресурсный контур/RCS resource contour" in text
    assert "• Эффект/Last: not_sent | Продолжение combat-entry не запускалось" in text


def test_cockpit_renders_qiki_zone_blocked_state() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000013",
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Corridor blocked", ru="Коридор заблокирован"),
                body=BilingualText(
                    en=(
                        "QIKI will not clear docking-corridor entry "
                        "because the craft is still outside the allowed zone."
                    ),
                    ru=(
                        "QIKI не разрешит вход в коридор стыковки, "
                        "потому что аппарат всё ещё вне допустимой зоны."
                    ),
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="zone",
                reason_code="DOCKING_ZONE_TOO_FAR",
                reason=BilingualText(
                    en="Station range 6400 m exceeds the docking-corridor threshold 5000 m.",
                    ru="Дальность до станции 6400 м превышает порог коридора стыковки 5000 м.",
                ),
                allowed_when=BilingualText(
                    en="Reduce the station range below the docking-corridor threshold before retrying.",
                    ru="Сократите дальность до станции ниже порога коридора стыковки и повторите попытку.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="healthy",
                    source="sensor",
                    confidence=0.92,
                    reason_code="DOCKING_ZONE_TOO_FAR",
                    reason=BilingualText(
                        en="Station range 6400 m exceeds the docking-corridor threshold 5000 m.",
                        ru="Дальность до станции 6400 м превышает порог коридора стыковки 5000 м.",
                    ),
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Docking-corridor entry was not started.",
                    ru="Вход в коридор стыковки не был начат.",
                ),
                telemetry_confirmation=BilingualText(
                    en="Radar telemetry still shows the craft outside the docking corridor.",
                    ru="Радарная телеметрия всё ещё показывает аппарат вне коридора стыковки.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        ),
    )
    text = _render_text(screen)

    assert "• Допуск/Legality: blocked [zone] DOCKING_ZONE_TOO_FAR" in text
    assert "• Доверие/Trust: healthy | Радарный трек станции/Station radar track | conf=0.92 | src=sensor" in text
    assert "• Эффект/Last: not_sent | Вход в коридор стыковки не был начат." in text


def test_cockpit_renders_qiki_failed_trust_state() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000016",
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Attitude hold blocked", ru="Удержание ориентации заблокировано"),
                body=BilingualText(
                    en="QIKI blocks attitude hold because the IMU currently reports a failed state.",
                    ru="QIKI блокирует удержание ориентации, потому что IMU сейчас сообщает о сбое.",
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="trust",
                reason_code="IMU_FAILED",
                reason=BilingualText(
                    en="IMU reports a failed state, so QIKI will not trust attitude stabilization commands.",
                    ru=(
                        "IMU сообщает о сбойном состоянии, "
                        "поэтому QIKI не будет доверять командам стабилизации ориентации."
                    ),
                ),
                allowed_when=BilingualText(
                    en="Recover the IMU before requesting attitude stabilization again.",
                    ru="Восстановите IMU перед повторным запросом стабилизации ориентации.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="IMU telemetry", ru="Телеметрия IMU"),
                    state="failed",
                    source="sensor",
                    confidence=0.0,
                    reason_code="IMU_FAILED",
                    reason=BilingualText(en="IMU status=crit, reason=not ok.", ru="Статус IMU=crit, причина=not ok."),
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Attitude stabilization was not started.",
                    ru="Стабилизация ориентации не была начата.",
                ),
                telemetry_confirmation=BilingualText(
                    en="IMU telemetry still reports a failed state; no action was emitted.",
                    ru="Телеметрия IMU всё ещё сообщает о сбое; действие не запускалось.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        ),
    )
    text = _render_text(screen)

    assert "• Допуск/Legality: blocked [trust] IMU_FAILED" in text
    assert "• Доверие/Trust: failed | Телеметрия IMU/IMU telemetry | conf=0.00 | src=sensor" in text
    assert "• Эффект/Last: not_sent | Стабилизация ориентации не была начата." in text


def test_cockpit_renders_confirmable_qiki_action() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000010",
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Release ready", ru="Отстыковка готова"),
                body=BilingualText(
                    en="QIKI can prepare a real undock command, but ORION must confirm it explicitly.",
                    ru="QIKI может подготовить реальную команду отстыковки, но ORION должен подтвердить её отдельно.",
                ),
            ),
            legality=QikiLegalityV1(
                status="allowed",
                domain="physics",
                reason_code="DOCK_RELEASE_READY",
                reason=BilingualText(
                    en="Docking telemetry confirms an attached state on port A.",
                    ru="Телеметрия стыковки подтверждает пристыкованное состояние на порту A.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Docking telemetry", ru="Телеметрия стыковки"),
                    state="healthy",
                    source="sensor",
                    confidence=1.0,
                    reason_code="DOCK_RELEASE_READY",
                    reason=BilingualText(
                        en="Docking telemetry confirms an attached state on port A.",
                        ru="Телеметрия стыковки подтверждает пристыкованное состояние на порту A.",
                    ),
                )
            ],
            consequence=QikiConsequenceV1(
                status="pending",
                summary=BilingualText(
                    en="The undock command is prepared and waiting for explicit operator confirmation.",
                    ru="Команда отстыковки подготовлена и ждёт явного подтверждения оператора.",
                ),
            ),
            proposals=[
                QikiProposalV1(
                    proposal_id="qiki-release-dock",
                    title=BilingualText(en="Confirm undock", ru="Подтвердить отстыковку"),
                    justification=BilingualText(
                        en="Telemetry confirms a docked state and a valid release path.",
                        ru="Телеметрия подтверждает пристыкованное состояние и валидный путь отстыковки.",
                    ),
                    confidence=1.0,
                    priority=90,
                    suggested_questions=[],
                    proposed_actions=[
                        QikiProposedActionV1(
                            subject="qiki.commands.control",
                            name="sim.dock.release",
                            parameters={},
                            dry_run=False,
                        )
                    ],
                )
            ],
            warnings=[],
            error=None,
        ),
    )
    text = _render_text(screen)

    assert "• Эффект/Last: pending | Команда отстыковки подготовлена" in text
    assert "• Ожидает/Pending: confirm needed — Подтвердить отстыковку" in text
    assert "• Дальше/Next: подтвердить (кнопка / q confirm)" in text
    assert "Действие/Action: Подтвердить отстыковку/Confirm undock -> sim.dock.release" in text


def test_cockpit_renders_qiki_procedure_plan_preview_and_execution_state() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "PAUSED", "paused": True, "speed": 0.25}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000011",
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Safe observation ready", ru="Безопасное наблюдение готово"),
                body=BilingualText(
                    en="QIKI prepared a short observation procedure.",
                    ru="QIKI подготовила короткую процедуру наблюдения.",
                ),
            ),
            legality=QikiLegalityV1(
                status="allowed",
                domain="resource",
                reason_code="SAFE_OBSERVATION_PROCEDURE_READY",
                reason=BilingualText(
                    en="Existing simulation control path is ready.",
                    ru="Существующий контур управления симуляцией готов.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Simulation control state", ru="Состояние управления симуляцией"),
                    state="healthy",
                    source="derived",
                    confidence=1.0,
                    reason_code="SIM_CONTROL_READY",
                    reason=BilingualText(
                        en="Simulation control is ready.",
                        ru="Управление симуляцией готово.",
                    ),
                )
            ],
            consequence=QikiConsequenceV1(
                status="pending",
                summary=BilingualText(
                    en="Procedure prepared.",
                    ru="Процедура подготовлена.",
                ),
            ),
            proposals=[
                QikiProposalV1(
                    proposal_id="qiki-safe-observation",
                    title=BilingualText(en="Run safe observation", ru="Запустить безопасное наблюдение"),
                    justification=BilingualText(
                        en="ok",
                        ru="ок",
                    ),
                    confidence=1.0,
                    priority=85,
                    suggested_questions=[],
                    proposed_actions=[
                        QikiProposedActionV1(
                            kind="ORION_PROCEDURE",
                            subject="orionv.procedure",
                            name="safe_pause_resume",
                            parameters={},
                            dry_run=False,
                        )
                    ],
                )
            ],
            warnings=[],
            error=None,
        ),
        qiki_pending_action_title="Запустить безопасное наблюдение",
        qiki_plan_preview_lines=["1. sim.pause -> ack sim.pause", "2. sim.start -> ack sim.start"],
        qiki_procedure_status="Процедура safe_pause_resume: шаг 1/2 выполняется",
    )
    text = _render_text(screen)

    assert "Подготовлено/Prepared: Запустить безопасное наблюдение" in text
    assert "• Дальше/Next: подтвердить (кнопка / q confirm)" in text
    assert "План/Plan:" in text
    assert "1. sim.pause -> ack sim.pause" in text
    assert "2. sim.start -> ack sim.start" in text
    assert "Исполнение/Execution: Процедура safe_pause_resume: шаг 1/2 выполняется" in text
    assert (
        "Действие/Action: Запустить безопасное наблюдение/Run safe observation "
        "-> proc run safe_pause_resume"
    ) in text
    assert "Процедура:" in text
    assert "Время/Time: sim_state=PAUSED | paused=ДА | speed=0.25x" in text
    assert "Журнал/Journal: click Процедуры/Procedures -> F6 for procedure audit trail." in text


def test_cockpit_renders_procedure_plan_preview_with_parameters() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 0.25}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        qiki_response=None,
        qiki_pending_action_title="Запустить медленное наблюдение",
        qiki_plan_preview_lines=["1. sim.pause -> ack sim.pause", "2. sim.start speed=0.25 -> ack sim.start"],
        qiki_procedure_status="Процедура safe_pause_slow_resume: шаг 2/2 выполняется",
    )
    text = _render_text(screen)

    assert "Процедура:" in text
    assert "Подготовлено/Prepared: Запустить медленное наблюдение" in text
    assert "2. sim.start speed=0.25 -> ack sim.start" in text
    assert "Исполнение/Execution: Процедура safe_pause_slow_resume: шаг 2/2 выполняется" in text
    assert "Время/Time: sim_state=RUNNING | paused=НЕТ | speed=0.25x" in text


def test_cockpit_renders_observation_objective_seed() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "PAUSED", "paused": True, "speed": 1.0}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        observation_objective={
            "objective_id": "observation-123",
            "request_id": "req-123",
            "proposal_id": "prop-123",
            "status": "prepared",
            "observation_style": "safe",
            "procedure_name": "safe_pause_resume",
            "route_role": "official",
            "target_designator": "AST44995",
            "track_visible": True,
            "track_id": "trk-42",
            "track_label": "AST44995",
            "track_range_m": 3500.0,
            "track_quality": 0.97,
            "title_ru": "Безопасное наблюдение готово",
            "summary_ru": "Процедура безопасной стабилизации наблюдения подготовлена.",
        },
        qiki_response=None,
        objective_event_lines=[
            "objectives | prepared | Процедура безопасной стабилизации наблюдения подготовлена.",
        ],
        qiki_pending_action_title="Запустить безопасное наблюдение",
        qiki_plan_preview_lines=["1. sim.pause -> ack sim.pause", "2. sim.start -> ack sim.start"],
        qiki_procedure_status="Процедура safe_pause_resume: ожидание подтверждения",
    )
    text = _render_text(screen)

    assert "Цель наблюдения:" in text
    assert "Статус/Status: prepared | profile=безопасный" in text
    assert "Цель/Target: AST44995" in text
    assert "Процедура/Procedure: safe_pause_resume" in text
    assert "Маршрут/Route: безопасный (safe)" in text
    assert "Route contour: style=safe | procedure=safe_pause_resume" in text
    assert "Route role: official" in text
    assert "Идентификатор/Objective ID: observation-123" in text
    assert "Proposal ID: prop-123" in text
    assert "Request ID: req-123" in text
    assert "Контракт/Contract: kind=observation_objective_seed" in text
    assert "Радар/Track: visible | AST44995 | range=3500 м | quality=0.97" in text
    assert "Track ID: trk-42" in text
    assert "Смысл/Meaning: Процедура безопасной стабилизации наблюдения подготовлена." in text
    assert "Связанные факты:" in text
    assert "objectives | prepared | Процедура безопасной стабилизации наблюдения подготовлена." in text


def test_cockpit_renders_observation_objective_confirmed_closure() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        observation_objective={
            "objective_id": "observation-123",
            "kind": "observation_objective_update",
            "status": "confirmed",
            "observation_style": "safe",
            "procedure_name": "safe_pause_resume",
            "route_role": "official",
            "target_designator": "ALLY-4D1ED5",
            "track_visible": True,
            "track_label": "ALLY-4D1ED5",
            "track_range_m": 3500.0,
            "track_quality": 0.97,
            "title_ru": "Наблюдение завершено",
            "summary_ru": "Observation-цель завершена, и её телеметрический эффект подтверждён.",
        },
        qiki_response=None,
    )
    text = _render_text(screen)

    assert "Статус/Status: confirmed | profile=безопасный" in text
    assert "Цель/Target: ALLY-4D1ED5" in text
    assert "Маршрут/Route: безопасный (safe)" in text
    assert "Route contour: style=safe | procedure=safe_pause_resume" in text
    assert "Route role: official" in text
    assert "Смысл/Meaning: Observation-цель завершена, и её телеметрический эффект подтверждён." in text
    assert "Следующий шаг/Next: objective closure подтверждён, можно переходить к следующей цели." in text


def test_cockpit_renders_hidden_event_follow_up_constraint() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 0.25}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        observation_objective={
            "objective_id": "observation-321",
            "kind": "observation_objective_update",
            "status": "confirmed",
            "observation_style": "slow",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "target_designator": "ALLY-4D1ED5",
            "track_visible": True,
            "track_label": "ALLY-4D1ED5",
            "track_range_m": 3500.0,
            "track_quality": 0.97,
            "title_ru": "Наблюдение завершено",
            "summary_ru": "Observation-цель завершена, и её телеметрический эффект подтверждён.",
            "follow_up_status": "review_required",
            "follow_up_reason_code": "HIDDEN_EVENT_REVIEW_REQUIRED",
            "follow_up_event_type": "HIDDEN_EVENT_REVEALED",
            "follow_up_summary_ru": (
                "Нужен follow-up по скрытому событию: проверьте связанный факт перед следующей observation-целью."
            ),
        },
        qiki_response=None,
    )
    text = _render_text(screen)

    assert "Route role: deviation" in text
    assert (
        "Ограничение/Constraint: status=review_required | "
        "source=HIDDEN_EVENT_REVEALED | reason=HIDDEN_EVENT_REVIEW_REQUIRED"
    ) in text
    assert (
        "Follow-up: Нужен follow-up по скрытому событию: "
        "проверьте связанный факт перед следующей observation-целью."
    ) in text
    assert (
        "Следующий шаг/Next: сначала проверьте linked hidden fact и подтвердите review командой review confirm, "
        "затем переходите к следующей observation-цели."
    ) in text


def test_cockpit_renders_hidden_event_review_closure() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 0.25}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        observation_objective={
            "objective_id": "observation-321",
            "kind": "observation_objective_update",
            "status": "confirmed",
            "observation_style": "slow",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "target_designator": "ALLY-4D1ED5",
            "track_visible": True,
            "track_label": "ALLY-4D1ED5",
            "track_range_m": 3500.0,
            "track_quality": 0.97,
            "title_ru": "Наблюдение завершено",
            "summary_ru": "Closure review скрытого события подтверждён на существующем observation path.",
            "follow_up_status": "review_completed",
            "follow_up_reason_code": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
            "follow_up_event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
            "follow_up_summary_ru": (
                "Review скрытого события закрыт: связанный факт подтверждён, "
                "и теперь открыт один post-review follow-up choice."
            ),
        },
        qiki_response=None,
    )
    text = _render_text(screen)

    assert (
        "Ограничение/Constraint: status=review_completed | "
        "source=HIDDEN_EVENT_REVIEW_ACKNOWLEDGED | reason=HIDDEN_EVENT_REVIEW_ACKNOWLEDGED"
    ) in text
    assert (
        "Follow-up: Review скрытого события закрыт: связанный факт подтверждён, "
        "и теперь открыт один post-review follow-up choice."
    ) in text
    assert (
        "Следующий шаг/Next: review closure подтверждён; выберите post-review follow-up командой follow-up hold."
    ) in text


def test_cockpit_renders_post_review_hold_for_recheck() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 0.25}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        observation_objective={
            "objective_id": "observation-321",
            "kind": "observation_objective_update",
            "status": "confirmed",
            "observation_style": "slow",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "target_designator": "ALLY-4D1ED5",
            "track_visible": True,
            "track_label": "ALLY-4D1ED5",
            "track_range_m": 3500.0,
            "track_quality": 0.97,
            "title_ru": "Наблюдение завершено",
            "summary_ru": "Post-review hold for recheck выбран на существующем observation path.",
            "follow_up_status": "hold_for_recheck",
            "follow_up_reason_code": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
            "follow_up_event_type": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
            "follow_up_summary_ru": (
                "Выбран post-review hold for recheck: удерживайте цель "
                "на осторожном recheck-контуре перед следующей observation-целью."
            ),
        },
        qiki_response=None,
    )
    text = _render_text(screen)

    assert (
        "Ограничение/Constraint: status=hold_for_recheck | "
        "source=HIDDEN_EVENT_RECHECK_HOLD_SELECTED | reason=HIDDEN_EVENT_RECHECK_HOLD_SELECTED"
    ) in text
    assert (
        "Follow-up: Выбран post-review hold for recheck: "
        "удерживайте цель на осторожном recheck-контуре перед следующей observation-целью."
    ) in text
    assert (
        "Следующий шаг/Next: post-review hold выбран; выполните осторожный safe recheck для той же цели "
        "перед следующей observation-целью."
    ) in text


def test_cockpit_renders_resume_observation_after_hold() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        observation_objective={
            "objective_id": "observation-321",
            "kind": "observation_objective_update",
            "status": "confirmed",
            "observation_style": "slow",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "target_designator": "ALLY-4D1ED5",
            "track_visible": True,
            "track_label": "ALLY-4D1ED5",
            "track_range_m": 3500.0,
            "track_quality": 0.97,
            "title_ru": "Наблюдение возобновлено",
            "summary_ru": "Resume observation выбран на существующем observation path.",
            "follow_up_status": "resume_observation",
            "follow_up_reason_code": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
            "follow_up_event_type": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
            "follow_up_summary_ru": (
                "Выбран resume observation: hold_for_recheck закрыт, и contour возвращён к одному cautious safe "
                "observation."
            ),
        },
        qiki_response=None,
    )
    text = _render_text(screen)

    assert (
        "Ограничение/Constraint: status=resume_observation | "
        "source=HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED | reason=HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED"
    ) in text
    assert (
        "Follow-up: Выбран resume observation: hold_for_recheck закрыт, и contour возвращён к одному cautious "
        "safe observation."
    ) in text
    assert (
        "Следующий шаг/Next: resume observation подтверждён; задайте один cautious safe observation для той же "
        "цели, чтобы продолжить contour."
    ) in text


def test_cockpit_renders_reconfirmed_continuation_result() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        observation_objective={
            "objective_id": "observation-321",
            "kind": "observation_objective_update",
            "status": "confirmed",
            "observation_style": "slow",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "target_designator": "ALLY-4D1ED5",
            "track_visible": True,
            "track_label": "ALLY-4D1ED5",
            "track_range_m": 3500.0,
            "track_quality": 0.97,
            "title_ru": "Observation reconfirmed",
            "summary_ru": "Continuation-result зафиксирован на том же observation contour.",
            "reason_code": "OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED",
            "observation_result_status": "reconfirmed",
            "observation_result_reason_code": "OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED",
            "observation_result_summary_ru": (
                "Observation continuation outcome подтверждён: цель ALLY-4D1ED5 безопасно reconfirmed после "
                "resume_observation на том же objective contour."
            ),
        },
        qiki_response=None,
    )
    text = _render_text(screen)

    assert (
        "Результат/Outcome: status=reconfirmed | reason=OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED"
    ) in text
    assert "Outcome: Observation continuation outcome подтверждён" in text
    assert (
        "Следующий шаг/Next: continuation-result зафиксирован; та же цель reconfirmed, можно переходить к "
        "следующей observation-цели."
    ) in text


def test_cockpit_renders_signature_changed_continuation_result() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        observation_objective={
            "objective_id": "observation-654",
            "kind": "observation_objective_update",
            "status": "confirmed",
            "observation_style": "slow",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "target_designator": "ALLY-4D1ED5",
            "track_visible": True,
            "track_id": "track-42",
            "track_label": "SPOOF-42",
            "track_range_m": 3100.0,
            "track_quality": 0.93,
            "title_ru": "Observation signature changed",
            "summary_ru": "Continuation-result зафиксирован: та же цель сохранилась, но signature обновилась.",
            "reason_code": "OBJECTIVE_RESUMED_OBSERVATION_SIGNATURE_CHANGED",
            "observation_result_status": "signature_changed",
            "observation_result_reason_code": "OBJECTIVE_RESUMED_OBSERVATION_SIGNATURE_CHANGED",
            "observation_result_summary_ru": (
                "Observation continuation outcome подтверждён: ALLY-4D1ED5 остаётся тем же track contact, но его "
                "live signature сменилась с ALLY-4D1ED5 на SPOOF-42 после resume_observation."
            ),
        },
        qiki_response=None,
    )
    text = _render_text(screen)

    assert (
        "Результат/Outcome: status=signature_changed | reason=OBJECTIVE_RESUMED_OBSERVATION_SIGNATURE_CHANGED"
    ) in text
    assert "Outcome: Observation continuation outcome подтверждён" in text
    assert (
        "Следующий шаг/Next: continuation-result зафиксирован; тот же contact сохранился, но его signature "
        "изменилась, поэтому дальше используйте обновлённую identity."
    ) in text


def test_cockpit_renders_linked_facts_placeholder_when_no_timeline() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        observation_objective={
            "objective_id": "observation-123",
            "status": "prepared",
            "observation_style": "slow",
            "procedure_name": "safe_pause_slow_resume",
            "target_designator": "ALLY-4D1ED5",
        },
        qiki_response=None,
    )
    text = _render_text(screen)

    assert "Связанные факты:" in text
    assert "FACTS        | IDLE       | linked events idle" in text


def test_cockpit_renders_combat_entry_procedure_preview() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        safe_mode={},
        qiki_response=QikiChatResponseV1(
            request_id=UUID(int=54),
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Combat entry ready", ru="Вход в бой подготовлен"),
                body=BilingualText(en="ok", ru="ок"),
            ),
            legality=QikiLegalityV1(
                status="allowed",
                domain="protocol",
                reason_code="COMBAT_ENTRY_PROCEDURE_READY",
                reason=BilingualText(en="ok", ru="ок"),
                allowed_when=BilingualText(
                    en="Confirm the prepared ORION procedure to execute one limited RCS intercept burst.",
                    ru="Подтвердите подготовленную процедуру ORION, чтобы выполнить один ограниченный RCS-манёвр.",
                ),
            ),
            trust_signals=[],
            consequence=QikiConsequenceV1(
                status="pending",
                summary=BilingualText(en="Procedure prepared", ru="Процедура подготовлена"),
            ),
            proposals=[
                QikiProposalV1(
                    proposal_id="qiki-combat-entry-preview",
                    title=BilingualText(en="Run combat-entry burst", ru="Запустить манёвр входа в бой"),
                    justification=BilingualText(en="ok", ru="ок"),
                    confidence=0.91,
                    priority=92,
                    suggested_questions=[],
                    proposed_actions=[
                        QikiProposedActionV1(
                            kind="ORION_PROCEDURE",
                            subject="orionv.procedure",
                            name="hostile_rcs_intercept_burst",
                            parameters={},
                            dry_run=False,
                        )
                    ],
                )
            ],
            warnings=[],
            error=None,
        ),
        qiki_pending_action_title="Запустить манёвр входа в бой",
        qiki_plan_preview_lines=["1. sim.rcs.fire axis=forward pct=35.0 duration_s=2.0 -> ack sim.rcs.fire"],
        qiki_procedure_status="Процедура hostile_rcs_intercept_burst: шаг 1/1 выполняется",
    )
    text = _render_text(screen)

    assert "Подготовлено/Prepared: Запустить манёвр входа в бой" in text
    assert "1. sim.rcs.fire axis=forward pct=35.0 duration_s=2.0 -> ack sim.rcs.fire" in text
    assert "Исполнение/Execution: Процедура hostile_rcs_intercept_burst: шаг 1/1 выполняется" in text
    assert (
        "Действие/Action: Запустить манёвр входа в бой/Run combat-entry burst "
        "-> proc run hostile_rcs_intercept_burst"
    ) in text


def test_cockpit_renders_tactical_shift_after_active_intercept() -> None:
    screen = _CaptureCockpit()
    screen.set_state(
        telemetry={},
        nats_connected=True,
        active_incidents=0,
        incidents=[],
        qiki_response=QikiChatResponseV1(
            request_id="00000000-0000-0000-0000-000000000014",
            ok=True,
            mode=QikiMode.FACTORY,
            reply=QikiReplyV1(
                title=BilingualText(en="Intercept already active", ru="Перехват уже активен"),
                body=BilingualText(
                    en="The next step is to hold track and reassess after the current burst completes.",
                    ru="Следующий шаг — удерживать трек и переоценить ситуацию после завершения текущего импульса.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="protocol",
                reason_code="TACTICAL_STATE_INTERCEPT_ACTIVE",
                reason=BilingualText(
                    en="Combat-entry pulse is already active.",
                    ru="Combat-entry импульс уже активен.",
                ),
                allowed_when=BilingualText(
                    en="Wait for the active intercept pulse to finish, then retry.",
                    ru="Дождитесь завершения активного перехватного импульса, затем повторите запрос.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Tactical state", ru="Тактическое состояние"),
                    state="healthy",
                    source="sensor",
                    confidence=1.0,
                    reason_code="TACTICAL_STATE_INTERCEPT_ACTIVE",
                    reason=BilingualText(
                        en="Combat-entry pulse is already active.",
                        ru="Combat-entry импульс уже активен.",
                    ),
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="No new combat-entry pulse was emitted because the current intercept pulse is still active.",
                    ru="Новый combat-entry импульс не отправлялся, потому что текущий перехватный импульс ещё активен.",
                ),
                telemetry_confirmation=BilingualText(
                    en="propulsion.rcs still reports an active intercept pulse.",
                    ru="propulsion.rcs всё ещё показывает активный перехватный импульс.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        ),
    )
    text = _render_text(screen)

    assert "• Допуск/Legality: deferred [protocol] TACTICAL_STATE_INTERCEPT_ACTIVE" in text
    assert "Тактическое состояние/Tactical state" in text
    assert "• Дальше/Next: Дождитесь завершения активного перехватного импульса" in text
