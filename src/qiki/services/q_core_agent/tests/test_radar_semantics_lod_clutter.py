from __future__ import annotations

import time

from qiki.services.q_core_agent.core.radar_backends import RadarPoint, RadarScene
from qiki.services.q_core_agent.core.radar_controls import RadarInputController
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.radar_render_policy import RadarRenderPolicy
from qiki.services.q_core_agent.core.radar_trail_store import RadarTrailStore
from qiki.services.q_core_agent.core.radar_view_state import RadarViewState
from qiki.services.q_core_agent.core.terminal_radar_renderer import render_terminal_screen


def _event(
    *,
    subsystem: str,
    event_type: str,
    payload: dict,
    reason: str,
    truth_state: str = "OK",
) -> dict:
    return {
        "event_id": f"evt-{subsystem}-{event_type}-{int(time.time() * 1000)}",
        "ts": time.time(),
        "subsystem": subsystem,
        "event_type": event_type,
        "payload": payload,
        "tick_id": None,
        "truth_state": truth_state,
        "reason": reason,
    }


def _ok_event(*, track_id: str = "t1", is_fallback: bool = False, truth_state: str = "OK") -> dict:
    return _event(
        subsystem="SENSORS",
        event_type="SENSOR_TRUST_VERDICT",
        payload={
            "ok": True,
            "reason": "OK",
            "is_fallback": is_fallback,
            "age_s": 0.2,
            "quality": 0.9,
            "data": {
                "tracks": [
                    {
                        "track_id": track_id,
                        "range_m": 7.0,
                        "vr_mps": 0.2,
                        "azimuth_deg": 20.0,
                        "elevation_deg": 5.0,
                        "age_s": 0.2,
                        "quality": 0.9,
                    }
                ]
            },
        },
        reason="OK",
        truth_state=truth_state,
    )


def _scene_points(count: int) -> RadarScene:
    return RadarScene(
        ok=True,
        reason="OK",
        truth_state="OK",
        is_fallback=False,
        points=[
            RadarPoint(
                x=float(i + 1),
                y=float(i + 1),
                z=0.0,
                vr_mps=0.1,
                metadata={"target_id": f"t{i}", "range_m": float(i + 1)},
            )
            for i in range(count)
        ],
    )


def test_lod_vectors_disabled_below_threshold() -> None:
    policy = RadarRenderPolicy()
    plan = policy.build_plan(view_state=RadarViewState(zoom=1.0), targets_count=1, frame_time_ms=0.0)
    assert plan.draw_vectors is False


def test_lod_vectors_enabled_at_threshold() -> None:
    policy = RadarRenderPolicy()
    plan = policy.build_plan(view_state=RadarViewState(zoom=1.2), targets_count=1, frame_time_ms=0.0)
    assert plan.draw_vectors is True


def test_lod_labels_disabled_below_threshold() -> None:
    policy = RadarRenderPolicy()
    plan = policy.build_plan(view_state=RadarViewState(zoom=1.4), targets_count=1, frame_time_ms=0.0)
    assert plan.draw_labels is False


def test_lod_labels_enabled_at_threshold() -> None:
    policy = RadarRenderPolicy()
    plan = policy.build_plan(view_state=RadarViewState(zoom=1.6), targets_count=1, frame_time_ms=0.0)
    assert plan.draw_labels is True


def test_clutter_by_target_count_disables_labels() -> None:
    policy = RadarRenderPolicy(clutter_targets_max=2)
    plan = policy.build_plan(view_state=RadarViewState(zoom=2.2), targets_count=5, frame_time_ms=0.0)
    assert plan.clutter_on is True
    assert plan.draw_labels is False


def test_clutter_by_frame_budget_scales_bitmap_down() -> None:
    policy = RadarRenderPolicy(frame_budget_ms=10.0, bitmap_scale=1.0)
    plan = policy.build_plan(view_state=RadarViewState(zoom=2.0), targets_count=1, frame_time_ms=15.0)
    assert plan.clutter_on is True
    assert plan.bitmap_scale < 1.0


def test_hud_shows_clutter_on() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    pipeline._last_frame_time_ms = 200.0
    screen = render_terminal_screen(
        [_ok_event()],
        pipeline=pipeline,
        view_state=RadarViewState(zoom=2.0, color_enabled=False),
    )
    assert "CLUTTER: ON" in screen


