from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from qiki.services.operator_console.orion_v.hardware_view_model.thresholds import (
    COMMS_AGE_CRIT_S,
    COMMS_AGE_WARN_S,
    POWER_SOC_CRIT_PCT,
    POWER_SOC_WARN_PCT,
    PROPULSION_FUEL_WARN_PCT,
    THERMAL_CORE_CRIT_C,
    THERMAL_CORE_WARN_C,
)
from qiki.services.operator_console.orion_v.hardware_view_model.types import (
    HardwareViewModel,
    SubsystemView,
    TelemetryField,
    ViewStatus,
)
from qiki.services.operator_console.orion_v.screens.systems import (
    F2_CARD_SOURCE_MAP,
    build_system_cards,
)
from qiki.services.operator_console.orion_v.sensor_trust_model import (
    SensorTrustOverride,
    SensorTrustSnapshot,
    assess_sensor_trust,
)
from qiki.shared.models.qiki_chat import BilingualText, QikiChatResponseV1

_SEVERITY_RANK = {"attention": 1, "warning": 2, "critical": 3}
_SEVERITY_LABEL = {"attention": "ATTENTION", "warning": "WARNING", "critical": "CRITICAL"}
_SYSTEM_ALERT_STATUS = {ViewStatus.WARN: "warning", ViewStatus.CRIT: "critical"}
_OBJECTIVE_ALERTS = {
    "review_required": {
        "severity": "critical",
        "title": "Review required",
        "effect": "Route continuation is constrained until the hidden observation fact is acknowledged and closed.",
        "source": "objective follow-up + operator objective event",
    },
    "hold_for_recheck": {
        "severity": "warning",
        "title": "Hold for recheck",
        "effect": "The contour remains gated until one cautious recheck is completed for the same target.",
        "source": "objective follow-up + post-review contour gate",
    },
}
_VIEW_STATUS_KEY = {
    ViewStatus.OK: "ok",
    ViewStatus.WARN: "warn",
    ViewStatus.CRIT: "crit",
    ViewStatus.NO_DATA: "nodata",
}
_VIEW_STATUS_SEVERITY = {
    ViewStatus.OK: "normal",
    ViewStatus.WARN: "warning",
    ViewStatus.CRIT: "critical",
    ViewStatus.NO_DATA: "unavailable",
}


@dataclass(frozen=True, slots=True)
class OperatorAlert:
    id: str
    severity: str
    title: str
    short_meaning: str
    source: str
    operator_effect: str
    next_action_hint: str | None = None
    incident_id: str | None = None
    order_index: int = 0


@dataclass(frozen=True, slots=True)
class AlertSummary:
    critical_count: int = 0
    warning_count: int = 0
    attention_count: int = 0
    focus_alert: OperatorAlert | None = None
    selected_critical_alert: OperatorAlert | None = None
    action_required: bool = False
    stale: bool = False
    unavailable: bool = False


@dataclass(frozen=True, slots=True)
class SubsystemChip:
    slug: str
    label: str
    status: str
    severity: str
    short_summary: str
    hint: str
    numeric_anchor: float | None = None
    # DISPLAY_CANON строка №4: готовый якорь для показа на чипе («100% ~262м»);
    # проза short_summary живёт в tooltip
    anchor_text: str = ""
    stale: bool = False
    degraded: bool = False
    action: str = "select_subsystem"
    target: str = ""


@dataclass(frozen=True, slots=True)
class AlwaysOnOperatorState:
    mission_phase: str | None = None
    world_run_state: str | None = None
    vehicle_mode: str | None = None
    control_authority: str | None = None
    autopilot_status: str | None = None
    autopilot_mode: str | None = None
    link_status: str | None = None
    telemetry_age_ms: float | None = None
    signal_latency_ms: float | None = None
    packet_loss_percent: float | None = None
    last_contact_timestamp: str | None = None
    alert_summary: AlertSummary = AlertSummary()
    safe_envelope_state: str | None = None
    emergency_mode: str | None = None
    safe_mode_trigger: str | None = None
    collision_imminent: bool | None = None
    battery_charge_percent: float | None = None
    power_balance_mw: float | None = None
    power_distribution_status: str | None = None
    core_temperature_c: float | None = None
    battery_temp_c: float | None = None
    thermal_load_percent: float | None = None
    fuel_remaining_percent: float | None = None
    delta_v_remaining_ms: float | None = None
    engine_status: str | None = None
    propulsion_mode: str | None = None
    hull_integrity_percent: float | None = None
    hull_breach_detected: bool | None = None
    q_core_status: str | None = None
    watchdog_status: str | None = None
    qiki_assist_status: str | None = None
    human_ack_required: bool = False
    last_command_status: str | None = None
    operator_action_required: bool = False
    pending_command_count: int = 0
    partial_fields: tuple[str, ...] = ()
    unavailable_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DerivedOperatorIndicators:
    power_margin_state: str | None = None
    time_to_power_deficit: float | None = None
    time_to_battery_critical: float | None = None
    thermal_margin_state: str | None = None
    hotspot_source: str | None = None
    time_to_overheat: float | None = None
    trajectory_deviation: str | None = None
    eta_to_target: str | None = None
    attitude_stability: str | None = None
    maneuver_feasibility: str | None = None
    fuel_margin_to_plan: str | None = None
    rcs_authority_available: bool | None = None
    commandability_state: str | None = None
    data_freshness_state: str | None = None
    sensor_trust_state: str | None = None
    sensor_trust_summary: str | None = None
    sensor_trust_effect: str | None = None
    sensor_trust_confidence: float | None = None
    collision_risk_score: float | None = None
    intervention_required: bool = False
    autonomy_confidence: str | None = None
    mission_risk_state: str | None = None
    partial_fields: tuple[str, ...] = ()
    unavailable_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OperatorLoopState:
    last_command_status: str = "idle"
    last_command_summary: str = "Команда ещё не подавалась"
    pending_command_count: int = 0
    operator_action_required: bool = False
    command_mode_state: str = "standby"
    hotkey_context: str = "'/' ':' — команда"
    status_text: str = "Команды: help"
    current_level: str = "f1"
    replay_mode: bool = False
    selected_incident_id: str | None = None
    selected_subsystem: str | None = None
    has_selected_incident: bool = False
    incident_controls_visible: bool = False
    page_controls_visible: bool = False
    # ADR-0020: кнопка Пауза/Старт процедуры установки (show-when: active)
    attach_procedure_active: bool = False
    attach_procedure_paused: bool = False
    # Игровая (активная) пауза: состояние времени реплики для кнопки ⏸/▶ Мир
    world_paused: bool = False
    # Срез 1 (F5-рука): ЧИСТЫЙ флаг «есть QIKI-кандидат на подтверждение»
    # (= qiki_pending_action ≠ None, БЕЗ примеси алертов) — show-when кнопки Выполнить.
    qiki_action_pending: bool = False


