"""Display-only render helpers for ORION V left/right MFD page content.

This module shapes existing ORION view-models, hardware cards, radar tracks,
incident rows and local seed projections into left/right MFD text panes.  It must
not validate commands, mutate runtime state, raise trust, claim telemetry
transport, or turn local seeds into flight truth.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from qiki.services.operator_console.orion_v.body_structure_face_map import format_face_map_lines
from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    format_power_accumulator_mfd_lines,
    format_soc_bat,
    format_soc_cap,
)
from qiki.services.operator_console.orion_v.mfd_layout import (
    clipped_lines,
    mfd_page_label,
    normalize_mfd_page,
    section_lines,
)

_UNKNOWN = "unknown"
_EMPTY = "-"


def _get(obj: Any, name: str, default: Any = "") -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _text(value: Any, default: str = _EMPTY) -> str:
    if value is None:
        return default
    value_s = str(value).strip()
    if value_s.lower() in {"", "none", "n/a", "null"}:
        return default
    return value_s


def _pct_text(value: Any) -> str:
    value_s = _text(value, _UNKNOWN)
    if value_s == _UNKNOWN or value_s == _EMPTY:
        return _UNKNOWN
    if value_s.endswith("%"):
        return value_s
    return f"{value_s}%"


def _card_by_id(cards: Sequence[Any], subsystem_id: str) -> Any | None:
    expected = str(subsystem_id or "").strip()
    for card in cards:
        if _text(_get(card, "subsystem_id"), "") == expected:
            return card
    return None


def _card_lines(card: Any | None, *, title: str) -> list[str]:
    if card is None:
        return [title, "status: missing", "summary: no subsystem card available"]
    return [
        title,
        f"status: {_text(_get(card, 'current_status'))} [{_text(_get(card, 'severity'))}]",
        f"summary: {_text(_get(card, 'summary'))}",
        f"effect: {_text(_get(card, 'operational_effect'))}",
        f"next: {_text(_get(card, 'next_attention'))}",
    ]


def _incident_lines(incidents: Sequence[Mapping[str, Any]], *, limit: int = 5) -> list[str]:
    if not incidents:
        return ["no active incident rows in this view"]
    rows: list[str] = []
    for incident in incidents[:limit]:
        inc_id = _text(incident.get("id") or incident.get("incident_id"), "incident")
        severity = _text(incident.get("severity"), _UNKNOWN)
        message = _text(
            incident.get("description") or incident.get("message") or incident.get("summary"),
            _EMPTY,
        )
        rows.append(f"- {inc_id} [{severity}] {message}")
    if len(incidents) > limit:
        rows.append(f"+ {len(incidents) - limit} more incident(s): open F8/F3 detail")
    return rows


def _radar_track_lines(
    radar_tracks: Mapping[str, Mapping[str, Any]],
    *,
    limit: int = 6,
) -> list[str]:
    if not radar_tracks:
        return ["no live radar tracks in current state"]
    rows: list[str] = []
    for index, (track_id, track) in enumerate(radar_tracks.items(), start=1):
        if index > limit:
            rows.append(f"+ {len(radar_tracks) - limit} more track(s): open detail")
            break
        label = _text(track.get("track_label") or track.get("label") or track_id, track_id)
        range_m = _text(track.get("range_m") or track.get("range") or track.get("distance_m"), _UNKNOWN)
        bearing = _text(track.get("bearing_deg") or track.get("bearing"), _UNKNOWN)
        quality = _text(track.get("quality") or track.get("confidence"), _UNKNOWN)
        age = _text(track.get("age_s") or track.get("age"), _UNKNOWN)
        rows.append(f"#{index} {label} | range={range_m} | bearing={bearing} | q={quality} | age={age}")
    return rows


def _objective_lines(objective: Mapping[str, Any] | None) -> list[str]:
    if not objective:
        return ["no active observation objective"]
    target = _text(
        objective.get("target_designator") or objective.get("track_label") or objective.get("track_id"),
        "no target",
    )
    role = _text(
        objective.get("route_role") or objective.get("profile") or objective.get("objective_type"),
        "objective",
    )
    status = _text(objective.get("status") or objective.get("state"), _UNKNOWN)
    summary = _text(objective.get("summary_ru") or objective.get("summary") or objective.get("description"), _EMPTY)
    rows = [f"target: {target}", f"role: {role}", f"status: {status}", f"summary: {summary}"]
    follow_up = objective.get("follow_up")
    if isinstance(follow_up, Mapping):
        rows.append(f"follow_up: {_text(follow_up.get('summary_ru') or follow_up.get('summary'))}")
    result = objective.get("result")
    if isinstance(result, Mapping):
        rows.append(f"result: {_text(result.get('summary_ru') or result.get('summary'))}")
    return rows


def _safe_lines(safe_mode: Mapping[str, Any] | None) -> list[str]:
    if not safe_mode:
        return ["SAFE: no active safe-mode payload"]
    active = safe_mode.get("active") is True
    reason = _text(safe_mode.get("reason"), _EMPTY)
    state = "active" if active else "inactive"
    return [f"SAFE: {state}", f"reason: {reason}"]


def _safe_power_summary(power_thermal_vm: Any) -> str:
    return (
        f"POWER({_text(_get(power_thermal_vm, 'source'), _UNKNOWN)}) "
        f"SoC_bat={format_soc_bat(_get(power_thermal_vm, 'battery_soc_pct'))} "
        f"SoC_cap={format_soc_cap(_get(power_thermal_vm, 'supercap_soc_pct'))} "
        f"bus={_text(_get(power_thermal_vm, 'bus_state'), _UNKNOWN)} "
        f"peak={_text(_get(power_thermal_vm, 'peak_readiness'), _UNKNOWN)}"
    )


def _face_map_lines(body_vm: Any) -> list[str]:
    rows = ["Face Map", "source: body_structure_view_model / attach seed"]
    rows.extend(format_face_map_lines(_get(body_vm, "faces", ())))
    rows.extend(
        [
            "",
            "Selected face",
            f"face_id: {_text(_get(body_vm, 'selected_face_id'))}",
            f"role: {_text(_get(body_vm, 'selected_face_role'))}",
            f"occupancy: {_text(_get(body_vm, 'selected_face_occupancy'))}",
            f"module: {_text(_get(body_vm, 'selected_face_module_id'))}",
            "",
            "Boundary: F00-F11 skeleton != calculated CAD geometry",
        ]
    )
    return rows


def render_left_mfd_page(
    *,
    page: str | None,
    body_vm: Any,
    telemetry: Mapping[str, Any] | None = None,
    observation_objective: Mapping[str, Any] | None = None,
    radar_tracks: Mapping[str, Mapping[str, Any]] | None = None,
    incidents: Sequence[Mapping[str, Any]] | None = None,
    safe_mode: Mapping[str, Any] | None = None,
) -> str:
    """Render a left MFD page with page-specific source-backed content."""
    selected = normalize_mfd_page("left", page)
    label = mfd_page_label("left", selected)
    tracks = dict(radar_tracks or {})
    objective = dict(observation_objective or {}) if observation_objective else None
    incidents_seq = list(incidents or [])
    telemetry_map = dict(telemetry or {})
    header = [
        f"LEFT MFD / {label}",
        f"page: {selected} | read-only projection; no runtime mutation",
    ]

    if selected == "radar":
        sections = [section_lines("Radar picture", _radar_track_lines(tracks), limit=9)]
    elif selected == "nav":
        nav_rows = [
            f"scene_profile: {_text(telemetry_map.get('scene_profile'))}",
            f"route_role: {_text((objective or {}).get('route_role'))}",
            *_objective_lines(objective),
        ]
        sections = [section_lines("Navigation / Route", nav_rows, limit=12)]
    elif selected == "target":
        target_rows = [
            *_objective_lines(objective),
            "",
            "Radar correlation",
            *_radar_track_lines(tracks, limit=4),
        ]
        sections = [section_lines("Target / Objective", target_rows, limit=14)]
    elif selected == "sector":
        sector_rows = [*_safe_lines(safe_mode), "", "Incidents", *_incident_lines(incidents_seq)]
        sections = [section_lines("Sector / Context", sector_rows, limit=14)]
    elif selected == "mission":
        mission_rows = [
            *_objective_lines(objective),
            "",
            "Body seed",
            f"modules: {_text(_get(body_vm, 'attached_modules_count'))}",
            f"last_decision: {_text(_get(body_vm, 'last_decision'))}",
            f"evidence: {_text(_get(body_vm, 'evidence_card_type'))}",
        ]
        sections = [section_lines("Mission / Procedure", mission_rows, limit=14)]
    else:
        sections = [section_lines("Left MFD", ["page routed; data missing"], limit=8)]

    rows = list(header)
    for section in sections:
        rows.append("")
        rows.extend(section)
    return "\n".join(clipped_lines(rows, limit=34))


def render_right_mfd_page(
    *,
    page: str | None,
    cards: Sequence[Any],
    body_structure_vm: Any,
    body_physics_vm: Any,
    power_thermal_vm: Any,
    selected_subsystem: str | None = None,
    radar_tracks: Mapping[str, Mapping[str, Any]] | None = None,
    incidents: Sequence[Mapping[str, Any]] | None = None,
    safe_mode: Mapping[str, Any] | None = None,
    inspector_lines: Sequence[str] | None = None,
) -> str:
    """Render a right MFD page with concrete page content instead of placeholders."""
    selected = normalize_mfd_page("right", page)
    label = mfd_page_label("right", selected)
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
    subsystem_key = selected_subsystem or page_to_subsystem.get(selected)
    header = [
        f"RIGHT MFD / {label}",
        f"page: {selected} | evidence station: read-only projection, not source of truth",
    ]

    if selected == "systems":
        rows = [
            *_face_map_lines(body_structure_vm),
            "",
            "Body Structure",
            f"decision: {_text(_get(body_structure_vm, 'last_decision'))}",
            f"module: {_text(_get(body_structure_vm, 'module_id'))}",
            f"mount: {_text(_get(body_structure_vm, 'mount_point'))}",
            f"passport: {_text(_get(body_structure_vm, 'passport_status'))}",
            f"runtime_ready: {_text(_get(body_structure_vm, 'runtime_ready'))}",
            f"capability: {_text(_get(body_structure_vm, 'capability_status'))}",
            "",
            "Physical Consequence",
            f"card: {_text(_get(body_physics_vm, 'evidence_card_type'))}",
            f"mass: {_text(_get(body_physics_vm, 'mass_state'))}",
            f"CoM: {_text(_get(body_physics_vm, 'com_delta_class'))}",
            f"inertia: {_text(_get(body_physics_vm, 'inertia_class'))}",
            f"Thrust Map: {_text(_get(body_physics_vm, 'thrust_map_status'))}",
            f"Torque Map: {_text(_get(body_physics_vm, 'torque_map_status'))}",
        ]
        sections = [section_lines("Systems / Body", rows, limit=24)]
    elif selected == "sensors":
        rows = [
            *_card_lines(_card_by_id(cards, "sensors"), title="Sensors card"),
            "",
            "Radar tracks",
            *_radar_track_lines(dict(radar_tracks or {})),
        ]
        sections = [section_lines("Sensor Trust / Radar", rows, limit=18)]
    elif selected == "power":
        rows = [
            _safe_power_summary(power_thermal_vm),
            "PDU_boundary: target-only; no full PDU runtime in this patch",
            "",
            *format_power_accumulator_mfd_lines(power_thermal_vm),
        ]
        power_limit = 16 if inspector_lines else 30
        sections = [section_lines("Power / Accumulator", rows, limit=power_limit)]
    elif selected == "thermal":
        nodes = list(_get(power_thermal_vm, "thermal_nodes", ()) or ())
        rows = [f"thermal_status: {_text(_get(power_thermal_vm, 'thermal_status'), _UNKNOWN)}"]
        for node in nodes:
            blocked = ", ".join(_get(node, "blocked_commands", ()) or ()) or "none"
            rows.append(
                f"{_text(_get(node, 'node_id'))}: {_text(_get(node, 'thermal_class'))} | "
                f"temp={_text(_get(node, 'temperature_c'), _UNKNOWN)} | blocked={blocked}"
            )
        rows.append(f"runtime: {_text(_get(power_thermal_vm, 'runtime_conformance'), _UNKNOWN)}")
        sections = [section_lines("Thermal Nodes", rows, limit=16)]
    elif selected == "comms":
        rows = [
            *_card_lines(_card_by_id(cards, "comms"), title="Comms card"),
            "",
            "Boundary: no NBL wideband or telemetry transport claim is made by this page.",
        ]
        sections = [section_lines("Comms / Link", rows, limit=14)]
    elif selected == "propulsion":
        rows = [
            *_card_lines(_card_by_id(cards, "propulsion"), title="Propulsion card"),
            "",
            "Thrust Map: TBD / calculation-required",
            "Torque Map: TBD / calculation-required",
            "No RCS physics or maneuver authority is claimed by this MFD page.",
        ]
        sections = [section_lines("Propulsion / Motion", rows, limit=16)]
    elif selected == "docking":
        rows = [
            *_card_lines(_card_by_id(cards, "docking"), title="Docking card"),
            "",
            "Bayonet bridge requires hard lock, electrical safety, handshake and passport validation.",
            "This MFD page does not activate bridge or detach workflow.",
        ]
        sections = [section_lines("Docking / Bayonet", rows, limit=16)]
    elif selected == "journal":
        rows = [
            *_card_lines(_card_by_id(cards, "safety"), title="Safety / incident card"),
            "",
            "Incidents",
            *_incident_lines(list(incidents or ())),
            "",
            "Full audit/evidence details remain on F8.",
        ]
        sections = [section_lines("Journal / Audit Glance", rows, limit=18)]
    elif selected == "procedures":
        rows = [
            *_safe_lines(safe_mode),
            "",
            "Command lifecycle",
            "request → validation → allowed/rejected → publish → ACK → effect_confirmation → audit",
            "No command executes from this MFD text pane.",
        ]
        sections = [section_lines("Procedures / Command Gate", rows, limit=14)]
    else:
        sections = [section_lines("Right MFD", ["page routed; data missing"], limit=8)]

    selected_card = _card_by_id(cards, subsystem_key or "")
    card_already_in_page = {"systems", "sensors", "comms", "propulsion", "docking", "journal"}
    if selected_card is not None and selected not in card_already_in_page:
        sections.append(section_lines("Selected subsystem", _card_lines(selected_card, title="Card"), limit=8))
    if inspector_lines:
        sections.append(section_lines("Inspector", inspector_lines, limit=8))

    rows = list(header)
    for section in sections:
        rows.append("")
        rows.extend(section)
    return "\n".join(clipped_lines(rows, limit=38))
