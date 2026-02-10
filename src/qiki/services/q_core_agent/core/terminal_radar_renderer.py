"""Terminal radar/HUD renderer driven by EventStore facts and radar backend pipeline."""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .radar_backends import RadarPoint, RadarScene
from .radar_pipeline import RadarPipeline
from .radar_view_state import RadarViewState

_ANSI_RESET = "\x1b[0m"
_ANSI_RED = "\x1b[31m"
_ANSI_YELLOW = "\x1b[33m"
_ANSI_GREEN = "\x1b[32m"
_ANSI_CYAN = "\x1b[36m"


@dataclass(frozen=True)
class _ViewModel:
    fsm_state: str = "N/A"
    safe_mode_reason: str = ""
    safe_exit_hits: int = 0
    safe_exit_required: int = 0
    docking_hits: int = 0
    docking_required: int = 0
    last_actuation_action: str = "N/A"
    last_actuation_status: str = "N/A"
    last_actuation_reason: str = ""
    sensor_ok: bool = False
    sensor_reason: str = "NO_DATA"
    sensor_truth_state: str = "NO_DATA"
    sensor_is_fallback: bool = False
    range_m: float | None = None
    vr_mps: float | None = None
    azimuth_deg: float | None = None
    elevation_deg: float | None = None
    age_s: float | None = None
    quality: float | None = None
    tracks: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def _as_event_dict(event: Any) -> dict[str, Any]:
    if isinstance(event, Mapping):
        return dict(event)
    payload = getattr(event, "payload", {})
    truth_state = getattr(event, "truth_state", "")
    truth_state_value = getattr(truth_state, "value", truth_state)
    return {
        "event_id": getattr(event, "event_id", ""),
        "ts": getattr(event, "ts", 0.0),
        "subsystem": getattr(event, "subsystem", ""),
        "event_type": getattr(event, "event_type", ""),
        "payload": payload if isinstance(payload, dict) else {},
        "truth_state": str(truth_state_value or ""),
        "reason": getattr(event, "reason", ""),
        "tick_id": getattr(event, "tick_id", None),
    }


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value))
    except Exception:
        return default


def _parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _parse_confirmation(trigger: str) -> tuple[int, int]:
    if not trigger.startswith("DOCKING_CONFIRMING_"):
        return 0, 0
    suffix = trigger.replace("DOCKING_CONFIRMING_", "", 1)
    if "_OF_" not in suffix:
        return 0, 0
    left, right = suffix.split("_OF_", 1)
    return _parse_int(left, 0), _parse_int(right, 0)


def _extract_tracks(sensor_data: dict[str, Any], view: _ViewModel) -> tuple[dict[str, Any], ...]:
    raw_tracks = sensor_data.get("tracks")
    tracks: list[dict[str, Any]] = []
    if isinstance(raw_tracks, list):
        for idx, item in enumerate(raw_tracks):
            if not isinstance(item, dict):
                continue
            range_m = _parse_float(item.get("range_m"))
            vr_mps = _parse_float(item.get("vr_mps"))
            if range_m is None or vr_mps is None:
                continue
            azimuth_deg = _parse_float(item.get("azimuth_deg", 0.0))
            elevation_deg = _parse_float(item.get("elevation_deg"))
            tracks.append(
                {
                    "track_id": str(item.get("track_id") or f"track-{idx}"),
                    "range_m": range_m,
                    "vr_mps": vr_mps,
                    "azimuth_deg": azimuth_deg if azimuth_deg is not None else 0.0,
                    "elevation_deg": elevation_deg,
                    "quality": _parse_float(item.get("quality")),
                    "age_s": _parse_float(item.get("age_s")),
                }
            )
    if tracks:
        return tuple(tracks)
    if view.range_m is not None and view.vr_mps is not None:
        return (
            {
                "track_id": "station-track-0",
                "range_m": view.range_m,
                "vr_mps": view.vr_mps,
                "azimuth_deg": view.azimuth_deg if view.azimuth_deg is not None else 0.0,
                "elevation_deg": view.elevation_deg,
                "quality": view.quality,
                "age_s": view.age_s,
            },
        )
    return ()


