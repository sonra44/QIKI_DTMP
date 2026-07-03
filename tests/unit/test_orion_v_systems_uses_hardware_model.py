from __future__ import annotations

from qiki.services.operator_console.orion_v.hardware_view_model.types import (
    HardwareViewModel,
    SubsystemView,
    TelemetryField,
    ViewStatus,
)
from qiki.services.operator_console.orion_v.screens.systems import (
    SystemCardWidget,
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

    assert "Питание / Заряд [critical]" in text
    assert "Статус: питание ограничено" in text
    assert "Сводка: Заряд 10%, 19В" in text


def test_missing_truth_is_rendered_as_unknown() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.OK,
        subsystems={},
        generated_at=0.0,
    )

    text = render_system_cards(build_system_cards(model))

    assert "Питание / Заряд [unknown]" in text
    assert "Статус: правда неполна" in text
    assert "Сводка: Нет данных" in text


def test_system_cards_render_severity_badges_and_selected_marker() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.CRIT,
        subsystems={
            "power": SubsystemView(
                id="power",
                title="Энергия",
                status=ViewStatus.CRIT,
                fields=[_field("power.soc", "Уровень заряда", 10, "%", ViewStatus.CRIT)],
                summary="Заряд 10%",
            ),
            "comms": SubsystemView(
                id="comms",
                title="Связь",
                status=ViewStatus.WARN,
                fields=[_field("comms.link_state", "Link", "DEGRADED", "", ViewStatus.WARN)],
                summary="Связь деградирует",
            ),
        },
        generated_at=0.0,
    )

    text = render_system_cards(build_system_cards(model), selected_subsystem="comms")

    assert "Питание / Заряд [critical]" in text
    assert "Связь / Канал / Протокол [degraded]" in text
    assert "#ff5f56" in text
    assert "#f2b84b" in text
    assert "CRIT" in text
    assert "WARN" in text
    assert "ВЫБРАНО" in text


def test_system_card_widget_sets_css_status_and_selected_classes() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.CRIT,
        subsystems={
            "power": SubsystemView(
                id="power",
                title="Энергия",
                status=ViewStatus.CRIT,
                fields=[_field("power.soc", "Уровень заряда", 10, "%", ViewStatus.CRIT)],
                summary="Источник ЭСП: батарея [УСТАРЕЛО]",
            )
        },
        generated_at=0.0,
    )
    card = next(card for card in build_system_cards(model) if card.subsystem_id == "power")

    widget = SystemCardWidget(card, selected=True)
    widget._refresh()

    assert widget.has_class("system-card")
    assert widget.has_class("status-crit")
    assert widget.has_class("selected")
    rendered = str(widget.render())
    assert "[CRIT]" in rendered
    assert "Источник ЭСП: батарея [УСТАРЕЛО]" in rendered


def test_system_card_widget_sets_warn_css_class() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.WARN,
        subsystems={
            "comms": SubsystemView(
                id="comms",
                title="Связь",
                status=ViewStatus.WARN,
                fields=[_field("comms.link_state", "Link", "DEGRADED", "", ViewStatus.WARN)],
                summary="Источник связи: [УСТАРЕЛО]",
            )
        },
        generated_at=0.0,
    )
    card = next(card for card in build_system_cards(model) if card.subsystem_id == "comms")

    widget = SystemCardWidget(card)
    widget._refresh()

    assert widget.has_class("status-warn")
    rendered = str(widget.render())
    assert "[WARN]" in rendered
    assert "Источник связи: [УСТАРЕЛО]" in rendered


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

    assert "Питание / Заряд [stable]" in text
    assert "Статус: зарядка доступна" in text
    assert "Эффект: Питание от дока поддерживает станционный контур и снижает нагрузку на маршрут." in text


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
    assert "Навигация / Маршрут [critical]" in text
    assert "Статус: гейт review активен" in text
    assert "Эффект: Поток действий F1 ограничен, пока review наблюдения не подтверждён и не закрыт." in text
    assert "Дальше: Продолжение разрешено только после review confirm." in text


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

    assert "Сенсоры / Радар / Наблюдение [stable]" in text
    assert "Статус: цель наблюдения в захвате" in text
    assert "Сводка: Сенсоры: 3 в работе, 0 деградации, 0 отключены | треков 1 | цель ALLY-62FD23" in text


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

    assert "Санкция безопасности: SAFE MODE активен (SAFE_MODE_ENTER_SENSORS_STALE)" in text
    assert "Безопасность / Целостность / Угрозы [critical]" in text
    assert "Статус: SAFE MODE активен" in text