@dataclass(frozen=True, slots=True)
class OperatorShellState:
    level_label: str = "F1 Кокпит"
    events_count: int = 0
    always_on: AlwaysOnOperatorState = AlwaysOnOperatorState()
    derived: DerivedOperatorIndicators = DerivedOperatorIndicators()
    alerts: tuple[OperatorAlert, ...] = ()
    chips: tuple[SubsystemChip, ...] = ()
    operator_loop: OperatorLoopState = OperatorLoopState()
    console_lines: tuple[str, ...] = ()

    @classmethod
    def empty(cls) -> OperatorShellState:
        return cls()


def build_operator_shell_state(
    *,
    hardware_model: HardwareViewModel | None,
    attach_procedure_active: bool = False,
    attach_procedure_paused: bool = False,
    world_paused: bool = False,
    telemetry: dict[str, Any] | None = None,
    safe_mode: dict[str, Any] | None = None,
    observation_objective: dict[str, Any] | None = None,
    incidents: list[dict[str, Any]] | None = None,
    radar_tracks: dict[str, dict[str, Any]] | None = None,
    qiki_response: QikiChatResponseV1 | None = None,
    sensor_trust_override: SensorTrustOverride | str | None = None,
    qiki_pending_action_title: str | None = None,
    qiki_pending_action: dict[str, Any] | None = None,
    selected_incident_id: str | None = None,
    selected_subsystem: str | None = None,
    nats_state: str = "lost",
    replay_mode: bool = False,
    current_level: str = "f1",
    level_label: str = "F1 Кокпит",
    events_count: int = 0,
    last_telemetry_received_wall: float | None = None,
    help_text: str = "Команды: help",
    command_mode_open: bool = False,
    qiki_pending_count: int = 0,
    procedure_running: bool = False,
    ack_pending: bool = False,
    last_command_status: str | None = None,
    last_command_summary: str | None = None,
    console_lines: tuple[str, ...] = (),
) -> OperatorShellState:
    telemetry = telemetry or {}
    safe_mode = safe_mode or {}
    objective = dict(observation_objective or {})
    incidents = list(incidents or [])
    radar_tracks = dict(radar_tracks or {})

    alerts = tuple(
        build_level0_alerts(
            hardware_model=hardware_model,
            telemetry=telemetry,
            safe_mode=safe_mode,
            observation_objective=objective,
            active_incidents=len(incidents),
            incidents=incidents,
            radar_tracks=radar_tracks,
            qiki_response=qiki_response,
        )
    )
    alert_summary = _build_alert_summary(
        alerts=alerts,
        selected_incident_id=selected_incident_id,
        telemetry_age_ms=_telemetry_age_ms(last_telemetry_received_wall),
        safe_mode=safe_mode,
        human_ack_required=qiki_pending_action is not None,
    )
    operator_loop = _build_operator_loop_state(
        attach_procedure_active=attach_procedure_active,
        attach_procedure_paused=attach_procedure_paused,
        world_paused=world_paused,
        current_level=current_level,
        replay_mode=replay_mode,
        selected_incident_id=selected_incident_id,
        selected_subsystem=selected_subsystem,
        command_mode_open=command_mode_open,
        status_text=help_text,
        pending_command_count=qiki_pending_count + int(procedure_running) + int(ack_pending),
        human_ack_required=qiki_pending_action is not None,
        has_selected_incident=selected_incident_id is not None,
        alert_summary=alert_summary,
        last_command_status=last_command_status,
        last_command_summary=last_command_summary,
    )
    always_on = _build_always_on_state(
        hardware_model=hardware_model,
        telemetry=telemetry,
        safe_mode=safe_mode,
        qiki_response=qiki_response,
        qiki_pending_action=qiki_pending_action,
        nats_state=nats_state,
        replay_mode=replay_mode,
        last_telemetry_received_wall=last_telemetry_received_wall,
        alert_summary=alert_summary,
        operator_loop=operator_loop,
    )
    # SENSORTRUST-0001: derived perception-trust surface (shared contract with
    # legacy-telemetry fallback; override is local UI posture, not runtime truth).
    sensor_trust_snapshot = assess_sensor_trust(
        hardware_model=hardware_model,
        telemetry=telemetry,
        radar_tracks=radar_tracks,
        observation_objective=objective,
        operator_override=sensor_trust_override,
    )
    derived = _build_derived_indicators(
        hardware_model=hardware_model,
        telemetry=telemetry,
        observation_objective=objective,
        replay_mode=replay_mode,
        always_on=always_on,
        alert_summary=alert_summary,
        operator_loop=operator_loop,
        qiki_response=qiki_response,
        sensor_trust_snapshot=sensor_trust_snapshot,
    )
    chips = _build_subsystem_chips(
        hardware_model=hardware_model,
        qiki_response=qiki_response,
        qiki_pending_action_title=qiki_pending_action_title,
        derived=derived,
        telemetry_age_ms=always_on.telemetry_age_ms,
    )
    return OperatorShellState(
        level_label=level_label,
        events_count=max(0, int(events_count)),
        always_on=always_on,
        derived=derived,
        alerts=alerts,
        chips=chips,
        operator_loop=operator_loop,
        console_lines=tuple(str(line).strip() for line in console_lines if str(line).strip()),
    )


def build_level0_alerts(
    *,
    hardware_model: HardwareViewModel | None,
    telemetry: dict[str, Any] | None = None,
    safe_mode: dict[str, Any] | None = None,
    observation_objective: dict[str, Any] | None = None,
    active_incidents: int = 0,
    incidents: list[dict[str, Any]] | None = None,
    radar_tracks: dict[str, dict[str, Any]] | None = None,
    qiki_response: QikiChatResponseV1 | None = None,
) -> list[OperatorAlert]:
    telemetry = telemetry or {}
    safe_mode = safe_mode or {}
    objective = dict(observation_objective or {})
    incidents = list(incidents or [])
    radar_tracks = dict(radar_tracks or {})

    alerts: list[OperatorAlert] = []
    alerts.extend(_build_objective_alerts(objective))
    alerts.extend(_build_observation_confidence_alerts(objective))
    alerts.extend(_build_qiki_alerts(qiki_response))
    alerts.extend(_build_incident_alerts(incidents))
    alerts.extend(
        _build_system_alerts(
            hardware_model=hardware_model,
            telemetry=telemetry,
            safe_mode=safe_mode,
            objective=objective,
            active_incidents=active_incidents,
            incidents=incidents,
            radar_tracks=radar_tracks,
        )
    )
    return sorted(alerts, key=lambda alert: (-_SEVERITY_RANK.get(alert.severity, 0), alert.order_index, alert.id))