def _build_view(events: Sequence[Any]) -> _ViewModel:
    view = _ViewModel(docking_required=max(1, _parse_int(os.getenv("QIKI_DOCKING_CONFIRMATION_COUNT", "3"), 3)))
    for raw_event in events:
        event = _as_event_dict(raw_event)
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        event_type = str(event.get("event_type", ""))
        subsystem = str(event.get("subsystem", ""))
        reason = str(event.get("reason", ""))
        truth_state = str(event.get("truth_state", "")).upper()

        if subsystem == "FSM" and event_type == "FSM_TRANSITION":
            to_state = str(payload.get("to_state", "")) or view.fsm_state
            trigger = str(payload.get("trigger_event", ""))
            context = payload.get("context", {})
            if not isinstance(context, dict):
                context = {}
            docking_hits = _parse_int(context.get("docking_confirm_hits", view.docking_hits), view.docking_hits)
            safe_reason = str(context.get("safe_mode_reason", "")) or view.safe_mode_reason
            confirm_hit, confirm_total = _parse_confirmation(trigger)
            if confirm_total > 0:
                docking_hits = confirm_hit
            if trigger == "DOCKING_CONFIRMED":
                docking_hits = max(docking_hits, view.docking_required)
            view = _ViewModel(
                fsm_state=to_state,
                safe_mode_reason=safe_reason,
                safe_exit_hits=view.safe_exit_hits,
                safe_exit_required=view.safe_exit_required,
                docking_hits=docking_hits,
                docking_required=max(view.docking_required, confirm_total or view.docking_required),
                last_actuation_action=view.last_actuation_action,
                last_actuation_status=view.last_actuation_status,
                last_actuation_reason=view.last_actuation_reason,
                sensor_ok=view.sensor_ok,
                sensor_reason=view.sensor_reason,
                sensor_truth_state=view.sensor_truth_state,
                sensor_is_fallback=view.sensor_is_fallback,
                range_m=view.range_m,
                vr_mps=view.vr_mps,
                azimuth_deg=view.azimuth_deg,
                elevation_deg=view.elevation_deg,
                age_s=view.age_s,
                quality=view.quality,
                tracks=view.tracks,
            )
        elif subsystem == "SAFE_MODE" and event_type == "SAFE_MODE":
            safe_reason = str(payload.get("reason", reason))
            view = _ViewModel(
                fsm_state="SAFE_MODE" if payload.get("action") != "exit" else view.fsm_state,
                safe_mode_reason=safe_reason,
                safe_exit_hits=_parse_int(payload.get("exit_hits", view.safe_exit_hits), view.safe_exit_hits),
                safe_exit_required=_parse_int(payload.get("confirmation_count", view.safe_exit_required), view.safe_exit_required),
                docking_hits=view.docking_hits,
                docking_required=view.docking_required,
                last_actuation_action=view.last_actuation_action,
                last_actuation_status=view.last_actuation_status,
                last_actuation_reason=view.last_actuation_reason,
                sensor_ok=view.sensor_ok,
                sensor_reason=view.sensor_reason,
                sensor_truth_state=view.sensor_truth_state,
                sensor_is_fallback=view.sensor_is_fallback,
                range_m=view.range_m,
                vr_mps=view.vr_mps,
                azimuth_deg=view.azimuth_deg,
                elevation_deg=view.elevation_deg,
                age_s=view.age_s,
                quality=view.quality,
                tracks=view.tracks,
            )
        elif subsystem == "ACTUATORS" and event_type == "ACTUATION_RECEIPT":
            view = _ViewModel(
                fsm_state=view.fsm_state,
                safe_mode_reason=view.safe_mode_reason,
                safe_exit_hits=view.safe_exit_hits,
                safe_exit_required=view.safe_exit_required,
                docking_hits=view.docking_hits,
                docking_required=view.docking_required,
                last_actuation_action=str(payload.get("action", "N/A")),
                last_actuation_status=str(payload.get("status", "N/A")).upper(),
                last_actuation_reason=str(payload.get("reason", reason)),
                sensor_ok=view.sensor_ok,
                sensor_reason=view.sensor_reason,
                sensor_truth_state=view.sensor_truth_state,
                sensor_is_fallback=view.sensor_is_fallback,
                range_m=view.range_m,
                vr_mps=view.vr_mps,
                azimuth_deg=view.azimuth_deg,
                elevation_deg=view.elevation_deg,
                age_s=view.age_s,
                quality=view.quality,
                tracks=view.tracks,
            )
        elif subsystem == "SENSORS" and event_type == "SENSOR_TRUST_VERDICT":
            sensor_data = payload.get("data", {})
            if not isinstance(sensor_data, dict):
                sensor_data = {}
            candidate = _ViewModel(
                fsm_state=view.fsm_state,
                safe_mode_reason=view.safe_mode_reason,
                safe_exit_hits=view.safe_exit_hits,
                safe_exit_required=view.safe_exit_required,
                docking_hits=view.docking_hits,
                docking_required=view.docking_required,
                last_actuation_action=view.last_actuation_action,
                last_actuation_status=view.last_actuation_status,
                last_actuation_reason=view.last_actuation_reason,
                sensor_ok=bool(payload.get("ok", False)),
                sensor_reason=str(payload.get("reason", reason or "NO_DATA")).upper(),
                sensor_truth_state=truth_state or view.sensor_truth_state,
                sensor_is_fallback=bool(payload.get("is_fallback", False)),
                range_m=_parse_float(sensor_data.get("range_m", view.range_m)),
                vr_mps=_parse_float(sensor_data.get("vr_mps", view.vr_mps)),
                azimuth_deg=_parse_float(sensor_data.get("azimuth_deg", view.azimuth_deg)),
                elevation_deg=_parse_float(sensor_data.get("elevation_deg", view.elevation_deg)),
                age_s=_parse_float(payload.get("age_s", view.age_s)),
                quality=_parse_float(payload.get("quality", view.quality)),
                tracks=view.tracks,
            )
            view = _ViewModel(
                **{**candidate.__dict__, "tracks": _extract_tracks(sensor_data, candidate)},
            )
    return view


