"""Input controller for radar view state."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, replace

from .radar_backends import RadarScene
from .radar_backends.geometry import project_point
from .radar_view_state import RadarViewState

_VIEW_KEYS = {"1": "top", "2": "side", "3": "front", "4": "iso"}
_ZOOM_STEP = 0.15
_PAN_STEP = 0.2
_ROT_STEP = 7.5
_MIN_ZOOM = 0.25
_MAX_ZOOM = 6.0


@dataclass(frozen=True)
class RadarAction:
    kind: str
    value: str = ""
    x: float = 0.0
    y: float = 0.0
    dx: float = 0.0
    dy: float = 0.0


@dataclass(frozen=True)
class RadarMouseEvent:
    kind: str
    x: float = 0.0
    y: float = 0.0
    delta: float = 0.0
    button: str = "left"
    is_button_down: bool = False
    dx: float = 0.0
    dy: float = 0.0


class RadarInputController:
    def __init__(self, *, ack_s: float | None = None):
        if ack_s is None:
            ack_s = _env_float("SITUATION_ACK_S", 10.0)
        self.ack_s = max(0.0, float(ack_s))

    def handle_key(self, key: str) -> RadarAction:
        raw = (key or "").strip()
        token = raw.lower()
        if token in _VIEW_KEYS:
            return RadarAction(kind="SET_VIEW", value=_VIEW_KEYS[token])
        if token == "r":
            return RadarAction(kind="RESET_VIEW")
        if token == "o":
            return RadarAction(kind="TOGGLE_OVERLAYS")
        if token == "g":
            return RadarAction(kind="TOGGLE_GRID")
        if token == "b":
            return RadarAction(kind="TOGGLE_RANGE_RINGS")
        if token == "v":
            return RadarAction(kind="TOGGLE_VECTORS")
        if token == "t":
            return RadarAction(kind="TOGGLE_TRAILS")
        if token == "l":
            return RadarAction(kind="TOGGLE_LABELS")
        if token == "i":
            return RadarAction(kind="TOGGLE_INSPECTOR")
        if token == "c":
            return RadarAction(kind="TOGGLE_COLOR")
        if token == "q":
            return RadarAction(kind="QUIT")
        if raw == "A":
            return RadarAction(kind="ALERT_ACK")
        if raw == "F":
            return RadarAction(kind="ALERT_FOCUS")
        if token == "a" or raw == "]":
            return RadarAction(kind="ALERT_NEXT")
        if raw == "[":
            return RadarAction(kind="ALERT_PREV")
        if token == "s":
            return RadarAction(kind="TOGGLE_SITUATIONS")
        if token == "j":
            return RadarAction(kind="ALERT_NEXT")
        if token == "k":
            return RadarAction(kind="ALERT_PREV")
        if token in {"+", "="}:
            return RadarAction(kind="ZOOM_IN")
        if token in {"-", "_"}:
            return RadarAction(kind="ZOOM_OUT")
        if token in {"h", "left"}:
            return RadarAction(kind="PAN_LEFT")
        if token in {"l", "right"}:
            return RadarAction(kind="PAN_RIGHT")
        if token in {"up"}:
            return RadarAction(kind="PAN_UP")
        if token in {"down"}:
            return RadarAction(kind="PAN_DOWN")
        return RadarAction(kind="NOOP")

    def handle_mouse(self, event: RadarMouseEvent) -> RadarAction:
        if event.kind == "wheel":
            if event.delta > 0:
                return RadarAction(kind="ZOOM_IN")
            if event.delta < 0:
                return RadarAction(kind="ZOOM_OUT")
            return RadarAction(kind="NOOP")
        if event.kind == "click" and event.button == "left":
            return RadarAction(kind="SELECT_TARGET", x=event.x, y=event.y)
        if event.kind == "drag" and event.is_button_down:
            if abs(event.dx) < 1e-9 and abs(event.dy) < 1e-9:
                return RadarAction(kind="NOOP")
            if event.button == "left":
                return RadarAction(kind="DRAG", dx=event.dx, dy=event.dy)
        return RadarAction(kind="NOOP")

    def apply_action(self, state: RadarViewState, action: RadarAction, *, scene: RadarScene | None = None) -> RadarViewState:
        kind = action.kind
        if kind == "SET_VIEW":
            view = action.value if action.value in {"top", "side", "front", "iso"} else state.view
            return replace(state, view=view)
        if kind == "ZOOM_IN":
            return replace(state, zoom=min(_MAX_ZOOM, state.zoom + _ZOOM_STEP))
        if kind == "ZOOM_OUT":
            return replace(state, zoom=max(_MIN_ZOOM, state.zoom - _ZOOM_STEP))
        if kind == "PAN_LEFT":
            return replace(state, pan_x=state.pan_x - _PAN_STEP)
        if kind == "PAN_RIGHT":
            return replace(state, pan_x=state.pan_x + _PAN_STEP)
        if kind == "PAN_UP":
            return replace(state, pan_y=state.pan_y + _PAN_STEP)
        if kind == "PAN_DOWN":
            return replace(state, pan_y=state.pan_y - _PAN_STEP)
        if kind == "DRAG":
            if state.view == "iso":
                return replace(
                    state,
                    rot_yaw=state.rot_yaw + action.dx * _ROT_STEP,
                    rot_pitch=max(-85.0, min(85.0, state.rot_pitch + action.dy * _ROT_STEP)),
                )
            return replace(state, pan_x=state.pan_x + action.dx, pan_y=state.pan_y + action.dy)
        if kind == "SELECT_TARGET":
            return replace(state, selected_target_id=self._pick_target(scene, state, action.x, action.y))
        if kind == "TOGGLE_OVERLAYS":
            return replace(state, overlays_enabled=not state.overlays_enabled)
        if kind == "TOGGLE_GRID":
            return replace(state, overlays=replace(state.overlays, grid=not state.overlays.grid))
        if kind == "TOGGLE_RANGE_RINGS":
            return replace(state, overlays=replace(state.overlays, range_rings=not state.overlays.range_rings))
        if kind == "TOGGLE_VECTORS":
            return replace(state, overlays=replace(state.overlays, vectors=not state.overlays.vectors))
        if kind == "TOGGLE_TRAILS":
            return replace(state, overlays=replace(state.overlays, trails=not state.overlays.trails))
        if kind == "TOGGLE_LABELS":
            return replace(state, overlays=replace(state.overlays, labels=not state.overlays.labels))
        if kind == "TOGGLE_INSPECTOR":
            if state.inspector.mode == "off":
                return replace(state, inspector=replace(state.inspector, mode="on"))
            if state.inspector.mode == "on":
                return replace(
                    state,
                    inspector=replace(state.inspector, mode="pinned", pinned_target_id=state.selected_target_id),
                )
            return replace(state, inspector=replace(state.inspector, mode="off", pinned_target_id=None))
        if kind == "TOGGLE_COLOR":
            return replace(state, color_enabled=not state.color_enabled)
        if kind == "TOGGLE_SITUATIONS":
            return replace(
                state,
                alerts=replace(state.alerts, situations_enabled=not state.alerts.situations_enabled),
            )
        if kind == "ALERT_NEXT":
            return replace(state, alerts=replace(state.alerts, cursor=state.alerts.cursor + 1))
        if kind == "ALERT_PREV":
            return replace(state, alerts=replace(state.alerts, cursor=max(0, state.alerts.cursor - 1)))
        if kind == "ALERT_FOCUS":
            return replace(state, selected_target_id=state.alerts.focus_track_id or state.selected_target_id)
        if kind == "ALERT_ACK":
            situation_id = state.alerts.selected_situation_id
            if not situation_id:
                return state
            ack_map = dict(state.alerts.acked_until_by_situation)
            ack_map[situation_id] = time.time() + self.ack_s
            ordered = tuple(sorted(ack_map.items()))
            return replace(state, alerts=replace(state.alerts, acked_until_by_situation=ordered))
        if kind == "RESET_VIEW":
            return replace(
                state,
                zoom=1.0,
                pan_x=0.0,
                pan_y=0.0,
                rot_yaw=0.0,
                rot_pitch=0.0,
                selected_target_id=None,
                overlays_enabled=True,
                overlays=replace(
                    state.overlays,
                    grid=True,
                    range_rings=True,
                    vectors=True,
                    trails=True,
                    labels=True,
                    selection_highlight=True,
                ),
                inspector=replace(state.inspector, mode="off", pinned_target_id=None),
                alerts=replace(
                    state.alerts,
                    cursor=0,
                    selected_situation_id=None,
                    focus_track_id=None,
                    acked_until_by_situation=(),
                ),
            )
        return state

    def apply_key(self, state: RadarViewState, key: str, *, scene: RadarScene | None = None) -> RadarViewState:
        token = (key or "").strip()
        if token in _VIEW_KEYS:
            return replace(state, view=_VIEW_KEYS[token])
        return self.apply_action(state, self.handle_key(token), scene=scene)

    def _pick_target(self, scene: RadarScene | None, state: RadarViewState, x: float, y: float) -> str | None:
        if scene is None or not scene.points:
            return None
        best_id: str | None = None
        best_distance: float | None = None
        for index, point in enumerate(scene.points):
            projected = project_point(point, state.view, rot_yaw_deg=state.rot_yaw, rot_pitch_deg=state.rot_pitch)
            px = projected.u * state.zoom + state.pan_x
            py = projected.v * state.zoom + state.pan_y
            distance = ((px - x) ** 2) + ((py - y) ** 2)
            target_id = str(point.metadata.get("target_id") or point.metadata.get("id") or f"target-{index}")
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_id = target_id
        return best_id


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default