def _build_alert_summary(
    *,
    alerts: tuple[OperatorAlert, ...],
    selected_incident_id: str | None,
    telemetry_age_ms: float | None,
    safe_mode: dict[str, Any],
    human_ack_required: bool,
) -> AlertSummary:
    counts = {"critical": 0, "warning": 0, "attention": 0}
    for alert in alerts:
        counts[alert.severity] = counts.get(alert.severity, 0) + 1
    focus_alert = _pick_focus_alert(alerts, selected_incident_id)
    selected_critical = next((alert for alert in alerts if alert.severity == "critical"), None)
    stale = telemetry_age_ms is not None and telemetry_age_ms >= COMMS_AGE_CRIT_S * 1000.0
    unavailable = telemetry_age_ms is None and not alerts
    action_required = (
        counts["critical"] > 0
        or human_ack_required
        or bool(safe_mode.get("active"))
    )
    return AlertSummary(
        critical_count=counts["critical"],
        warning_count=counts["warning"],
        attention_count=counts["attention"],
        focus_alert=focus_alert,
        selected_critical_alert=selected_critical,
        action_required=action_required,
        stale=stale,
        unavailable=unavailable,
    )


def _build_always_on_state(
    *,
    hardware_model: HardwareViewModel | None,
    telemetry: dict[str, Any],
    safe_mode: dict[str, Any],
    qiki_response: QikiChatResponseV1 | None,
    qiki_pending_action: dict[str, Any] | None,
    nats_state: str,
    replay_mode: bool,
    last_telemetry_received_wall: float | None,
    alert_summary: AlertSummary,
    operator_loop: OperatorLoopState,
) -> AlwaysOnOperatorState:
    partial: set[str] = set()
    unavailable: set[str] = set()

    mission_phase = _mission_phase_label(telemetry=telemetry, replay_mode=replay_mode)
    world_run_state = _world_run_state(telemetry=telemetry, replay_mode=replay_mode)
    if mission_phase is not None:
        partial.add("mission_phase")
    else:
        unavailable.add("mission_phase")

    vehicle_mode = _raw_text(
        telemetry,
        ("vehicle_mode",),
        ("vehicle", "mode"),
        ("navigation", "mode"),
    ) or _field_text(hardware_model, "navigation", "navigation.mode")
    if vehicle_mode is not None:
        partial.add("vehicle_mode")
    else:
        unavailable.add("vehicle_mode")

    control_authority = _control_authority_label(
        safe_mode=safe_mode,
        qiki_pending_action=qiki_pending_action,
        qiki_response=qiki_response,
        replay_mode=replay_mode,
    )
    partial.add("control_authority")

    telemetry_age_ms = _telemetry_age_ms(last_telemetry_received_wall)
    signal_latency_ms = _field_num(hardware_model, "comms", "comms.latency_ms")
    packet_loss_percent = _field_num(hardware_model, "comms", "comms.packet_loss_pct")
    last_contact_timestamp = _timestamp_text(last_telemetry_received_wall)
    link_status = _link_status_label(
        hardware_model=hardware_model,
        nats_state=nats_state,
        replay_mode=replay_mode,
        telemetry_age_ms=telemetry_age_ms,
    )
    partial.add("link_status")

    safe_mode_trigger = str(safe_mode.get("reason") or "").strip() or None
    if safe_mode_trigger is None:
        unavailable.add("safe_mode_trigger")

    collision_imminent = _raw_bool(
        telemetry,
        ("collision", "imminent"),
        ("safety", "collision_imminent"),
        ("navigation", "collision_imminent"),
    )
    if collision_imminent is None:
        unavailable.add("collision_imminent")

    battery_charge_percent = _field_num(hardware_model, "power", "power.soc")
    draw_w = _field_num(hardware_model, "power", "power.draw_w")
    available_w = _field_num(hardware_model, "power", "power.available_w")
    power_balance_mw = (
        round((available_w - draw_w) * 1000.0, 1)
        if available_w is not None and draw_w is not None
        else None
    )
    if power_balance_mw is not None:
        partial.add("power_balance_mw")
    else:
        unavailable.add("power_balance_mw")
    power_distribution_status = _field_text(hardware_model, "power", "pdu.state")
    if power_distribution_status is None:
        unavailable.add("power_distribution_status")

    core_temperature_c = _field_num(hardware_model, "thermal", "thermal.core_c")
    battery_temp_c = _raw_num(
        telemetry,
        ("battery", "temp_c"),
        ("power", "battery_temp_c"),
    )
    if battery_temp_c is None:
        unavailable.add("battery_temp_c")
    thermal_load_percent = (
        round(max(0.0, min(core_temperature_c / THERMAL_CORE_CRIT_C, 1.0)) * 100.0, 1)
        if core_temperature_c is not None
        else None
    )
    if thermal_load_percent is not None:
        partial.add("thermal_load_percent")
    else:
        unavailable.add("thermal_load_percent")

    fuel_remaining_percent = _field_num(hardware_model, "propulsion", "propulsion.fuel_pct")
    delta_v_remaining_ms = _raw_num(
        telemetry,
        ("propulsion", "delta_v_remaining_ms"),
        ("navigation", "delta_v_remaining_ms"),
    )
    if delta_v_remaining_ms is None:
        unavailable.add("delta_v_remaining_ms")
    engine_status = _subsystem_status_label(hardware_model, "propulsion")
    if engine_status is not None:
        partial.add("engine_status")
    else:
        unavailable.add("engine_status")
    propulsion_mode = _raw_text(
        telemetry,
        ("propulsion", "mode"),
        ("engine", "mode"),
    )
    if propulsion_mode is None:
        unavailable.add("propulsion_mode")

    hull_integrity_percent = _field_num(hardware_model, "hull", "hull.integrity_pct")
    hull_breach_detected = _raw_bool(
        telemetry,
        ("hull", "breach_detected"),
        ("hull", "breach"),
    )
    if hull_breach_detected is None:
        unavailable.add("hull_breach_detected")

    q_core_status = _raw_text(
        telemetry,
        ("q_core", "status"),
        ("qcore", "status"),
    )
    if q_core_status is None:
        unavailable.add("q_core_status")
    watchdog_status = _raw_text(
        telemetry,
        ("compute", "watchdog_status"),
        ("watchdog", "status"),
    )
    if watchdog_status is None:
        unavailable.add("watchdog_status")
    qiki_assist_status = _qiki_assist_status(qiki_response=qiki_response, qiki_pending_action=qiki_pending_action)
    if qiki_assist_status is not None:
        partial.add("qiki_assist_status")
    else:
        unavailable.add("qiki_assist_status")

    autopilot_status = _raw_text(
        telemetry,
        ("autopilot", "status"),
        ("guidance", "autopilot_status"),
    )
    autopilot_mode = _raw_text(
        telemetry,
        ("autopilot", "mode"),
        ("guidance", "autopilot_mode"),
    )
    if autopilot_status is None:
        unavailable.add("autopilot_status")
    if autopilot_mode is None:
        unavailable.add("autopilot_mode")

    safe_envelope_state = _safe_envelope_state(alert_summary=alert_summary, safe_mode=safe_mode)
    emergency_mode = "safe_mode" if bool(safe_mode.get("active")) else None

    return AlwaysOnOperatorState(
        mission_phase=mission_phase,
        world_run_state=world_run_state,
        vehicle_mode=vehicle_mode,
        control_authority=control_authority,
        autopilot_status=autopilot_status,
        autopilot_mode=autopilot_mode,
        link_status=link_status,
        telemetry_age_ms=telemetry_age_ms,
        signal_latency_ms=signal_latency_ms,
        packet_loss_percent=packet_loss_percent,
        last_contact_timestamp=last_contact_timestamp,
        alert_summary=alert_summary,
        safe_envelope_state=safe_envelope_state,
        emergency_mode=emergency_mode,
        safe_mode_trigger=safe_mode_trigger,
        collision_imminent=collision_imminent,
        battery_charge_percent=battery_charge_percent,
        power_balance_mw=power_balance_mw,
        power_distribution_status=power_distribution_status,
        core_temperature_c=core_temperature_c,
        battery_temp_c=battery_temp_c,
        thermal_load_percent=thermal_load_percent,
        fuel_remaining_percent=fuel_remaining_percent,
        delta_v_remaining_ms=delta_v_remaining_ms,
        engine_status=engine_status,
        propulsion_mode=propulsion_mode,
        hull_integrity_percent=hull_integrity_percent,
        hull_breach_detected=hull_breach_detected,
        q_core_status=q_core_status,
        watchdog_status=watchdog_status,
        qiki_assist_status=qiki_assist_status,
        human_ack_required=qiki_pending_action is not None,
        last_command_status=operator_loop.last_command_status,
        operator_action_required=operator_loop.operator_action_required,
        pending_command_count=operator_loop.pending_command_count,
        partial_fields=tuple(sorted(partial)),
        unavailable_fields=tuple(sorted(unavailable)),
    )


