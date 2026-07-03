from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Button, Static

from qiki.services.operator_console.orion_v.body_physics_view_model import get_body_physics_console_view_model
from qiki.services.operator_console.orion_v.evidence_inspector import format_subsystem_inspector
from qiki.services.operator_console.orion_v.screens.body_structure_textual import BodyStructureTextualDashboard
from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    build_power_thermal_console_view_model_from_telemetry,
    format_soc_bat,
    format_soc_cap,
)
from qiki.services.operator_console.orion_v.screens.power_thermal_textual import PowerThermalTextualDashboard
from qiki.services.operator_console.orion_v.widgets.body_physics_panel import BodyPhysicsPanel
from qiki.services.operator_console.orion_v.body_structure_view_model import (
    format_body_structure_system_summary,
    get_body_structure_console_view_model,
)
from qiki.services.operator_console.orion_v.mfd_page_content import (
    render_left_mfd_page,
    render_right_mfd_page,
)
from qiki.services.operator_console.orion_v.ui_rich import semantic_update
from qiki.services.operator_console.orion_v.mfd_layout import (
    MFD_DEFAULT_LEFT_PAGE,
    MFD_DEFAULT_RIGHT_PAGE,
    mfd_button_class,
    mfd_button_specs,
    mfd_page_label,
    normalize_mfd_page,
    softkey_bar,
)
from qiki.services.operator_console.orion_v.hardware_view_model.types import (
    HardwareViewModel,
    SubsystemView,
    TelemetryField,
    ViewStatus,
)

F2_CARD_ORDER: tuple[str, ...] = (
    "body_structure",
    "docking",
    "power",
    "propulsion",
    "navigation",
    "sensors",
    "comms",
    "safety",
)


def _mfd_visual_domain(selector: str) -> str:
    if "left" in selector:
        return "left"
    if "right" in selector:
        return "right"
    if "power" in selector:
        return "power"
    if "thermal" in selector:
        return "thermal"
    if "evidence" in selector:
        return "evidence"
    return "status"


F2_CARD_TITLES: dict[str, str] = {
    "body_structure": "Корпус / Модули",
    "docking": "Стыковка / Узел",
    "power": "Питание / Заряд",
    "propulsion": "Двигатели / Движение",
    "navigation": "Навигация / Маршрут",
    "sensors": "Сенсоры / Радар / Наблюдение",
    "comms": "Связь / Канал / Протокол",
    "safety": "Безопасность / Целостность / Угрозы",
}

F2_CARD_SOURCE_MAP: dict[str, dict[str, tuple[str, ...] | str]] = {
    "body_structure": {
        "raw_sources": ("run_attach_pipeline", "EventStore audit", "ORION Evidence Card"),
        "derived": ("body_structure_view_model", "local self-check", "direct in-process"),
        "operator_text": "visible body-structure attach lifecycle seed status",
    },
    "docking": {
        "raw_sources": (
            "hardware_view_model.docking",
            "qiki.telemetry.docking.*",
            "qiki.telemetry.power.dock_bridge_state",
        ),
        "derived": ("docking.summary", "scene profile", "dock bridge context"),
        "operator_text": "station interface state, action gate, next docking attention",
    },
    "power": {
        "raw_sources": ("hardware_view_model.power", "qiki.telemetry.power.*", "qiki.telemetry.docking.*"),
        "derived": ("power.summary", "runtime/load-shed interpretation", "charging context"),
        "operator_text": "power availability, action limitation, recharge attention",
    },
    "propulsion": {
        "raw_sources": ("hardware_view_model.propulsion", "hardware_view_model.navigation"),
        "derived": ("propulsion.summary", "burn margin", "maneuver authority interpretation"),
        "operator_text": "maneuver health, motion authority, next burn concern",
    },
    "navigation": {
        "raw_sources": (
            "hardware_view_model.navigation",
            "active observation objective",
            "qiki objective follow_up/result fields",
            "qiki.telemetry.docking/orbit.*",
        ),
        "derived": ("scene profile", "route contour", "objective effect"),
        "operator_text": "route state, current action gate, next contour attention",
    },
    "sensors": {
        "raw_sources": ("hardware_view_model.sensors", "live radar tracks", "active observation objective"),
        "derived": ("sensor summary", "track availability", "observation context"),
        "operator_text": "sensor picture, observation confidence, next observation attention",
    },
    "comms": {
        "raw_sources": ("hardware_view_model.comms", "qiki.telemetry.comms.*"),
        "derived": ("comms.summary", "latency/loss freshness quality"),
        "operator_text": "link health, protocol confidence, next comms concern",
    },
    "safety": {
        "raw_sources": ("hardware_view_model.hull", "safe_mode events", "active incidents"),
        "derived": ("integrity summary", "hazard aggregation", "safety authority gate"),
        "operator_text": "hazard posture, operator restriction, next safety attention",
    },
}

_SEVERITY_LABELS: dict[ViewStatus, str] = {
    ViewStatus.OK: "stable",
    ViewStatus.WARN: "degraded",
    ViewStatus.CRIT: "critical",
    ViewStatus.NO_DATA: "unknown",
}

_STATUS_BADGES: dict[ViewStatus, str] = {
    ViewStatus.OK: "OK",
    ViewStatus.WARN: "WARN",
    ViewStatus.CRIT: "CRIT",
    ViewStatus.NO_DATA: "NO DATA",
}

_STATUS_BADGE_STYLES: dict[ViewStatus, str] = {
    ViewStatus.OK: "",
    ViewStatus.WARN: "bold #f2b84b",
    ViewStatus.CRIT: "bold #ff5f56",
    ViewStatus.NO_DATA: "dim",
}

_STATUS_RAIL_STYLES: dict[ViewStatus, str] = {
    ViewStatus.OK: "dim",
    ViewStatus.WARN: "bold #f2b84b",
    ViewStatus.CRIT: "bold #ff5f56",
    ViewStatus.NO_DATA: "dim",
}


@dataclass(slots=True)
class SystemCard:
    subsystem_id: str
    title: str
    status: ViewStatus
    current_status: str
    severity: str
    summary: str
    operational_effect: str
    next_attention: str
    quick_hint: str | None = None
    order_index: int = 0


_STATUS_CLASSES: dict[ViewStatus, str] = {
    ViewStatus.OK: "status-ok",
    ViewStatus.WARN: "status-warn",
    ViewStatus.CRIT: "status-crit",
    ViewStatus.NO_DATA: "status-unknown",
}


