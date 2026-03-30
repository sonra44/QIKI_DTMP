from __future__ import annotations

from qiki.services.operator_console.orion_v.hardware_view_model.types import (
    HardwareViewModel,
    SubsystemView,
    TelemetryField,
    ViewStatus,
)
from qiki.services.operator_console.orion_v.screens.systems import (
    build_system_cards,
    render_system_cards,
    render_system_cards_with_safety,
)


def _field(key: str, label: str, value: object, unit: str, status: ViewStatus) -> TelemetryField:
    return TelemetryField(
        key=key,
        label=label,
        value=value,
        unit=unit,
        status=status,
        hint="",
        ts=None,
    )


def test_systems_screen_reads_power_status_from_hardware_model() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.CRIT,
        subsystems={
            "power": SubsystemView(
                id="power",
                title="Энергия",
                status=ViewStatus.CRIT,
                fields=[
                    _field("power.soc", "Уровень заряда", 10, "%", ViewStatus.CRIT),
                    _field("power.bus_v", "Напряжение шины", 19, "В", ViewStatus.CRIT),
                ],
                summary="Заряд 10%, 19В",
            )
        },
        generated_at=0.0,
    )

    text = render_system_cards(build_system_cards(model))

    assert "Power / Charge [critical]" in text
    assert "Status: power constrained" in text
    assert "Summary: Заряд 10%, 19В" in text


def test_missing_truth_is_rendered_as_unknown() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.OK,
        subsystems={},
        generated_at=0.0,
    )

    text = render_system_cards(build_system_cards(model))

    assert "Power / Charge [unknown]" in text
    assert "Status: truth incomplete" in text
    assert "Summary: Нет данных" in text


def test_docked_power_card_changes_meaning_with_charging_context() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.OK,
        subsystems={
            "power": SubsystemView(
                id="power",
                title="Энергия",
                status=ViewStatus.OK,
                fields=[
                    _field("power.soc", "Уровень заряда", 84, "%", ViewStatus.OK),
                    _field("power.runtime_min", "Осталось до разрядки", 95, "мин", ViewStatus.OK),
                    _field("power.dock_bridge_state", "Dock power bridge", "ACTIVE", "", ViewStatus.OK),
                ],
                summary="Заряд 84%, 27.9В, ~95 мин",
            )
        },
        generated_at=0.0,
    )

    text = render_system_cards(
        build_system_cards(
            model,
            telemetry={"docking": {"connected": True, "state": "docked"}},
        )
    )

    assert "Power / Charge [stable]" in text
    assert "Status: charging supported" in text
    assert "Effect: Dockside power supports the current station contour and reduces route pressure." in text


def test_route_transit_card_uses_objective_follow_up_as_action_gate() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.OK,
        subsystems={
            "navigation": SubsystemView(
                id="navigation",
                title="Навигация",
                status=ViewStatus.OK,
                fields=[
                    _field("navigation.speed_mps", "Скорость", 12.0, "м/с", ViewStatus.OK),
                    _field("navigation.heading_deg", "Курс", 42.0, "°", ViewStatus.OK),
                ],
                summary="Скорость 12.0 м/с, курс 42°",
            )
        },
        generated_at=0.0,
    )

    cards = build_system_cards(
        model,
        telemetry={"docking": {"connected": False}},
        observation_objective={
            "route_role": "official",
            "procedure_name": "safe_pause_slow_resume",
            "follow_up_status": "review_required",
            "follow_up_summary_ru": "Нужно закрыть review перед продолжением.",
            "follow_up_allowed_when_ru": "Продолжение разрешено только после review confirm.",
        },
    )
    text = render_system_cards(cards)

    assert cards[0].subsystem_id == "navigation"
    assert "Navigation / Route [critical]" in text
    assert "Status: review gate active" in text
    assert "Effect: F1 action flow is constrained until the observation review is acknowledged and closed." in text
    assert "Next: Продолжение разрешено только после review confirm." in text


def test_sensors_card_uses_live_target_track() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.OK,
        subsystems={
            "sensors": SubsystemView(
                id="sensors",
                title="Сенсоры",
                status=ViewStatus.OK,
                fields=[],
                summary="Сенсоры: 3 в работе, 0 деградации, 0 отключены",
            )
        },
        generated_at=0.0,
    )

    text = render_system_cards(
        build_system_cards(
            model,
            observation_objective={
                "target_designator": "ALLY-62FD23",
                "track_id": "trk-1",
            },
            radar_tracks={
                "trk-1": {
                    "track_id": "trk-1",
                    "track_label": "ALLY-62FD23",
                }
            },
        )
    )

    assert "Sensors / Radar / Observation [stable]" in text
    assert "Status: observation target live" in text
    assert "Summary: Сенсоры: 3 в работе, 0 деградации, 0 отключены | tracks 1 | target ALLY-62FD23" in text


def test_systems_screen_renders_safe_mode_authority_header_and_card() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.OK,
        subsystems={},
        generated_at=0.0,
    )

    text = render_system_cards_with_safety(
        build_system_cards(
            model,
            safe_mode={
                "active": True,
                "reason": "SAFE_MODE_ENTER_SENSORS_STALE",
                "authority": "q-core-agent(events)",
            },
        ),
        safe_mode={
            "active": True,
            "reason": "SAFE_MODE_ENTER_SENSORS_STALE",
            "authority": "q-core-agent(events)",
        },
    )

    assert "Safety authority: SAFE MODE active (SAFE_MODE_ENTER_SENSORS_STALE)" in text
    assert "Safety / Integrity / Hazard [critical]" in text
    assert "Status: safe mode active" in text