def _build_derived_indicators(
    *,
    hardware_model: HardwareViewModel | None,
    telemetry: dict[str, Any],
    observation_objective: dict[str, Any],
    replay_mode: bool,
    always_on: AlwaysOnOperatorState,
    alert_summary: AlertSummary,
    operator_loop: OperatorLoopState,
    qiki_response: QikiChatResponseV1 | None,
    sensor_trust_snapshot: SensorTrustSnapshot,
) -> DerivedOperatorIndicators:
    partial: set[str] = set()
    unavailable: set[str] = set()

    runtime_min = _field_num(hardware_model, "power", "power.runtime_min")
    battery_charge = always_on.battery_charge_percent
    power_margin_state = _power_margin_state(
        power_balance_mw=always_on.power_balance_mw,
        battery_charge_percent=battery_charge,
    )
    time_to_power_deficit = 0.0 if always_on.power_balance_mw is not None and always_on.power_balance_mw < 0 else None
    time_to_battery_critical = None
    if runtime_min is not None and battery_charge is not None and battery_charge > 0:
        scale = max(0.0, (battery_charge - POWER_SOC_CRIT_PCT) / battery_charge)
        time_to_battery_critical = round(runtime_min * scale * 60.0, 1)
        partial.add("time_to_battery_critical")
    else:
        unavailable.add("time_to_battery_critical")

    hotspot_source = (
        _field_text(hardware_model, "thermal", "thermal.trip_nodes")
        or _field_text(hardware_model, "thermal", "thermal.warn_nodes")
    )
    thermal_margin_state = _thermal_margin_state(always_on.core_temperature_c, hotspot_source)
    if hotspot_source is not None:
        partial.add("hotspot_source")
    else:
        unavailable.add("hotspot_source")
    unavailable.add("time_to_overheat")

    route_role = str(observation_objective.get("route_role") or "").strip().lower() or None
    if route_role is not None:
        trajectory_deviation = "deviation-active" if route_role == "deviation" else "nominal"
        partial.add("trajectory_deviation")
    else:
        trajectory_deviation = None
        unavailable.add("trajectory_deviation")

    eta_to_target = _field_text(hardware_model, "docking", "docking.eta_contact")
    if eta_to_target is not None:
        partial.add("eta_to_target")
    else:
        unavailable.add("eta_to_target")

    attitude_stability = _attitude_stability(hardware_model)
    if attitude_stability is not None:
        partial.add("attitude_stability")
    else:
        unavailable.add("attitude_stability")

    maneuver_feasibility = _maneuver_feasibility(hardware_model, always_on.fuel_remaining_percent)
    if maneuver_feasibility is not None:
        partial.add("maneuver_feasibility")
    else:
        unavailable.add("maneuver_feasibility")

    unavailable.add("fuel_margin_to_plan")
    rcs_authority_available = _rcs_authority_available(hardware_model)
    if rcs_authority_available is not None:
        partial.add("rcs_authority_available")
    else:
        unavailable.add("rcs_authority_available")

    commandability_state = _commandability_state(
        replay_mode=replay_mode,
        link_status=always_on.link_status,
        telemetry_age_ms=always_on.telemetry_age_ms,
    )
    data_freshness_state = _data_freshness_state(always_on.telemetry_age_ms)

    collision_risk_score = 1.0 if always_on.collision_imminent is True else None
    if collision_risk_score is None:
        unavailable.add("collision_risk_score")

    autonomy_confidence = _autonomy_confidence(qiki_response)
    if autonomy_confidence is not None:
        partial.add("autonomy_confidence")
    else:
        unavailable.add("autonomy_confidence")

    mission_risk_state = _mission_risk_state(
        alert_summary=alert_summary,
        safe_envelope_state=always_on.safe_envelope_state,
        telemetry_age_ms=always_on.telemetry_age_ms,
    )

    return DerivedOperatorIndicators(
        power_margin_state=power_margin_state,
        time_to_power_deficit=time_to_power_deficit,
        time_to_battery_critical=time_to_battery_critical,
        thermal_margin_state=thermal_margin_state,
        hotspot_source=hotspot_source,
        time_to_overheat=None,
        trajectory_deviation=trajectory_deviation,
        eta_to_target=eta_to_target,
        attitude_stability=attitude_stability,
        maneuver_feasibility=maneuver_feasibility,
        fuel_margin_to_plan=None,
        rcs_authority_available=rcs_authority_available,
        commandability_state=commandability_state,
        data_freshness_state=data_freshness_state,
        sensor_trust_state=sensor_trust_snapshot.state.value,
        sensor_trust_summary=sensor_trust_snapshot.short_chip,
        sensor_trust_effect=sensor_trust_snapshot.operator_effect_ru,
        sensor_trust_confidence=sensor_trust_snapshot.confidence,
        collision_risk_score=collision_risk_score,
        intervention_required=operator_loop.operator_action_required,
        autonomy_confidence=autonomy_confidence,
        mission_risk_state=mission_risk_state,
        partial_fields=tuple(sorted(partial)),
        unavailable_fields=tuple(sorted(unavailable)),
    )