class SystemCardWidget(Static):
    """F2 card presenter. Visual severity comes from CSS classes, not inline Rich styles."""

    can_focus = True

    def __init__(self, card: SystemCard, *, selected: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._card = card
        self._selected = selected

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self.set_classes(self._class_string())
        self.update(_card_widget_text(self._card, selected=self._selected))

    def _class_string(self) -> str:
        classes = ["system-card", _STATUS_CLASSES[self._card.status]]
        if self._selected:
            classes.append("selected")
        return " ".join(classes)


def build_system_cards(
    hardware_model: HardwareViewModel | None,
    *,
    telemetry: dict[str, Any] | None = None,
    safe_mode: dict[str, Any] | None = None,
    observation_objective: dict[str, Any] | None = None,
    active_incidents: int = 0,
    incidents: list[dict[str, Any]] | None = None,
    radar_tracks: dict[str, dict[str, Any]] | None = None,
) -> list[SystemCard]:
    telemetry = telemetry or {}
    safe_mode = safe_mode or {}
    objective = dict(observation_objective or {})
    incidents = list(incidents or [])
    radar_tracks = dict(radar_tracks or {})
    scene_profile = _resolve_scene_profile(telemetry, objective)

    cards = [
        _build_body_structure_card(),
        _build_docking_card(hardware_model, telemetry=telemetry, scene_profile=scene_profile),
        _build_power_card(hardware_model, telemetry=telemetry, scene_profile=scene_profile),
        _build_propulsion_card(hardware_model, telemetry=telemetry, scene_profile=scene_profile),
        _build_navigation_card(hardware_model, telemetry=telemetry, objective=objective, scene_profile=scene_profile),
        _build_sensors_card(hardware_model, objective=objective, radar_tracks=radar_tracks),
        _build_comms_card(hardware_model, scene_profile=scene_profile),
        _build_safety_card(
            hardware_model,
            safe_mode=safe_mode,
            active_incidents=active_incidents,
            incidents=incidents,
        ),
    ]
    return sorted(cards, key=lambda card: (-_status_rank(card.status), card.order_index))


def render_system_cards(cards: list[SystemCard], *, selected_subsystem: str | None = None) -> str:
    return render_system_cards_with_safety(cards, safe_mode=None, selected_subsystem=selected_subsystem)


def _styled(text: str, style: str) -> str:
    escaped = escape(text)
    return f"[{style}]{escaped}[/]" if style else escaped


def _status_badge(status: ViewStatus) -> str:
    label = _STATUS_BADGES[status]
    style = _STATUS_BADGE_STYLES[status]
    return _styled(f"[{label}]", style)


def _card_title_line(card: SystemCard, *, selected: bool, select_action: str) -> str:
    rail = _styled("▌", _STATUS_RAIL_STYLES[card.status])
    marker = "[reverse bold cyan] SELECTED [/]" if selected else "[dim]        [/]"
    severity = _styled(card.severity.upper(), _STATUS_BADGE_STYLES[card.status])
    title = escape(card.title)
    # Keep the legacy plain "[severity]" token for existing text assertions and search,
    # then add a stronger state badge/rail for the operator scan path.
    return f"{rail} {marker} {title} [{card.severity}] {_status_badge(card.status)} [dim]{severity}[/] {select_action}"


def _card_widget_text(card: SystemCard, *, selected: bool) -> str:
    select_action = _action_link("select_subsystem", card.subsystem_id)
    marker = "SELECTED" if selected else "       "
    severity_token = _literal_bracketed(card.severity)
    badge_token = _literal_bracketed(_STATUS_BADGES[card.status])
    lines = [
        f"{marker} {escape(card.title)} {severity_token} {badge_token} {select_action}",
        f"Status: {escape(card.current_status)}",
        f"Summary: {escape(card.summary)}",
        f"Effect: {escape(card.operational_effect)}",
        f"Next: {escape(card.next_attention)}",
    ]
    if card.quick_hint:
        lines.append(f"Hint: {escape(card.quick_hint)}")
    return "\n".join(lines)


def _literal_bracketed(value: str) -> str:
    return f"\\[{escape(value)}]"


def render_system_cards_with_safety(
    cards: list[SystemCard],
    *,
    safe_mode: dict[str, Any] | None,
    selected_subsystem: str | None = None,
) -> str:
    lines = [
        "[F2] Systems Overview",
        "",
        "Обзор оператора: состояние → влияние на действия → куда смотреть дальше",
        "Правда: hardware_view_model + телеметрия/цель/события — уже в ORION V",
    ]
    authority = _safe_mode_header_line(safe_mode)
    if authority:
        lines.append(authority)
    lines.append("")
    for card in cards:
        selected = selected_subsystem == card.subsystem_id
        select_action = _action_link("select_subsystem", card.subsystem_id)
        lines.append(_card_title_line(card, selected=selected, select_action=select_action))
        lines.append(f"   Status: {escape(card.current_status)} {_status_badge(card.status)}")
        lines.append(f"   Summary: {escape(card.summary)}")
        lines.append(f"   Effect: {escape(card.operational_effect)}")
        lines.append(f"   Next: {escape(card.next_attention)}")
        if card.quick_hint:
            lines.append(f"   Hint: [dim]{escape(card.quick_hint)}[/]")
        lines.append("")
    return "\n".join(lines).rstrip()


def _build_body_structure_card() -> SystemCard:
    vm = get_body_structure_console_view_model()
    status = ViewStatus.OK if vm.seed_status == "online" else ViewStatus.NO_DATA
    if vm.last_decision == "waiting":
        summary = (
            f"interactive seed ready; modules={vm.attached_modules_count}; "
            f"F06={vm.after_mount_state}; action=press B"
        )
        effect = "Waiting for operator action: press B to run attach self-check."
        next_attention = "F8 Evidence is empty until the self-check produces an audit-backed card."
        current_status = "online: waiting for B"
    elif vm.interaction_state == "already_attached":
        summary = (
            f"already attached; modules={vm.attached_modules_count}; "
            f"F06={vm.after_mount_state}; press R to reset"
        )
        effect = "The positive attach seed has already run; reset to replay the visible loop."
        next_attention = f"F8 Evidence: {vm.evidence_card_type} / {vm.evidence_card_id}."
        current_status = "online: already attached"
    else:
        summary = (
            f"Before modules={vm.before_modules_count}, F06={vm.before_mount_state}; "
            f"After modules={vm.after_modules_count}, F06={vm.after_mount_state}; "
            f"module={vm.module_id}; ready={str(vm.runtime_ready).lower()}; "
            f"capability={vm.capability_status}; evidence={vm.trust_status}"
        )
        effect = (
            "Interactive attach lifecycle seed is visible: operator action -> "
            "run_attach_pipeline -> audit -> Evidence Card -> ORION F1/F2/F8."
        )
        next_attention = (
            f"F8 Evidence: {vm.evidence_card_type} / {vm.evidence_card_id}. "
            "This is local self-check telemetry, not NATS flight telemetry."
        )
        current_status = f"online: {vm.last_decision} on {vm.mount_point}"
    return _make_card(
        "body_structure",
        status=status,
        current_status=current_status,
        summary=summary,
        operational_effect=effect,
        next_attention=next_attention,
        quick_hint=format_body_structure_system_summary(vm),
    )


def _build_docking_card(
    hardware_model: HardwareViewModel | None,
    *,
    telemetry: dict[str, Any],
    scene_profile: str,
) -> SystemCard:
    subsystem = _subsystem(hardware_model, "docking")
    power = _subsystem(hardware_model, "power")
    status = _status_of(subsystem)
    state = _field_text(subsystem, "docking.state")
    lock_state = _field_text(subsystem, "docking.lock")
    dock_bridge = _field_text(power, "power.dock_bridge_state")
    distance = _field_text(subsystem, "docking.distance_m")
    approach = _field_text(subsystem, "docking.approach_mps")
    alignment = _field_text(subsystem, "docking.alignment_error_deg")
    docking_connected = _pick_bool(telemetry, ["docking", "connected"]) is True
    state_norm = state.lower()
    lock_norm = lock_state.lower()
    docked = docking_connected or "locked" in lock_norm or any(
        token in state_norm for token in ("docked", "capture", "charging")
    )
    active_sequence = any(token in state_norm for token in ("approach", "align", "capture"))
    summary_parts = [_summary_text(subsystem)]
    if dock_bridge != "Нет данных":
        summary_parts.append(f"dock bridge {dock_bridge}")
    summary = _join_summary(summary_parts)
    if docked:
        current_status = "station interface engaged"
        effect = "Station services and release flow are the main action gate right now."
        next_attention = "Verify release or charge intent before leaving station."
    elif active_sequence:
        current_status = "docking sequence active"
        effect = "Alignment and closure speed limit safe operator actions until capture settles."
        attention_parts = [
            f"distance {distance}" if distance != "Нет данных" else "",
            f"approach {approach}" if approach != "Нет данных" else "",
            f"alignment {alignment}" if alignment != "Нет данных" else "",
        ]
        next_attention = _join_summary([part for part in attention_parts if part])
        if next_attention == "Нет данных":
            next_attention = "Settle alignment and closure speed before capture."
    elif scene_profile == "docked":
        current_status = "dock state unresolved"
        effect = "Dock contour is still active, but truth is not yet coherent enough to trust release steps."
        next_attention = "Confirm docking state and lock path before changing contour."
        status = _merge_status(status, ViewStatus.WARN)
    elif status is ViewStatus.NO_DATA:
        current_status = "truth incomplete"
        effect = "There is no honest docking truth to interpret yet, so this card should not drive decisions."
        next_attention = "Wait for docking telemetry before treating this as a live contour."
    else:
        current_status = "not in docking contour"
        effect = "Docking does not currently constrain route or maneuver decisions."
        next_attention = "No immediate docking follow-up."
    return _make_card(
        "docking",
        status=status,
        current_status=current_status,
        summary=summary,
        operational_effect=effect,
        next_attention=next_attention,
        quick_hint="F1 keeps the active scene; F3 is for deeper docking detail.",
    )


def _build_power_card(
    hardware_model: HardwareViewModel | None,
    *,
    telemetry: dict[str, Any],
    scene_profile: str,
) -> SystemCard:
    subsystem = _subsystem(hardware_model, "power")
    status = _status_of(subsystem)
    runtime_min = _field_float(subsystem, "power.runtime_min")
    load_shedding = _field_text(subsystem, "power.load_shedding")
    shed_reasons = _field_text(subsystem, "power.shed_reasons")
    dock_bridge = _field_text(subsystem, "power.dock_bridge_state")
    limit_mode = _field_text(subsystem, "power.limit_mode")
    charging_supported = (
        scene_profile == "docked"
        and dock_bridge != "Нет данных"
        and any(token in dock_bridge.lower() for token in ("on", "active", "online", "enabled", "locked", "док"))
    )
    if _looks_enabled(load_shedding) or status is ViewStatus.CRIT:
        current_status = "power constrained"
        effect = "Available actions can be reduced by EPS limits or shed loads."
        next_attention = (
            f"Track shed reasons: {shed_reasons}."
            if shed_reasons != "Нет данных"
            else "Resolve EPS shedding before long procedures."
        )
    elif charging_supported:
        current_status = "charging supported"
        effect = "Dockside power supports the current station contour and reduces route pressure."
        next_attention = "Use station time to recover margin before undock."
    elif _looks_enabled(limit_mode) or status is ViewStatus.WARN:
        current_status = "power margin reduced"
        effect = (
            "The contour is still live, but higher-load actions should be checked "
            "against runtime and bus stability."
        )
        next_attention = (
            f"Remaining runtime is about {runtime_min:.0f} min."
            if runtime_min is not None
            else "Watch runtime and bus voltage before extending the contour."
        )
    elif status is ViewStatus.NO_DATA:
        current_status = "truth incomplete"
        effect = "Power truth is not established yet, so F2 should not invent a stability claim."
        next_attention = "Wait for EPS telemetry before trusting power margin."
    else:
        current_status = "self-powered stable"
        effect = "No immediate EPS gate is limiting the current operator flow."
        next_attention = "Watch runtime before any extended transit."
    evidence_line = _power_evidence_line(subsystem)
    summary = _summary_text(subsystem)
    summary = f"{summary} | source: hardware_view_model / telemetry"
    if evidence_line:
        summary = f"{summary} | {evidence_line}"
    pdu_evidence = _pdu_evidence_line(subsystem)
    if pdu_evidence:
        summary = f"{summary} | {pdu_evidence}"
    return _make_card(
        "power",
        status=status,
        current_status=current_status,
        summary=summary,
        operational_effect=effect,
        next_attention=next_attention,
        quick_hint="F3 is the place for raw EPS traces if shedding or limits appear.",
    )


def _build_propulsion_card(
    hardware_model: HardwareViewModel | None,
    *,
    telemetry: dict[str, Any],
    scene_profile: str,
) -> SystemCard:
    del telemetry, scene_profile
    subsystem = _subsystem(hardware_model, "propulsion")
    status = _status_of(subsystem)
    burn_time = _field_float(subsystem, "propulsion.burn_time_min")
    active_thrusters = _field_text(subsystem, "propulsion.rcs_active_count")
    thrust = _field_text(subsystem, "propulsion.total_thrust_n")
    if status is ViewStatus.CRIT:
        current_status = "maneuver authority constrained"
        effect = "Translation and procedure execution may fail or require immediate operator caution."
        next_attention = "Resolve propulsion faults or fuel exhaustion before committing to motion changes."
    elif status is ViewStatus.WARN:
        current_status = "maneuver margin reduced"
        effect = "Propulsion still responds, but burn margin or actuator health can limit the next action."
        next_attention = (
            f"Remaining burn margin is about {burn_time:.0f} min."
            if burn_time is not None
            else "Track fuel and actuator health during the next maneuver."
        )
    elif active_thrusters != "Нет данных" and active_thrusters not in {"0", "0.0"}:
        current_status = "thrust active"
        effect = "Motion is being actively generated, so propulsion cost should be watched alongside power and thermal."
        next_attention = f"Current thrust context: {thrust}."
    elif status is ViewStatus.NO_DATA:
        current_status = "truth incomplete"
        effect = "Propulsion health is not available yet, so motion authority should be treated as unknown."
        next_attention = "Wait for propulsion telemetry before leaning on maneuver assumptions."
    else:
        current_status = "maneuver authority available"
        effect = "No immediate propulsion gate is blocking the present contour."
        next_attention = "Keep fuel and motor temperatures under watch during sustained burns."
    summary = _summary_text(subsystem)
    rcs_evidence = _rcs_evidence_line(subsystem)
    if rcs_evidence:
        summary = f"{summary} | {rcs_evidence}"
    return _make_card(
        "propulsion",
        status=status,
        current_status=current_status,
        summary=summary,
        operational_effect=effect,
        next_attention=next_attention,
        quick_hint="Use F3 only if you need per-thruster or motor detail.",
    )


def _build_navigation_card(
    hardware_model: HardwareViewModel | None,
    *,
    telemetry: dict[str, Any],
    objective: dict[str, Any],
    scene_profile: str,
) -> SystemCard:
    subsystem = _subsystem(hardware_model, "navigation")
    status = _status_of(subsystem)
    follow_up = _objective_follow_up_contract(objective)
    result = _observation_result_contract(objective)
    route_role = str(objective.get("route_role") or "").strip().lower()
    if follow_up is not None:
        if follow_up["status"] == "review_required":
            status = _merge_status(status, ViewStatus.CRIT)
        else:
            status = _merge_status(status, ViewStatus.WARN)
    if result is not None and result["status"] == "signature_changed":
        status = _merge_status(status, ViewStatus.WARN)
    if scene_profile == "orbital_hold":
        status = _merge_status(status, ViewStatus.WARN)
    if follow_up is not None and follow_up["status"] == "review_required":
        current_status = "review gate active"
        effect = "F1 action flow is constrained until the observation review is acknowledged and closed."
        next_attention = follow_up.get("allowed_when_ru") or "Close the review gate before continuing the contour."
    elif follow_up is not None and follow_up["status"] == "hold_for_recheck":
        current_status = "route paused for recheck"
        effect = "The same contour remains active, but only cautious recheck actions are allowed next."
        next_attention = follow_up.get("allowed_when_ru") or "Proceed only through the recheck path."
    elif follow_up is not None and follow_up["status"] == "resume_observation":
        current_status = "same contour reopened"
        effect = "One safe observation step is available on the same route contour."
        next_attention = follow_up.get("allowed_when_ru") or "Use the reopened observation window while it stays valid."
    elif result is not None and result["status"] == "signature_changed":
        current_status = "signature changed on contour"
        effect = (
            "The contour remains truthful, but the observed target identity changed "
            "and should reshape next decisions."
        )
        next_attention = (
            result.get("summary_ru") or "Carry the changed signature into the next observation step."
        )
    elif result is not None and result["status"] == "reconfirmed":
        current_status = "continuation result recorded"
        effect = "The same contour is closed honestly; the next step can move on with reconfirmed truth."
        next_attention = result.get("summary_ru") or "Advance to the next observation objective when ready."
    elif route_role == "official":
        current_status = "official route active"
        effect = "F1 should be read as a route-transit contour, not as a station routine."
        next_attention = "Keep route truth and objective timeline aligned while transit is active."
    elif route_role == "deviation":
        current_status = "deviation route active"
        effect = "Current actions are shaped by a deviation contour and may unlock different consequences."
        next_attention = "Track follow-up facts closely; deviation changes what safe continuation means."
    elif scene_profile == "docked":
        current_status = "station reference active"
        effect = "Navigation exists, but docking geometry is the dominant action gate."
        next_attention = "Confirm undock intent before treating navigation as the primary contour."
    elif scene_profile == "orbital_hold":
        current_status = "orbital hold truth limited"
        effect = "This contour stays honest as an upstream runtime gap and should not drive new deep-screen logic yet."
        next_attention = "Do not overread orbital-hold semantics until runtime truth is upgraded upstream."
    else:
        current_status = "free-flight reference"
        effect = "Navigation is currently advisory and does not add a separate route gate."
        next_attention = "Watch confidence and heading if the contour shifts into transit."
    summary_parts = [_summary_text(subsystem)]
    if route_role:
        summary_parts.append(f"route role={route_role}")
    if follow_up is not None and follow_up.get("summary_ru"):
        summary_parts.append(follow_up["summary_ru"])
    if result is not None and result.get("summary_ru"):
        summary_parts.append(result["summary_ru"])
    return _make_card(
        "navigation",
        status=status,
        current_status=current_status,
        summary=_join_summary(summary_parts),
        operational_effect=effect,
        next_attention=next_attention,
        quick_hint="F1 shows the live scene; F6 keeps the objective/event timeline.",
    )


def _build_sensors_card(
    hardware_model: HardwareViewModel | None,
    *,
    objective: dict[str, Any],
    radar_tracks: dict[str, dict[str, Any]],
) -> SystemCard:
    subsystem = _subsystem(hardware_model, "sensors")
    status = _status_of(subsystem)
    result = _observation_result_contract(objective)
    track_count = len(radar_tracks)
    target_designator = str(objective.get("target_designator") or "").strip()
    objective_track_id = str(objective.get("track_id") or "").strip()
    target_track = radar_tracks.get(objective_track_id) if objective_track_id else None
    target_label = str((target_track or {}).get("track_label") or objective.get("track_label") or "").strip()
    if result is not None:
        current_status = "continuation result visible"
        effect = (
            "Observation truth already changed the contour, so sensors now support "
            "confirmation rather than discovery."
        )
        next_attention = (
            result.get("summary_ru") or "Carry the recorded observation result into the next operator step."
        )
    elif target_designator and target_track is not None:
        current_status = "observation target live"
        effect = "Sensor picture is actively supporting the current observation contour."
        next_attention = f"Keep {target_label or target_designator} in view while the contour is active."
    elif target_designator and objective_track_id:
        status = _merge_status(status, ViewStatus.WARN)
        current_status = "target reacquire needed"
        effect = "Observation flow depends on recovering the target in live radar truth."
        next_attention = f"Reacquire {target_designator} before assuming the contour is still valid."
    elif status in {ViewStatus.WARN, ViewStatus.CRIT}:
        current_status = "sensor confidence reduced"
        effect = "Observation truth is degraded; identifications and route judgments need extra caution."
        next_attention = "Watch critical sensor status before leaning on observation-heavy actions."
    elif track_count > 0:
        current_status = "radar picture live"
        effect = "Live contacts are available and can inform the next operator decision."
        next_attention = f"{track_count} live track(s) available for scene drill-down."
    elif status is ViewStatus.NO_DATA:
        current_status = "truth incomplete"
        effect = "No honest sensor picture is available yet, so this card should remain informationally conservative."
        next_attention = "Wait for sensor or radar truth before treating observation as grounded."
    else:
        current_status = "sensor picture available"
        effect = "No current contact is shaping the contour, but the sensor stack is not blocking operations."
        next_attention = "Use F1 when a track or target becomes relevant."
    summary_parts = [_summary_text(subsystem)]
    sensors_evidence = _sensors_evidence_line(subsystem)
    if sensors_evidence:
        summary_parts.append(sensors_evidence)
    if track_count:
        summary_parts.append(f"tracks {track_count}")
    if target_label:
        summary_parts.append(f"target {target_label}")
    elif target_designator:
        summary_parts.append(f"target {target_designator}")
    return _make_card(
        "sensors",
        status=status,
        current_status=current_status,
        summary=_join_summary(summary_parts),
        operational_effect=effect,
        next_attention=next_attention,
        quick_hint="F1 keeps the radar scene; F3 is for incidents, not for raw sensor dumps.",
    )


def _build_comms_card(
    hardware_model: HardwareViewModel | None,
    *,
    scene_profile: str,
) -> SystemCard:
    subsystem = _subsystem(hardware_model, "comms")
    status = _status_of(subsystem)
    plane_enabled = _field_text(subsystem, "comms.plane_enabled")
    age_s = _field_text(subsystem, "comms.age_s")
    if status is ViewStatus.CRIT or plane_enabled.lower() == "off":
        current_status = "link unavailable"
        effect = "Telemetry freshness and protocol confidence are compromised for the current loop."
        next_attention = "Restore the comms plane before relying on remote acknowledgements."
    elif status is ViewStatus.WARN:
        current_status = "link degraded"
        effect = "Commands and telemetry may still flow, but latency, loss, or stale data are shaping operator trust."
        next_attention = f"Watch freshness and loss; current age is {age_s}."
    elif status is ViewStatus.NO_DATA:
        current_status = "truth incomplete"
        effect = "Comms truth is not available yet, so protocol confidence should stay unresolved."
        next_attention = "Wait for live link telemetry before assuming the channel is available."
    else:
        current_status = "link available"
        effect = (
            "Station dialogue and acknowledgements remain available."
            if scene_profile == "docked"
            else "No immediate comms gate is limiting the current operator flow."
        )
        next_attention = "Monitor latency if the contour becomes time-sensitive."
    evidence_line = _comms_evidence_line(subsystem)
    summary = _summary_text(subsystem)
    if evidence_line:
        summary = f"{summary} | {evidence_line}"
    return _make_card(
        "comms",
        status=status,
        current_status=current_status,
        summary=summary,
        operational_effect=effect,
        next_attention=next_attention,
        quick_hint="If comms freshness slips, trust the live contour less aggressively.",
    )


def _build_safety_card(
    hardware_model: HardwareViewModel | None,
    *,
    safe_mode: dict[str, Any],
    active_incidents: int,
    incidents: list[dict[str, Any]],
) -> SystemCard:
    subsystem = _subsystem(hardware_model, "hull")
    status = _status_of(subsystem)
    safe_mode_active = safe_mode.get("active") is True
    safe_mode_reason = str(safe_mode.get("reason") or "").strip()
    crit_incidents = [inc for inc in incidents if str(inc.get("severity") or "").upper().startswith("C")]
    if safe_mode_active:
        status = _merge_status(status, ViewStatus.CRIT)
    elif crit_incidents:
        status = _merge_status(status, ViewStatus.CRIT)
    elif active_incidents > 0:
        status = _merge_status(status, ViewStatus.WARN)
    if safe_mode_active:
        current_status = "safe mode active"
        effect = "Q-Core safety authority overrides aggressive actions until the condition clears."
        next_attention = safe_mode_reason or "Clear the safe-mode reason before escalating actions."
    elif crit_incidents:
        latest = crit_incidents[0]
        current_status = "critical hazard open"
        effect = "Current contour should be incident-led; resolve or acknowledge the hazard before deeper system work."
        next_attention = _incident_text(latest)
    elif status in {ViewStatus.WARN, ViewStatus.CRIT}:
        current_status = "hazard watch"
        effect = "Integrity or incident state is already shaping what the operator should risk next."
        next_attention = "Keep hazard and integrity state ahead of route ambition."
    elif status is ViewStatus.NO_DATA:
        current_status = "truth incomplete"
        effect = "There is no honest integrity or hazard truth yet, so safety posture stays unresolved."
        next_attention = "Wait for hull or safety events before assuming a clear posture."
    else:
        current_status = "integrity stable"
        effect = "No safety authority override is currently constraining the operator loop."
        next_attention = "Maintain incident watch as the contour changes."
    summary_parts = [_summary_text(subsystem)]
    if safe_mode_reason:
        summary_parts.append(f"SAFE MODE: {safe_mode_reason}")
    if active_incidents:
        summary_parts.append(f"incidents {active_incidents}")
    return _make_card(
        "safety",
        status=status,
        current_status=current_status,
        summary=_join_summary(summary_parts),
        operational_effect=effect,
        next_attention=next_attention,
        quick_hint="F3 is the right place for incident drill-down after this overview flags the risk.",
    )


def _make_card(
    subsystem_id: str,
    *,
    status: ViewStatus,
    current_status: str,
    summary: str,
    operational_effect: str,
    next_attention: str,
    quick_hint: str | None = None,
) -> SystemCard:
    return SystemCard(
        subsystem_id=subsystem_id,
        title=F2_CARD_TITLES[subsystem_id],
        status=status,
        current_status=current_status,
        severity=_SEVERITY_LABELS[status],
        summary=summary,
        operational_effect=operational_effect,
        next_attention=next_attention,
        quick_hint=quick_hint,
        order_index=F2_CARD_ORDER.index(subsystem_id),
    )


def _status_rank(status: ViewStatus) -> int:
    return {ViewStatus.NO_DATA: 0, ViewStatus.OK: 1, ViewStatus.WARN: 2, ViewStatus.CRIT: 3}[status]


def _subsystem(hardware_model: HardwareViewModel | None, subsystem_id: str) -> SubsystemView | None:
    if hardware_model is None:
        return None
    return hardware_model.subsystems.get(subsystem_id)


def _status_of(subsystem: SubsystemView | None) -> ViewStatus:
    return subsystem.status if subsystem is not None else ViewStatus.NO_DATA


def _summary_text(subsystem: SubsystemView | None) -> str:
    if subsystem is None:
        return "Нет данных"
    summary = str(subsystem.summary or "").strip()
    return summary or "Нет данных"


def _field_map(subsystem: SubsystemView | None) -> dict[str, TelemetryField]:
    if subsystem is None:
        return {}
    return {field.key: field for field in subsystem.fields}


def _field_value(field: TelemetryField | None) -> str:
    if field is None:
        return "Нет данных"
    value = field.value
    if value is None:
        return "Нет данных"
    value_str = str(value).strip()
    if not value_str or value_str.lower() in {"n/a", "none"}:
        return "Нет данных"
    return f"{value_str} {field.unit}".strip()


def _field_evidence_suffix(field: TelemetryField | None) -> str:
    """Compact ADR-0014 evidence marker for a field (empty when trusted/fresh)."""
    if field is None:
        return ""
    if field.trust_status == "missing":
        return " [НЕТ ИСТОЧНИКА]"
    if field.freshness == "stale" or field.trust_status == "degraded":
        return " [УСТАРЕЛО]"
    return ""


def _power_evidence_line(subsystem: SubsystemView | None) -> str:
    """ADR-0014 evidence note for battery/supercap when not trusted (else empty)."""
    field_map = _field_map(subsystem)
    parts = []
    for label, key in (("батарея", "power.soc"), ("суперкап", "power.supercap_soc")):
        suffix = _field_evidence_suffix(field_map.get(key))
        if suffix:
            parts.append(f"{label}{suffix}")
    return ("Источник ЭСП: " + ", ".join(parts)) if parts else ""


def _sensors_evidence_line(subsystem: SubsystemView | None) -> str:
    """IF-SENSOR-TELEM §15 evidence — CONSUMED from emitted records (collector field
    sensors.if_sensor_telem.evidence). Always shown, including honest "нет данных" when the
    producer does not emit the block; never silently dropped."""
    field = _field_map(subsystem).get("sensors.if_sensor_telem.evidence")
    if field is None:
        return ""
    return f"датчики·доказательство: {field.value}"


def _pdu_evidence_line(subsystem: SubsystemView | None) -> str:
    """IF-PDU-POWER §11 evidence — CONSUMED from emitted records (collector field
    power.if_pdu_power.evidence). Always shown, including honest "нет данных" when the
    producer does not emit the block; never silently dropped."""
    field = _field_map(subsystem).get("power.if_pdu_power.evidence")
    if field is None:
        return ""
    return f"PDU·доказательство: {field.value}"


def _rcs_evidence_line(subsystem: SubsystemView | None) -> str:
    """IF-RCS-CMD §14 evidence — CONSUMED from the emitted record (collector field
    propulsion.if_rcs_cmd.evidence). Always shown, including honest "нет данных" when the
    producer does not emit the record; never silently dropped."""
    field = _field_map(subsystem).get("propulsion.if_rcs_cmd.evidence")
    if field is None:
        return ""
    return f"RCS·доказательство: {field.value}"


def _comms_evidence_line(subsystem: SubsystemView | None) -> str:
    """ADR-0014 / IF-COMMS-001 §16.7 evidence note for the comms channel.

    delivery reason_codes (canon §16.6) and freshness/missing are SEPARATE evidence
    dimensions (canon 05§17): a blocked/degraded channel shows its reason_code; only a
    truly stale link gets [УСТАРЕЛО]; an absent source gets [НЕТ ИСТОЧНИКА]. Quiet (empty)
    when the channel is online / trusted / fresh.
    """
    field = _field_map(subsystem).get("comms.link_state")
    if field is None:
        return ""
    marks: list[str] = []
    if field.trust_status == "missing":
        marks.append("[НЕТ ИСТОЧНИКА]")
    elif field.freshness == "stale":
        marks.append("[УСТАРЕЛО]")
    reasons = ",".join(field.reason_codes) if field.reason_codes else ""
    if not marks and not reasons:
        return ""
    line = "Источник связи: канал"
    if marks:
        line += " " + " ".join(marks)
    if reasons:
        line += f"; причина {reasons}"
    return line


def _field_text(subsystem: SubsystemView | None, key: str) -> str:
    return _field_value(_field_map(subsystem).get(key))


def _field_float(subsystem: SubsystemView | None, key: str) -> float | None:
    field = _field_map(subsystem).get(key)
    if field is None or field.value is None:
        return None
    try:
        return float(field.value)
    except (TypeError, ValueError):
        return None


def _merge_status(left: ViewStatus, right: ViewStatus) -> ViewStatus:
    return left if _status_rank(left) >= _status_rank(right) else right


def _resolve_scene_profile(telemetry: dict[str, Any], objective: dict[str, Any]) -> str:
    route_role = str(objective.get("route_role") or "").strip().lower()
    objective_status = str(objective.get("status") or "").strip().lower()
    procedure_name = str(objective.get("procedure_name") or "").strip().lower()
    docking_state = _pick_text(telemetry, ["docking", "state"]).strip().lower()
    docking_connected = _pick_bool(telemetry, ["docking", "connected"]) is True
    orbit_state = _pick_text(telemetry, ["orbit", "state"]).strip().lower()
    if route_role in {"official", "deviation"} or procedure_name in {
        "safe_pause_resume",
        "safe_pause_slow_resume",
        "hostile_rcs_intercept_burst",
    }:
        return "route_transit"
    if docking_connected or docking_state in {"docked", "capture", "approach", "charging", "undocking"}:
        return "docked"
    if orbit_state in {"hold", "orbital_hold", "orbit_hold", "stable_orbit"}:
        return "orbital_hold"
    if objective_status in {"prepared", "confirmed"} and procedure_name:
        return "route_transit"
    return "free_flight"


def _pick_text(source: dict[str, Any], path: list[str]) -> str:
    value: Any = source
    for segment in path:
        if not isinstance(value, dict):
            return ""
        value = value.get(segment)
    if value is None:
        return ""
    return str(value).strip()


def _pick_bool(source: dict[str, Any], path: list[str]) -> bool | None:
    value: Any = source
    for segment in path:
        if not isinstance(value, dict):
            return None
        value = value.get(segment)
    if isinstance(value, bool):
        return value
    return None


def _objective_follow_up_contract(objective: dict[str, Any]) -> dict[str, str] | None:
    if not objective:
        return None
    status = str(objective.get("follow_up_status") or "").strip().lower()
    if not status:
        return None
    return {
        "status": status,
        "summary_ru": str(objective.get("follow_up_summary_ru") or "").strip(),
        "allowed_when_ru": str(objective.get("follow_up_allowed_when_ru") or "").strip(),
    }


def _observation_result_contract(objective: dict[str, Any]) -> dict[str, str] | None:
    if not objective:
        return None
    status = str(objective.get("observation_result_status") or "").strip().lower()
    if not status:
        return None
    return {
        "status": status,
        "summary_ru": str(objective.get("observation_result_summary_ru") or "").strip(),
    }


def _join_summary(parts: list[str]) -> str:
    filtered = [part for part in parts if part and part != "Нет данных"]
    return " | ".join(filtered) if filtered else "Нет данных"


def _looks_enabled(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"on", "online", "active", "enabled", "вкл", "да"}


def _incident_text(incident: dict[str, Any]) -> str:
    incident_id = str(incident.get("id") or "incident").strip()
    description = str(incident.get("description") or incident.get("message") or "").strip()
    return f"{incident_id}: {description}" if description else incident_id


def _safe_mode_header_line(safe_mode: dict[str, Any] | None) -> str | None:
    if not isinstance(safe_mode, dict) or safe_mode.get("active") is not True:
        return None
    reason = str(safe_mode.get("reason") or "").strip()
    reason_text = f" ({reason})" if reason else ""
    return f"Safety authority: SAFE MODE active{reason_text}"


def _action_link(action: str, value: str) -> str:
    safe_value = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"[@click={action}('{safe_value}')]select/click[/]"


def _render_systems_mfd_status(
    body_vm: Any,
    body_physics_vm: Any,
    power_vm: Any,
    *,
    active_left_page: str,
    active_right_page: str,
) -> str:
    return (
        "ORION V / F2 SYSTEMS MFD | "
        f"LEFT={mfd_page_label('left', active_left_page)}:{normalize_mfd_page('left', active_left_page)} | "
        f"RIGHT={mfd_page_label('right', active_right_page)}:{normalize_mfd_page('right', active_right_page)} | "
        f"BODY={body_vm.seed_status} | modules={body_vm.attached_modules_count} | "
        f"selected={body_vm.selected_face_id} | "
        f"POWER({str(getattr(power_vm, 'source', None) or 'unknown')}) "
        f"SoC_bat={format_soc_bat(getattr(power_vm, 'battery_soc_pct', None))} "
        f"SoC_cap={format_soc_cap(getattr(power_vm, 'supercap_soc_pct', None))} | "
        f"PHYSICS={body_physics_vm.evidence_card_type} | runtime={body_physics_vm.runtime_conformance}"
    )


def _render_systems_left_mfd(
    body_vm: Any,
    *,
    telemetry: dict[str, Any],
    observation_objective: dict[str, Any] | None,
    radar_tracks: dict[str, dict[str, Any]],
    incidents: list[dict[str, Any]],
    safe_mode: dict[str, Any],
    active_left_page: str,
) -> str:
    return render_left_mfd_page(
        page=active_left_page,
        body_vm=body_vm,
        telemetry=telemetry,
        observation_objective=observation_objective,
        radar_tracks=radar_tracks,
        incidents=incidents,
        safe_mode=safe_mode,
    )


def _render_systems_right_mfd(
    cards: list[SystemCard],
    *,
    body_structure_vm: Any,
    body_physics_vm: Any,
    power_thermal_vm: Any,
    selected_subsystem: str | None,
    hardware_model: HardwareViewModel | None,
    active_right_page: str,
    radar_tracks: dict[str, dict[str, Any]],
    incidents: list[dict[str, Any]],
    safe_mode: dict[str, Any],
) -> str:
    page_to_subsystem = {
        "systems": "body_structure",
        "sensors": "sensors",
        "power": "power",
        "thermal": "power",
        "comms": "comms",
        "propulsion": "propulsion",
        "docking": "docking",
        "journal": "safety",
        "procedures": "safety",
    }
    normalized_page = normalize_mfd_page("right", active_right_page)
    subsystem_key = selected_subsystem or page_to_subsystem.get(normalized_page)
    selected_view = _subsystem(hardware_model, subsystem_key) if subsystem_key else None
    return render_right_mfd_page(
        page=normalized_page,
        cards=cards,
        body_structure_vm=body_structure_vm,
        body_physics_vm=body_physics_vm,
        power_thermal_vm=power_thermal_vm,
        selected_subsystem=selected_subsystem,
        radar_tracks=radar_tracks,
        incidents=incidents,
        safe_mode=safe_mode,
        inspector_lines=format_subsystem_inspector(selected_view),
    )


def _mfd_pct_text(value: int | float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value}%"


class OrionVSystemsScreen(Static):
    """Operator-first F2 systems overview powered by existing truth sources."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._hardware_model: HardwareViewModel | None = None
        self._selected_subsystem: str | None = None
        self._safe_mode: dict[str, Any] = {}
        self._telemetry: dict[str, Any] = {}
        self._observation_objective: dict[str, Any] | None = None
        self._active_incidents = 0
        self._incidents: list[dict[str, Any]] = []
        self._radar_tracks: dict[str, dict[str, Any]] = {}
        self._active_left_mfd_page = MFD_DEFAULT_LEFT_PAGE
        self._active_right_mfd_page = MFD_DEFAULT_RIGHT_PAGE

    DEFAULT_CSS = """
    OrionVSystemsScreen {
        height: 1fr;
        layout: vertical;
    }

    #orionv-systems-title {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }

    #orionv-systems-mfd-root {
        height: 1fr;
        layout: vertical;
    }

    #orionv-systems-mfd-status {
        height: auto;
        max-height: 5;
        border: round #4f747c;
        border-title-color: #7de3f2;
        background: #10181b;
        color: #dce4dc;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    #orionv-systems-mfd-main {
        height: 1fr;
        layout: horizontal;
    }

    #orionv-systems-mfd-left-buttons,
    #orionv-systems-mfd-right-buttons {
        width: 12;
        height: 1fr;
        layout: vertical;
        background: #070d10;
        padding: 0 1;
    }

    #orionv-systems-mfd-left-buttons { margin: 0 1 0 0; }
    #orionv-systems-mfd-right-buttons { margin: 0 0 0 1; }

    #orionv-systems-mfd-left-buttons Button,
    #orionv-systems-mfd-right-buttons Button {
        width: 10;
        min-width: 10;
        height: 1;
        min-height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: #0d1518;
        color: #aebabb;
        text-style: bold;
    }

    #orionv-systems-mfd-left-screen,
    #orionv-systems-mfd-right-screen {
        width: 1fr;
        height: 1fr;
        border: round #3a8294;
        border-title-color: #64c7d8;
        background: #0d1417;
        color: #d8ded8;
        padding: 0 1;
        margin: 0 1 0 0;
    }

    #orionv-systems-mfd-right-screen {
        border: round #5f8a4a;
        border-title-color: #8fbf78;
    }

    #orionv-systems-mfd-left-buttons Button.mfd-active,
    #orionv-systems-mfd-right-buttons Button.mfd-active {
        border: heavy #f2b84b;
        color: #f6e7b4;
    }

    #orionv-systems-mfd-softkeys {
        height: auto;
        border: round #617078;
        background: #0f1518;
        color: #d8ded8;
        padding: 0 1;
        margin: 1 0 0 0;
    }

    #orionv-systems-compat {
        display: none;
        height: 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="orionv-systems-title")
        with Container(id="orionv-systems-mfd-root"):
            yield Static("", id="orionv-systems-mfd-status")
            with Container(id="orionv-systems-mfd-main"):
                with Container(id="orionv-systems-mfd-left-buttons"):
                    for button in mfd_button_specs("left"):
                        yield Button(button.label, id=f"systems-{button.button_id}", compact=True)
                yield Static("", id="orionv-systems-mfd-left-screen")
                yield Static("", id="orionv-systems-mfd-right-screen")
                with Container(id="orionv-systems-mfd-right-buttons"):
                    for button in mfd_button_specs("right"):
                        yield Button(button.label, id=f"systems-{button.button_id}", compact=True)
            yield Static("", id="orionv-systems-mfd-softkeys")
        with Container(id="orionv-systems-compat"):
            yield Static("", id="orionv-systems-intro")
            yield Static("", id="orionv-systems-authority")
            yield BodyStructureTextualDashboard(id="orionv-body-structure-dashboard")
            yield BodyPhysicsPanel(get_body_physics_console_view_model(), id="orionv-body-physics-panel")
            yield PowerThermalTextualDashboard(id="orionv-power-thermal-dashboard")
            with VerticalScroll(id="orionv-system-card-stream"):
                pass
            yield Static("", id="orionv-systems-inspector")

    def on_mount(self) -> None:
        self._refresh_text()

    def set_state(
        self,
        *,
        hardware_model: HardwareViewModel | None,
        telemetry: dict[str, Any] | None = None,
        selected_subsystem: str | None = None,
        safe_mode: dict[str, Any] | None = None,
        observation_objective: dict[str, Any] | None = None,
        active_incidents: int = 0,
        incidents: list[dict[str, Any]] | None = None,
        radar_tracks: dict[str, dict[str, Any]] | None = None,
        active_left_mfd_page: str | None = None,
        active_right_mfd_page: str | None = None,
    ) -> None:
        self._hardware_model = hardware_model
        self._telemetry = dict(telemetry or {})
        if selected_subsystem is not None:
            self._selected_subsystem = selected_subsystem
        self._safe_mode = safe_mode or {}
        self._observation_objective = dict(observation_objective or {}) or None
        self._active_incidents = active_incidents
        self._incidents = list(incidents or [])
        self._radar_tracks = dict(radar_tracks or {})
        self._active_left_mfd_page = normalize_mfd_page("left", active_left_mfd_page or self._active_left_mfd_page)
        self._active_right_mfd_page = normalize_mfd_page("right", active_right_mfd_page or self._active_right_mfd_page)
        self._refresh_text()

    def _semantic_static_update(self, selector: str, text: str) -> None:
        semantic_update(
            self.query_one(selector, Static),
            text,
            domain=_mfd_visual_domain(selector),
        )

    def _set_mfd_button_classes(self) -> None:
        for spec in (*mfd_button_specs("left"), *mfd_button_specs("right")):
            selector = f"#systems-{spec.button_id}"
            try:
                button = self.query_one(selector, Button)
            except Exception:
                continue
            button.set_classes(
                mfd_button_class(
                    spec,
                    active_left=self._active_left_mfd_page,
                    active_right=self._active_right_mfd_page,
                )
            )

    def _refresh_text(self) -> None:
        cards = build_system_cards(
            self._hardware_model,
            telemetry=self._telemetry,
            safe_mode=self._safe_mode,
            observation_objective=self._observation_objective,
            active_incidents=self._active_incidents,
            incidents=self._incidents,
            radar_tracks=self._radar_tracks,
        )
        self._semantic_static_update("#orionv-systems-title", "[F2] Systems Overview")
        self._semantic_static_update(
            "#orionv-systems-intro",
            "Обзор оператора: состояние → влияние на действия → куда смотреть дальше\n"
            "Правда: hardware_view_model + телеметрия/цель/события — уже в ORION V",
        )
        self._semantic_static_update(
            "#orionv-systems-authority",
            _safe_mode_header_line(self._safe_mode) or "",
        )
        body_structure_vm = get_body_structure_console_view_model()
        self.query_one("#orionv-body-structure-dashboard", BodyStructureTextualDashboard).update_view_model(
            body_structure_vm
        )
        body_physics_vm = get_body_physics_console_view_model(body_structure_vm)
        self.query_one("#orionv-body-physics-panel", BodyPhysicsPanel).update_view_model(
            body_physics_vm
        )
        power_thermal_vm = build_power_thermal_console_view_model_from_telemetry(self._telemetry)
        self.query_one("#orionv-power-thermal-dashboard", PowerThermalTextualDashboard).update_view_model(
            power_thermal_vm
        )
        self._semantic_static_update(
            "#orionv-systems-mfd-status",
            _render_systems_mfd_status(
                body_structure_vm,
                body_physics_vm,
                power_thermal_vm,
                active_left_page=self._active_left_mfd_page,
                active_right_page=self._active_right_mfd_page,
            ),
        )
        self._semantic_static_update(
            "#orionv-systems-mfd-left-screen",
            _render_systems_left_mfd(
                body_structure_vm,
                telemetry=self._telemetry,
                observation_objective=self._observation_objective,
                radar_tracks=self._radar_tracks,
                incidents=self._incidents,
                safe_mode=self._safe_mode,
                active_left_page=self._active_left_mfd_page,
            ),
        )
        self._semantic_static_update(
            "#orionv-systems-mfd-right-screen",
            _render_systems_right_mfd(
                cards,
                body_structure_vm=body_structure_vm,
                body_physics_vm=body_physics_vm,
                power_thermal_vm=power_thermal_vm,
                selected_subsystem=self._selected_subsystem,
                hardware_model=self._hardware_model,
                active_right_page=self._active_right_mfd_page,
                radar_tracks=self._radar_tracks,
                incidents=self._incidents,
                safe_mode=self._safe_mode,
            ),
        )
        self._semantic_static_update("#orionv-systems-mfd-softkeys", softkey_bar(("F3 deep",)))
        self._set_mfd_button_classes()
        stream = self.query_one("#orionv-system-card-stream", VerticalScroll)
        stream.remove_children()
        stream.mount(
            *(
                SystemCardWidget(
                    card,
                    selected=self._selected_subsystem == card.subsystem_id,
                )
                for card in cards
            )
        )
        # Unified §19 evidence Inspector for the selected subsystem (one render contract).
        selected_view = (
            _subsystem(self._hardware_model, self._selected_subsystem)
            if self._selected_subsystem
            else None
        )
        self._semantic_static_update(
            "#orionv-systems-inspector",
            "\n".join(format_subsystem_inspector(selected_view)),
        )