def test_inspector_shows_selected_track_details() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    controller = RadarInputController()
    state = controller.apply_key(RadarViewState(color_enabled=False), "i")
    state = RadarViewState(
        zoom=state.zoom,
        pan_x=state.pan_x,
        pan_y=state.pan_y,
        rot_yaw=state.rot_yaw,
        rot_pitch=state.rot_pitch,
        view=state.view,
        selected_target_id="t1",
        overlays_enabled=state.overlays_enabled,
        color_enabled=state.color_enabled,
        overlays=state.overlays,
        inspector=state.inspector,
    )
    screen = render_terminal_screen([_ok_event(track_id="t1")], pipeline=pipeline, view_state=state)
    assert "INSPECTOR: on id=t1" in screen
    assert "range=" in screen


def test_inspector_pinned_keeps_target() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    state = RadarViewState(selected_target_id="A", color_enabled=False)
    controller = RadarInputController()
    state = controller.apply_key(state, "i")
    state = controller.apply_key(state, "i")
    state = RadarViewState(
        zoom=state.zoom,
        pan_x=state.pan_x,
        pan_y=state.pan_y,
        rot_yaw=state.rot_yaw,
        rot_pitch=state.rot_pitch,
        view=state.view,
        selected_target_id="B",
        overlays_enabled=state.overlays_enabled,
        color_enabled=state.color_enabled,
        overlays=state.overlays,
        inspector=state.inspector,
    )
    screen = render_terminal_screen(
        [_ok_event(track_id="A"), _ok_event(track_id="B")],
        pipeline=pipeline,
        view_state=state,
    )
    assert "INSPECTOR: pinned id=A" in screen


def test_inspector_off_hides_details() -> None:
    screen = render_terminal_screen([_ok_event()], view_state=RadarViewState(inspector=RadarViewState().inspector))
    assert "INSPECTOR: off" in screen


def test_trail_length_capped() -> None:
    store = RadarTrailStore(max_len=3)
    scene = _scene_points(1)
    for i in range(5):
        point = scene.points[0]
        store.update_from_scene(
            RadarScene(
                ok=True,
                reason="OK",
                truth_state="OK",
                is_fallback=False,
                points=[RadarPoint(x=point.x + i, y=point.y, z=point.z, metadata=point.metadata)],
            )
        )
    assert len(store.get_trail("t0")) == 3


def test_trail_not_growing_on_no_data() -> None:
    store = RadarTrailStore(max_len=5)
    store.update_from_scene(_scene_points(1))
    before = len(store.get_trail("t0"))
    store.update_from_scene(RadarScene(ok=False, reason="NO_DATA", truth_state="NO_DATA", is_fallback=False, points=[]))
    after = len(store.get_trail("t0"))
    assert after == before


def test_clutter_disables_trails() -> None:
    policy = RadarRenderPolicy(clutter_targets_max=1)
    plan = policy.build_plan(view_state=RadarViewState(zoom=2.2), targets_count=3, frame_time_ms=0.0)
    assert plan.draw_trails is False


def test_truth_no_data_does_not_draw_target() -> None:
    screen = render_terminal_screen(
        [
            _event(
                subsystem="SENSORS",
                event_type="SENSOR_TRUST_VERDICT",
                payload={"ok": False, "reason": "NO_DATA", "is_fallback": False, "data": None},
                reason="NO_DATA",
                truth_state="NO_DATA",
            )
        ],
        view_state=RadarViewState(color_enabled=False),
    )
    assert "NO DATA: NO_DATA" in screen
    assert "→" not in screen
    assert "←" not in screen


def test_truth_fallback_marker_present() -> None:
    screen = render_terminal_screen(
        [_ok_event(is_fallback=True, truth_state="FALLBACK")],
        view_state=RadarViewState(color_enabled=False),
    )
    assert "FALLBACK" in screen


def test_backend_consistency_render_plan_same_for_unicode_and_bitmap() -> None:
    scene = _scene_points(4)
    view = RadarViewState(zoom=1.8)
    unicode_pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    bitmap_pipeline = RadarPipeline(RadarRenderConfig(renderer="auto", view="top", fps_max=10, color=False))
    plan_u = unicode_pipeline.build_render_plan(scene, view_state=view)
    plan_b = bitmap_pipeline.build_render_plan(scene, view_state=view)
    assert plan_u.lod_level == plan_b.lod_level
    assert plan_u.draw_labels == plan_b.draw_labels
    assert plan_u.draw_vectors == plan_b.draw_vectors