def _build_subsystem_chips(
    *,
    hardware_model: HardwareViewModel | None,
    qiki_response: QikiChatResponseV1 | None,
    qiki_pending_action_title: str | None,
    derived: DerivedOperatorIndicators,
    telemetry_age_ms: float | None,
) -> tuple[SubsystemChip, ...]:
    stale = telemetry_age_ms is not None and telemetry_age_ms >= COMMS_AGE_CRIT_S * 1000.0
    # DISPLAY_CANON строка №4: PWR несёт двойной якорь «SoC% ~мин» (таймер жизни)
    runtime_min = _field_num(hardware_model, "power", "power.runtime_min")
    power_anchor_extra = f" ~{runtime_min:.0f}м" if runtime_min is not None else ""
    chips = [
        _subsystem_chip(
            hardware_model=hardware_model,
            subsystem_id="power",
            label="PWR",
            action="select_subsystem",
            target="power",
            summary_fallback="no power truth",
            numeric_key="power.soc",
            stale=stale,
            anchor_extra=power_anchor_extra,
        ),
        _subsystem_chip(
            hardware_model=hardware_model,
            subsystem_id="thermal",
            label="THRM",
            action="select_subsystem",
            target="thermal",
            summary_fallback="no thermal truth",
            numeric_key="thermal.core_c",
            stale=stale,
            anchor_unit="°",
        ),
        _subsystem_chip(
            hardware_model=hardware_model,
            subsystem_id="propulsion",
            label="PROP",
            action="select_subsystem",
            target="propulsion",
            summary_fallback="no propulsion truth",
            numeric_key="propulsion.fuel_pct",
            stale=stale,
        ),
        _subsystem_chip(
            hardware_model=hardware_model,
            subsystem_id="hull",
            label="HULL",
            action="select_subsystem",
            target="hull",
            summary_fallback="no hull truth",
            numeric_key="hull.integrity_pct",
            stale=stale,
        ),
        _subsystem_chip(
            hardware_model=hardware_model,
            subsystem_id="compute",
            label="CPU",
            action="select_subsystem",
            target="compute",
            summary_fallback="no compute truth",
            numeric_key="compute.cpu_pct",
            stale=stale,
        ),
        _qiki_chip(
            qiki_response=qiki_response,
            qiki_pending_action_title=qiki_pending_action_title,
            stale=stale,
            mission_risk_state=derived.mission_risk_state,
        ),
    ]
    return tuple(chips)


def _build_operator_loop_state(
    *,
    current_level: str,
    replay_mode: bool,
    selected_incident_id: str | None,
    selected_subsystem: str | None,
    command_mode_open: bool,
    status_text: str,
    pending_command_count: int,
    human_ack_required: bool,
    has_selected_incident: bool,
    alert_summary: AlertSummary,
    last_command_status: str | None,
    last_command_summary: str | None,
    attach_procedure_active: bool = False,
    attach_procedure_paused: bool = False,
    world_paused: bool = False,
) -> OperatorLoopState:
    operator_action_required = human_ack_required or alert_summary.action_required
    level = current_level.strip().lower()
    return OperatorLoopState(
        last_command_status=last_command_status or ("awaiting_confirm" if human_ack_required else "idle"),
        last_command_summary=last_command_summary or status_text.strip() or "Command loop idle",
        pending_command_count=max(0, int(pending_command_count)),
        operator_action_required=operator_action_required,
        command_mode_state="open" if command_mode_open else "standby",
        hotkey_context=_hotkey_context(
            command_mode_open=command_mode_open,
            current_level=level,
            has_selected_incident=has_selected_incident,
        ),
        status_text=status_text.strip() or "Команды: help",
        current_level=level,
        replay_mode=replay_mode,
        selected_incident_id=selected_incident_id,
        selected_subsystem=selected_subsystem,
        has_selected_incident=has_selected_incident,
        incident_controls_visible=level in {"f1", "f3"},
        page_controls_visible=level in {"f3", "f6"},
        attach_procedure_active=attach_procedure_active,
        attach_procedure_paused=attach_procedure_paused,
        world_paused=world_paused,
        qiki_action_pending=human_ack_required,
    )


def _subsystem_chip(
    *,
    hardware_model: HardwareViewModel | None,
    subsystem_id: str,
    label: str,
    action: str,
    target: str,
    summary_fallback: str,
    numeric_key: str,
    stale: bool,
    anchor_unit: str = "%",
    anchor_extra: str = "",
) -> SubsystemChip:
    subsystem = _subsystem(hardware_model, subsystem_id)
    if subsystem is None:
        return SubsystemChip(
            slug=subsystem_id,
            label=label,
            status="nodata",
            severity="unavailable",
            short_summary="NO DATA",
            hint=summary_fallback,
            numeric_anchor=None,
            stale=stale,
            degraded=True,
            action=action,
            target=target,
        )
    numeric_anchor = _field_num(hardware_model, subsystem_id, numeric_key)
    status = _VIEW_STATUS_KEY.get(subsystem.status, "nodata")
    severity = _VIEW_STATUS_SEVERITY.get(subsystem.status, "unavailable")
    summary = str(subsystem.summary or "").strip() or summary_fallback
    anchor_text = (
        f"{numeric_anchor:.0f}{anchor_unit}{anchor_extra}" if numeric_anchor is not None else ""
    )
    return SubsystemChip(
        slug=subsystem_id,
        label=label,
        status=status,
        severity=severity,
        short_summary=summary[:36],
        hint=_chip_hint(subsystem),
        numeric_anchor=numeric_anchor,
        anchor_text=anchor_text,
        stale=stale,
        degraded=status != "ok",
        action=action,
        target=target,
    )