def _view_to_scene(view: _ViewModel) -> RadarScene:
    points: list[RadarPoint] = []
    if view.sensor_ok:
        for idx, track in enumerate(view.tracks):
            range_m = _parse_float(track.get("range_m"))
            vr_mps = _parse_float(track.get("vr_mps"))
            azimuth_deg = _parse_float(track.get("azimuth_deg", 0.0))
            if range_m is None or vr_mps is None:
                continue
            azimuth = math.radians(azimuth_deg if azimuth_deg is not None else 0.0)
            x = math.cos(azimuth) * range_m
            y = math.sin(azimuth) * range_m
            elevation_deg = _parse_float(track.get("elevation_deg"))
            if elevation_deg is not None:
                z = math.sin(math.radians(elevation_deg)) * range_m
            else:
                z = vr_mps * 5.0
            points.append(
                RadarPoint(
                    x=x,
                    y=y,
                    z=z,
                    vr_mps=vr_mps,
                    metadata={
                        "target_id": str(track.get("track_id", f"station-track-{idx}")),
                        "range_m": range_m,
                        "azimuth_deg": azimuth_deg,
                        "elevation_deg": elevation_deg,
                        "quality": _parse_float(track.get("quality")),
                        "age_s": _parse_float(track.get("age_s")),
                    },
                )
            )

    return RadarScene(
        ok=view.sensor_ok,
        reason=view.sensor_reason,
        truth_state=view.sensor_truth_state or "NO_DATA",
        is_fallback=view.sensor_is_fallback,
        points=points,
    )