def _qiki_chip(
    *,
    qiki_response: QikiChatResponseV1 | None,
    qiki_pending_action_title: str | None,
    stale: bool,
    mission_risk_state: str | None,
) -> SubsystemChip:
    if qiki_pending_action_title:
        return SubsystemChip(
            slug="qiki",
            label="QIKI",
            status="pending",
            severity="warning",
            short_summary="pending confirm",
            hint=qiki_pending_action_title[:36],
            stale=stale,
            degraded=True,
            action="show_level",
            target="f1",
        )
    if qiki_response is not None and qiki_response.legality is not None:
        status = str(qiki_response.legality.status or "ready").strip().lower() or "ready"
        severity = "critical" if status == "unsafe" else ("warning" if status != "allowed" else "normal")
        summary = status.replace("_", " ")
        hint = _text_from_bilingual(qiki_response.legality.reason) or "loop active"
        return SubsystemChip(
            slug="qiki",
            label="QIKI",
            status=status,
            severity=severity,
            short_summary=summary[:36],
            hint=hint[:36],
            stale=stale,
            degraded=severity != "normal" or mission_risk_state in {"warning", "critical"},
            action="show_level",
            target="f1",
        )
    return SubsystemChip(
        slug="qiki",
        label="QIKI",
        status="ready",
        severity="normal",
        short_summary="ready",
        hint="no pending action",
        stale=stale,
        degraded=False,
        action="show_level",
        target="f1",
    )


def _build_incident_alerts(incidents: list[dict[str, Any]]) -> list[OperatorAlert]:
    alerts: list[OperatorAlert] = []
    for index, incident in enumerate(incidents):
        incident_id = str(incident.get("id") or "incident").strip() or "incident"
        description = str(incident.get("description") or incident.get("message") or "No description").strip()
        severity = "critical" if str(incident.get("severity") or "").upper().startswith("C") else "warning"
        alerts.append(
            OperatorAlert(
                id=f"incident:{incident_id}",
                severity=severity,
                title=f"Incident {incident_id}",
                short_meaning=description,
                source="active incident queue / qiki.events.v1.audit",
                operator_effect=(
                    "The incident path already has an open C/A signal "
                    "that can override normal scene reading."
                ),
                next_action_hint=(
                    "Open the incident drill-down or acknowledge it "
                    "if the operator already understands the hazard."
                ),
                incident_id=incident_id,
                order_index=10 + index,
            )
        )
    return alerts


def _build_system_alerts(
    *,
    hardware_model: HardwareViewModel | None,
    telemetry: dict[str, Any],
    safe_mode: dict[str, Any],
    objective: dict[str, Any],
    active_incidents: int,
    incidents: list[dict[str, Any]],
    radar_tracks: dict[str, dict[str, Any]],
) -> list[OperatorAlert]:
    follow_up_status = str(objective.get("follow_up_status") or "").strip().lower()
    cards = build_system_cards(
        hardware_model,
        telemetry=telemetry,
        safe_mode=safe_mode,
        observation_objective=objective,
        active_incidents=active_incidents,
        incidents=incidents,
        radar_tracks=radar_tracks,
    )
    alerts: list[OperatorAlert] = []
    for card in cards:
        severity = _SYSTEM_ALERT_STATUS.get(card.status)
        if severity is None:
            continue
        if card.subsystem_id == "safety" and active_incidents > 0 and safe_mode.get("active") is not True:
            continue
        if card.subsystem_id == "navigation" and follow_up_status in _OBJECTIVE_ALERTS:
            continue
        if card.subsystem_id == "sensors" and not bool(objective.get("track_visible")):
            continue
        raw_sources = F2_CARD_SOURCE_MAP.get(card.subsystem_id, {}).get("raw_sources", ())
        source_text = (
            " + ".join(str(item) for item in raw_sources)
            if isinstance(raw_sources, tuple)
            else str(raw_sources)
        )
        alerts.append(
            OperatorAlert(
                id=f"system:{card.subsystem_id}",
                severity=severity,
                title="Питание / Заряд" if card.subsystem_id == "power" else card.title,
                short_meaning=card.current_status,
                source=source_text or "hardware_view_model",
                operator_effect=card.operational_effect,
                next_action_hint=card.next_attention,
                order_index=100 + card.order_index,
            )
        )
    return alerts


def _build_objective_alerts(objective: dict[str, Any]) -> list[OperatorAlert]:
    follow_up_status = str(objective.get("follow_up_status") or "").strip().lower()
    config = _OBJECTIVE_ALERTS.get(follow_up_status)
    if config is None:
        return []
    summary = _pick_text(objective, "follow_up_summary_ru", "follow_up_summary_en")
    allowed_when = _pick_text(objective, "follow_up_allowed_when_ru", "follow_up_allowed_when_en")
    return [
        OperatorAlert(
            id=f"objective:{follow_up_status}",
            severity=str(config["severity"]),
            title=str(config["title"]),
            short_meaning=summary or str(config["title"]),
            source=str(config["source"]),
            operator_effect=str(config["effect"]),
            next_action_hint=allowed_when or None,
            order_index=30,
        )
    ]


def _build_observation_confidence_alerts(objective: dict[str, Any]) -> list[OperatorAlert]:
    if not objective:
        return []
    target = str(objective.get("target_designator") or "").strip()
    track_visible = bool(objective.get("track_visible"))
    if not target or track_visible:
        return []
    return [
        OperatorAlert(
            id="objective:observation-confidence",
            severity="warning",
            title="Observation confidence missing",
            short_meaning=f"Target {target} is not visible on the current live contour.",
            source="objective target + radar visibility truth",
            operator_effect=(
                "Observation and route interpretation should stay conservative "
                "until the contact is reacquired."
            ),
            next_action_hint="Reacquire the target or wait for live radar truth before relying on the contour.",
            order_index=40,
        )
    ]


def _build_qiki_alerts(response: QikiChatResponseV1 | None) -> list[OperatorAlert]:
    if response is None:
        return []
    alerts: list[OperatorAlert] = []
    if response.legality is not None and response.legality.status != "allowed":
        severity = "critical" if response.legality.status == "unsafe" else "warning"
        title = _text_from_bilingual(response.reply.title) if response.reply is not None else "QIKI legality gate"
        status_label = response.legality.status.replace("_", " ")
        reason = _text_from_bilingual(response.legality.reason)
        allowed_when = _text_from_bilingual(response.legality.allowed_when)
        alerts.append(
            OperatorAlert(
                id=f"qiki:legality:{response.legality.reason_code}",
                severity=severity,
                title=title or "QIKI legality gate",
                short_meaning=reason or f"QIKI marked the action as {status_label}.",
                source=f"QIKI legality / domain={response.legality.domain}",
                operator_effect=(
                    "The latest QIKI decision is constraining the requested action, "
                    "so the operator should not treat the scene as freely actionable."
                ),
                next_action_hint=allowed_when or None,
                order_index=50,
            )
        )
    for index, warning in enumerate(response.warnings[:2]):
        warning_text = _text_from_bilingual(warning)
        if not warning_text:
            continue
        alerts.append(
            OperatorAlert(
                id=f"qiki:warning:{index}",
                severity="warning",
                title="QIKI caution",
                short_meaning=warning_text,
                source="QIKI warnings[]",
                operator_effect=(
                    "QIKI is signaling an immediate caution that should be resolved "
                    "before pushing the current contour harder."
                ),
                order_index=60 + index,
            )
        )
    return alerts


def _pick_focus_alert(alerts: tuple[OperatorAlert, ...], selected_incident_id: str | None) -> OperatorAlert | None:
    if not alerts:
        return None
    if selected_incident_id:
        for alert in alerts:
            if alert.incident_id == selected_incident_id:
                return alert
    return alerts[0]