def _colorize_truth(text: str, truth_state: str, *, color_enabled: bool) -> str:
    if not color_enabled:
        return text
    state = (truth_state or "").upper()
    if state == "OK":
        return f"{_ANSI_GREEN}{text}{_ANSI_RESET}"
    if state in {"NO_DATA", "STALE", "LOW_QUALITY"}:
        return f"{_ANSI_YELLOW}{text}{_ANSI_RESET}"
    if state in {"FALLBACK", "INVALID"}:
        return f"{_ANSI_RED}{text}{_ANSI_RESET}"
    return f"{_ANSI_CYAN}{text}{_ANSI_RESET}"


def _event_severity(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type", "")).upper()
    reason = str(event.get("reason", "")).upper()
    truth_state = str(event.get("truth_state", "")).upper()
    if event_type == "SAFE_MODE":
        return "SAFE"
    if truth_state in {"NO_DATA", "STALE", "LOW_QUALITY", "FALLBACK", "INVALID"}:
        return "WARN"
    if any(token in reason for token in ("FAIL", "TIMEOUT", "UNAVAILABLE", "INVALID", "REJECTED")):
        return "WARN"
    return "INFO"


def _format_event_log(events: Sequence[Any], max_items: int = 10, *, color_enabled: bool) -> list[str]:
    rows: list[str] = []
    for raw_event in list(events)[-max_items:]:
        event = _as_event_dict(raw_event)
        ts = _parse_float(event.get("ts"))
        ts_str = time.strftime("%H:%M:%S", time.localtime(ts)) if ts is not None and ts > 0 else "--:--:--"
        event_type = str(event.get("event_type", ""))
        reason = str(event.get("reason", ""))
        severity = _event_severity(event)
        marker = f"[{severity}]"
        row = f"[{ts_str}] {marker:<7} {event_type:<24} {reason}"
        if color_enabled:
            if severity == "WARN":
                row = f"{_ANSI_YELLOW}{row}{_ANSI_RESET}"
            elif severity == "SAFE":
                row = f"{_ANSI_RED}{row}{_ANSI_RESET}"
            else:
                row = f"{_ANSI_CYAN}{row}{_ANSI_RESET}"
        rows.append(row)
    return rows


def _overlay_legend(view_state: RadarViewState, disabled: Sequence[str]) -> str:
    symbols = [
        ("G", view_state.overlays.grid),
        ("B", view_state.overlays.range_rings),
        ("V", view_state.overlays.vectors),
        ("T", view_state.overlays.trails),
        ("L", view_state.overlays.labels),
    ]
    enabled = " ".join(symbol for symbol, on in symbols if on)
    if not enabled:
        enabled = "off"
    if disabled:
        return f"OVR: {enabled} dropped={','.join(disabled)}"
    return f"OVR: {enabled}"


def _build_inspector(scene: RadarScene, view_state: RadarViewState, view: _ViewModel) -> list[str]:
    if view_state.inspector.mode == "off":
        return ["INSPECTOR: off"]
    selected_id = view_state.selected_target_id
    if view_state.inspector.mode == "pinned" and view_state.inspector.pinned_target_id:
        selected_id = view_state.inspector.pinned_target_id
    if not selected_id:
        return [f"INSPECTOR: {view_state.inspector.mode} no selection"]
    for point in scene.points:
        point_id = str(point.metadata.get("target_id", ""))
        if point_id != selected_id:
            continue
        return [
            f"INSPECTOR: {view_state.inspector.mode} id={point_id}",
            f"  range={point.metadata.get('range_m', 'N/A')} vr={point.vr_mps:.3f}",
            f"  age={point.metadata.get('age_s', view.age_s)} quality={point.metadata.get('quality', view.quality)}",
            f"  trust={view.sensor_truth_state}/{view.sensor_reason}",
        ]
    return [f"INSPECTOR: {view_state.inspector.mode} id={selected_id} not found"]


def render_terminal_screen(
    events: Sequence[Any],
    *,
    event_log_size: int = 10,
    pipeline: RadarPipeline | None = None,
    view_state: RadarViewState | None = None,
) -> str:
    view = _build_view(events)
    scene = _view_to_scene(view)
    active_pipeline = pipeline or RadarPipeline()
    active_view_state = view_state or active_pipeline.view_state
    radar_output = active_pipeline.render_scene(scene, view_state=active_view_state)
    radar_lines = radar_output.lines
    stats = radar_output.stats
    plan = radar_output.plan
    log_lines = _format_event_log(
        events,
        max_items=event_log_size,
        color_enabled=active_pipeline.config.color and active_view_state.color_enabled,
    )

    safe_line = "SAFE: OFF"
    if view.fsm_state == "SAFE_MODE" or view.safe_mode_reason:
        safe_line = f"SAFE: ON reason={view.safe_mode_reason or 'UNKNOWN'} exit={view.safe_exit_hits}/{view.safe_exit_required or 0}"

    trust_line = f"TRUTH: {view.sensor_truth_state or 'NO_DATA'} reason={view.sensor_reason}"
    if view.sensor_is_fallback:
        trust_line += " FALLBACK"

    act_line = (
        f"LAST ACTUATION: {view.last_actuation_action} status={view.last_actuation_status}"
        f" reason={view.last_actuation_reason}"
    )

    header = [
        "=" * 72,
        (
            "MISSION CONTROL TERMINAL :: RADAR 3D + HUD (EventStore Facts) "
            f"backend={active_pipeline.active_backend_name} view={active_view_state.view}"
        ),
        "=" * 72,
    ]
    color_enabled = active_pipeline.config.color and active_view_state.color_enabled
    if not color_enabled:
        trust_line = f"{trust_line} [MONO]"
    trust_line = _colorize_truth(trust_line, view.sensor_truth_state, color_enabled=color_enabled)
    clutter_line = "CLUTTER: OFF"
    perf_line = "PERF: n/a"
    if stats is not None:
        perf_line = (
            f"PERF: {stats.frame_time_ms:.1f}ms (budget {active_pipeline.render_policy.frame_budget_ms:.0f}) "
            f"lvl={stats.degradation_level} scale={stats.bitmap_scale:.2f}"
        )
        if stats.clutter_on:
            reasons = ",".join(stats.clutter_reasons) if stats.clutter_reasons else "UNKNOWN"
            dropped = ",".join(stats.dropped_overlays) if stats.dropped_overlays else "-"
            clutter_line = f"CLUTTER: ON reasons=[{reasons}] dropped={dropped}"
    hud = [
        f"FSM: {view.fsm_state}",
        f"DOCKING CONFIRM: {view.docking_hits}/{max(1, view.docking_required)}",
        (
            f"VIEW: {active_view_state.view} zoom={active_view_state.zoom:.2f} pan=({active_view_state.pan_x:.2f},"
            f"{active_view_state.pan_y:.2f}) rot=({active_view_state.rot_yaw:.1f},{active_view_state.rot_pitch:.1f})"
        ),
        safe_line,
        act_line,
        trust_line,
        perf_line,
        clutter_line,
        _overlay_legend(active_view_state, plan.dropped_overlays if plan else ()),
    ]
    inspector_lines = _build_inspector(scene, active_view_state, view)
    radar_title = ["", "[ RADAR ]"]
    log_title = ["", "[ INSPECTOR ]", *inspector_lines, "", "[ EVENT LOG ]"]
    return "\n".join(header + radar_title + radar_lines + [""] + hud + log_title + log_lines)


def build_scene_from_events(events: Sequence[Any]) -> RadarScene:
    view = _build_view(events)
    return _view_to_scene(view)


def load_events_jsonl(path: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            row = line.strip()
            if not row:
                continue
            events.append(json.loads(row))
    return events