def _pick_text(source: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _text_from_bilingual(value: BilingualText | None) -> str:
    if value is None:
        return ""
    text = str(value.ru or "").strip()
    if text:
        return text
    return str(value.en or "").strip()


def _subsystem(hardware_model: HardwareViewModel | None, subsystem_id: str) -> SubsystemView | None:
    if hardware_model is None:
        return None
    return hardware_model.subsystems.get(subsystem_id)


def _field(hardware_model: HardwareViewModel | None, subsystem_id: str, key: str) -> TelemetryField | None:
    subsystem = _subsystem(hardware_model, subsystem_id)
    if subsystem is None:
        return None
    return next((field for field in subsystem.fields if field.key == key), None)


def _field_num(hardware_model: HardwareViewModel | None, subsystem_id: str, key: str) -> float | None:
    field = _field(hardware_model, subsystem_id, key)
    if field is None:
        return None
    value = field.value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _field_text(hardware_model: HardwareViewModel | None, subsystem_id: str, key: str) -> str | None:
    field = _field(hardware_model, subsystem_id, key)
    if field is None:
        return None
    text = str(field.value or "").strip()
    return text or None


def _raw_value(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _raw_text(data: dict[str, Any], *paths: tuple[str, ...]) -> str | None:
    for path in paths:
        value = _raw_value(data, path)
        text = str(value or "").strip()
        if text:
            return text
    return None


def _raw_num(data: dict[str, Any], *paths: tuple[str, ...]) -> float | None:
    for path in paths:
        value = _raw_value(data, path)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        return float(value)
    return None


def _raw_bool(data: dict[str, Any], *paths: tuple[str, ...]) -> bool | None:
    for path in paths:
        value = _raw_value(data, path)
        if isinstance(value, bool):
            return value
    return None


def _mission_phase_label(*, telemetry: dict[str, Any], replay_mode: bool) -> str | None:
    if replay_mode:
        return "REPLAY"
    sim_state = telemetry.get("sim_state")
    if not isinstance(sim_state, dict):
        return None
    state_name = str(sim_state.get("fsm_state") or "").strip().upper()
    if not state_name:
        return None
    speed = sim_state.get("speed")
    speed_text = f" {float(speed):.2f}x" if isinstance(speed, (int, float)) and not isinstance(speed, bool) else ""
    if bool(sim_state.get("paused")):
        return f"PAUSED{speed_text}"
    return f"{state_name}{speed_text}"


def _world_run_state(*, telemetry: dict[str, Any], replay_mode: bool) -> str:
    """MISSION_CONTROL_STRIP canon WORLD code: RUN / PAUSE / STOP / REPLAY / WAIT.

    Honest mapping: RUN is claimed only for an explicitly RUNNING world; boot/init/
    unknown states stay WAIT (canon: no-data shows WAIT, never «Нет данных»).
    """
    if replay_mode:
        return "REPLAY"
    sim_state = telemetry.get("sim_state")
    if not isinstance(sim_state, dict):
        return "WAIT"
    state_name = str(sim_state.get("fsm_state") or "").strip().upper()
    if not state_name:
        return "WAIT"
    if bool(sim_state.get("paused")):
        return "PAUSE"
    if state_name in {"STOPPED", "HALTED", "STOP", "SHUTDOWN"}:
        return "STOP"
    if state_name == "RUNNING":
        return "RUN"
    return "WAIT"


def _control_authority_label(
    *,
    safe_mode: dict[str, Any],
    qiki_pending_action: dict[str, Any] | None,
    qiki_response: QikiChatResponseV1 | None,
    replay_mode: bool,
) -> str:
    if replay_mode:
        return "analysis"
    if bool(safe_mode.get("active")):
        return str(safe_mode.get("authority") or "safe-mode")
    if qiki_pending_action is not None:
        return "operator-confirm"
    if qiki_response is not None and qiki_response.legality is not None:
        status = str(qiki_response.legality.status or "qiki").strip().lower() or "qiki"
        return f"qiki-{status}"
    return "operator"


def _telemetry_age_ms(last_telemetry_received_wall: float | None) -> float | None:
    if last_telemetry_received_wall is None:
        return None
    delta = max(0.0, datetime.now(tz=timezone.utc).timestamp() - last_telemetry_received_wall)
    return round(delta * 1000.0, 1)


def _timestamp_text(last_telemetry_received_wall: float | None) -> str | None:
    if last_telemetry_received_wall is None:
        return None
    return datetime.fromtimestamp(last_telemetry_received_wall, tz=timezone.utc).strftime("%H:%M:%SZ")


def _link_status_label(
    *,
    hardware_model: HardwareViewModel | None,
    nats_state: str,
    replay_mode: bool,
    telemetry_age_ms: float | None,
) -> str:
    if replay_mode:
        return "replay"
    if nats_state != "connected":
        return "offline"
    link_state = _field_text(hardware_model, "comms", "comms.link_state")
    if link_state:
        normalized = link_state.lower()
        # collector's field value is operator display text (В РАБОТЕ/ДЕГРАДАЦИЯ/
        # НЕТ ДАННЫХ for F2); fold it back so this truth-source stays code-valued
        normalized = {
            "в работе": "online",
            "деградация": "degraded",
            "нет данных": "offline",
        }.get(normalized, normalized)
        if normalized in {"down", "offline"}:
            return "offline"
        if telemetry_age_ms is not None and telemetry_age_ms >= COMMS_AGE_WARN_S * 1000.0:
            return "degraded"
        return normalized
    return "connected"


def _safe_envelope_state(*, alert_summary: AlertSummary, safe_mode: dict[str, Any]) -> str:
    if bool(safe_mode.get("active")):
        return "safe-mode"
    if alert_summary.critical_count > 0:
        return "breach"
    if alert_summary.warning_count > 0:
        return "constrained"
    return "nominal"


def _qiki_assist_status(
    *,
    qiki_response: QikiChatResponseV1 | None,
    qiki_pending_action: dict[str, Any] | None,
) -> str | None:
    if qiki_pending_action is not None:
        return "awaiting_human_ack"
    if qiki_response is None:
        return None
    if qiki_response.legality is not None:
        return str(qiki_response.legality.status or "ready").strip().lower() or "ready"
    if qiki_response.reply is not None:
        return "reply_ready"
    return None


def _power_margin_state(*, power_balance_mw: float | None, battery_charge_percent: float | None) -> str | None:
    if power_balance_mw is not None:
        if power_balance_mw < 0:
            return "critical"
        if power_balance_mw == 0:
            return "tight"
    if battery_charge_percent is not None:
        if battery_charge_percent <= POWER_SOC_CRIT_PCT:
            return "critical"
        if battery_charge_percent <= POWER_SOC_WARN_PCT:
            return "warning"
        return "nominal"
    return None


def _thermal_margin_state(core_temperature_c: float | None, hotspot_source: str | None) -> str | None:
    if core_temperature_c is None:
        return None
    if core_temperature_c >= THERMAL_CORE_CRIT_C or hotspot_source and "TRIP" in hotspot_source.upper():
        return "critical"
    if core_temperature_c >= THERMAL_CORE_WARN_C or hotspot_source and "WARN" in hotspot_source.upper():
        return "warning"
    return "nominal"


def _attitude_stability(hardware_model: HardwareViewModel | None) -> str | None:
    rates = [
        abs(value)
        for value in (
            _field_num(hardware_model, "navigation", "navigation.p_rate_dps"),
            _field_num(hardware_model, "navigation", "navigation.y_rate_dps"),
            _field_num(hardware_model, "navigation", "navigation.r_rate_dps"),
        )
        if value is not None
    ]
    if not rates:
        return None
    peak = max(rates)
    if peak >= 10.0:
        return "unstable"
    if peak >= 2.0:
        return "drifting"
    return "stable"


def _maneuver_feasibility(
    hardware_model: HardwareViewModel | None,
    fuel_remaining_percent: float | None,
) -> str | None:
    subsystem = _subsystem(hardware_model, "propulsion")
    if subsystem is None:
        return None
    if subsystem.status is ViewStatus.CRIT:
        return "blocked"
    # Аудит 0.17: топливо сравнивается с ТОПЛИВНЫМ порогом, а не с батарейным
    # (значения сегодня совпадают, но владельцы разные — семантика важнее).
    if subsystem.status is ViewStatus.WARN or (
        fuel_remaining_percent is not None and fuel_remaining_percent <= PROPULSION_FUEL_WARN_PCT
    ):
        return "constrained"
    return "available"


def _rcs_authority_available(hardware_model: HardwareViewModel | None) -> bool | None:
    active_count = _field_num(hardware_model, "propulsion", "propulsion.rcs_active_count")
    total_thrust = _field_num(hardware_model, "propulsion", "propulsion.total_thrust_n")
    if active_count is None and total_thrust is None:
        return None
    if active_count is not None:
        return active_count > 0
    return bool(total_thrust and total_thrust > 0)


def _commandability_state(
    *,
    replay_mode: bool,
    link_status: str | None,
    telemetry_age_ms: float | None,
) -> str:
    if replay_mode:
        return "replay-disabled"
    if link_status in {"offline", "down"}:
        return "blocked"
    if telemetry_age_ms is not None and telemetry_age_ms >= COMMS_AGE_WARN_S * 1000.0:
        return "degraded"
    return "commandable"


def _data_freshness_state(telemetry_age_ms: float | None) -> str:
    # MISSION_CONTROL_STRIP_CANON / ADR-0016: DATA freshness engineering codes.
    # No telemetry age → NODATA (honest, never "unknown"); age thresholds reuse the
    # comms warn/crit budgets (operator-console decision, not a telemetry-schema one).
    if telemetry_age_ms is None:
        return "NODATA"
    if telemetry_age_ms >= COMMS_AGE_CRIT_S * 1000.0:
        return "STALE"
    if telemetry_age_ms >= COMMS_AGE_WARN_S * 1000.0:
        return "LAG"
    return "OK"


def _autonomy_confidence(qiki_response: QikiChatResponseV1 | None) -> str | None:
    if qiki_response is None or qiki_response.legality is None:
        return None
    status = str(qiki_response.legality.status or "").strip().lower()
    if status == "allowed":
        return "high"
    if status in {"review", "hold", "deferred", "caution"}:
        return "guarded"
    if status:
        return "blocked"
    return None


def _mission_risk_state(
    *,
    alert_summary: AlertSummary,
    safe_envelope_state: str | None,
    telemetry_age_ms: float | None,
) -> str:
    if safe_envelope_state == "safe-mode" or alert_summary.critical_count > 0:
        return "critical"
    if telemetry_age_ms is not None and telemetry_age_ms >= COMMS_AGE_WARN_S * 1000.0:
        return "warning"
    if alert_summary.warning_count > 0:
        return "warning"
    return "nominal"


def _subsystem_status_label(hardware_model: HardwareViewModel | None, subsystem_id: str) -> str | None:
    subsystem = _subsystem(hardware_model, subsystem_id)
    if subsystem is None:
        return None
    return _VIEW_STATUS_KEY.get(subsystem.status)


def _chip_hint(subsystem: SubsystemView) -> str:
    for field in subsystem.fields:
        value = field.value
        if isinstance(value, bool) or value in {None, ""}:
            continue
        return f"{field.label}: {value}"[:40]
    return subsystem.summary[:40]


def _hotkey_context(*, command_mode_open: bool, current_level: str, has_selected_incident: bool) -> str:
    if command_mode_open:
        return "Enter — отправить | Esc — закрыть | q: — запрос к QIKI"
    if current_level in {"f3", "f6"}:
        return "PgUp/PgDn — страницы | ↑/↓ — выбор инцидента"
    if has_selected_incident:
        return "A — квитировать инцидент | X — снять квитированные"
    # без перечня экранов (DISPLAY_CANON строка №9): экраны показывают сами кнопки рейла;
    # H не упоминаем — справка живёт только на F1
    return "'/' ':' — команда"
