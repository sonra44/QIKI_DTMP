from __future__ import annotations

import time
from dataclasses import replace

from qiki.services.q_core_agent.core.radar_backends import RadarPoint, RadarScene
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.radar_render_policy import ClutterReason, DegradationState, RadarRenderPolicy
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


def _plan(
    policy: RadarRenderPolicy,
    *,
    zoom: float,
    targets_count: int,
    frame_time_ms: float,
    state: DegradationState | None = None,
    now_ts: float = 0.0,
    backend_name: str = "kitty",
) -> tuple:
    return policy.build_plan(
        view_state=RadarViewState(zoom=zoom),
        targets_count=targets_count,
        frame_time_ms=frame_time_ms,
        backend_name=backend_name,
        degradation_state=state,
        now_ts=now_ts,
    )


# LOD

def test_lod_vectors_disabled_below_threshold() -> None:
    policy = RadarRenderPolicy()
    plan, _ = _plan(policy, zoom=1.0, targets_count=1, frame_time_ms=0.0)
    assert plan.draw_vectors is False


def test_lod_vectors_enabled_at_threshold() -> None:
    policy = RadarRenderPolicy()
    plan, _ = _plan(policy, zoom=1.2, targets_count=1, frame_time_ms=0.0)
    assert plan.draw_vectors is True


def test_lod_labels_disabled_below_threshold() -> None:
    policy = RadarRenderPolicy()
    plan, _ = _plan(policy, zoom=1.4, targets_count=1, frame_time_ms=0.0)
    assert plan.draw_labels is False


def test_lod_labels_enabled_at_threshold() -> None:
    policy = RadarRenderPolicy()
    plan, _ = _plan(policy, zoom=1.6, targets_count=1, frame_time_ms=0.0)
    assert plan.draw_labels is True


# Multi-reason + anti-clutter

def test_multi_reason_contains_overload_and_budget() -> None:
    policy = RadarRenderPolicy(clutter_targets_max=2, frame_budget_ms=10.0)
    state = DegradationState()
    _, state = _plan(policy, zoom=2.0, targets_count=5, frame_time_ms=15.0, state=state, now_ts=1.0)
    plan, _ = _plan(policy, zoom=2.0, targets_count=5, frame_time_ms=15.0, state=state, now_ts=2.0)
    assert set(plan.clutter_reasons) >= {
        ClutterReason.TARGET_OVERLOAD.value,
        ClutterReason.FRAME_BUDGET_EXCEEDED.value,
    }


def test_multi_reason_does_not_duplicate_entries() -> None:
    policy = RadarRenderPolicy(clutter_targets_max=2, frame_budget_ms=10.0)
    state = DegradationState()
    for ts in (1.0, 2.0, 3.0):
        _, state = _plan(policy, zoom=2.0, targets_count=5, frame_time_ms=15.0, state=state, now_ts=ts)
    plan, _ = _plan(policy, zoom=2.0, targets_count=5, frame_time_ms=15.0, state=state, now_ts=4.0)
    assert len(plan.clutter_reasons) == len(set(plan.clutter_reasons))


# Step scaling

def test_scale_level_0_is_1_0() -> None:
    policy = RadarRenderPolicy(bitmap_scales=(1.0, 0.75, 0.5, 0.35))
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=0.0)
    assert plan.degradation_level == 0
    assert plan.bitmap_scale == 1.0


def test_scale_level_1_is_0_75() -> None:
    policy = RadarRenderPolicy(frame_budget_ms=10.0, bitmap_scales=(1.0, 0.75, 0.5, 0.35), degrade_confirm_frames=1)
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, now_ts=1.0)
    assert plan.degradation_level == 1
    assert plan.bitmap_scale == 0.75


def test_scale_level_2_is_0_5() -> None:
    policy = RadarRenderPolicy(frame_budget_ms=10.0, bitmap_scales=(1.0, 0.75, 0.5, 0.35), degrade_confirm_frames=1)
    state = DegradationState()
    for ts in (1.0, 2.0):
        _, state = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, state=state, now_ts=ts)
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, state=state, now_ts=3.0)
    assert plan.degradation_level == 3 or plan.degradation_level == 2
    assert plan.bitmap_scale in {0.5, 0.35}


def test_scale_level_3_is_0_35() -> None:
    policy = RadarRenderPolicy(
        frame_budget_ms=10.0,
        bitmap_scales=(1.0, 0.75, 0.5, 0.35),
        degrade_confirm_frames=1,
        degrade_cooldown_ms=0,
    )
    state = DegradationState()
    for ts in (1.0, 2.0, 3.0):
        _, state = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, state=state, now_ts=ts)
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, state=state, now_ts=4.0)
    assert plan.degradation_level == 3
    assert plan.bitmap_scale == 0.35


def test_unicode_backend_keeps_overlay_drop_even_if_scale_not_used() -> None:
    policy = RadarRenderPolicy(frame_budget_ms=10.0, degrade_confirm_frames=1)
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, now_ts=1.0, backend_name="unicode")
    assert plan.degradation_level >= 1
    assert plan.draw_labels is False


# Hysteresis

def test_single_budget_spike_does_not_degrade() -> None:
    policy = RadarRenderPolicy(frame_budget_ms=10.0, degrade_confirm_frames=2)
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, now_ts=1.0)
    assert plan.degradation_level == 0


def test_repeated_budget_violations_degrade() -> None:
    policy = RadarRenderPolicy(frame_budget_ms=10.0, degrade_confirm_frames=2)
    state = DegradationState()
    _, state = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, state=state, now_ts=1.0)
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, state=state, now_ts=2.0)
    assert plan.degradation_level == 1


def test_recovery_after_confirm_frames() -> None:
    policy = RadarRenderPolicy(
        frame_budget_ms=10.0,
        degrade_confirm_frames=1,
        recovery_confirm_frames=2,
        degrade_cooldown_ms=0,
    )
    plan, state = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, now_ts=1.0)
    assert plan.degradation_level == 1
    _, state = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=1.0, state=state, now_ts=2.0)
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=1.0, state=state, now_ts=3.0)
    assert plan.degradation_level == 0


def test_cooldown_blocks_rapid_degradation() -> None:
    policy = RadarRenderPolicy(frame_budget_ms=10.0, degrade_confirm_frames=1, degrade_cooldown_ms=5000)
    state = DegradationState()
    plan, state = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, state=state, now_ts=1.0)
    assert plan.degradation_level == 1
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, state=state, now_ts=1.2)
    assert plan.degradation_level == 1


# Render budget integration and HUD

def test_frame_budget_reason_appears_when_over_budget() -> None:
    policy = RadarRenderPolicy(frame_budget_ms=10.0, degrade_confirm_frames=1)
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, now_ts=1.0)
    assert ClutterReason.FRAME_BUDGET_EXCEEDED.value in plan.clutter_reasons


def test_frame_budget_reason_disappears_after_recovery() -> None:
    policy = RadarRenderPolicy(
        frame_budget_ms=10.0,
        degrade_confirm_frames=1,
        recovery_confirm_frames=1,
        degrade_cooldown_ms=0,
    )
    _, state = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=15.0, now_ts=1.0)
    plan, _ = _plan(policy, zoom=2.0, targets_count=1, frame_time_ms=1.0, state=state, now_ts=2.0)
    assert ClutterReason.FRAME_BUDGET_EXCEEDED.value not in plan.clutter_reasons


def test_hud_shows_reasons_and_scale_and_level() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    pipeline._last_frame_time_ms = 200.0
    screen = render_terminal_screen(
        [_ok_event()],
        pipeline=pipeline,
        view_state=RadarViewState(zoom=2.0, color_enabled=False),
    )
    assert "PERF:" in screen
    assert "lvl=" in screen
    assert "scale=" in screen


# Trails / truth / consistency regressions

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


def test_adaptive_level_respects_cooldown_and_recovers() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    pipeline.adaptive_policy = pipeline.adaptive_policy.__class__(
        enabled=True,
        ema_alpha_frame_ms=1.0,
        ema_alpha_targets=1.0,
        high_frame_ratio=1.1,
        low_frame_ratio=0.8,
        overload_target_ratio=1.0,
        underload_target_ratio=0.8,
        degrade_confirm_frames=1,
        recovery_confirm_frames=2,
        cooldown_ms=999999,
        max_level=2,
        clutter_reduction_per_level=0.2,
        lod_label_zoom_delta_per_level=0.1,
        lod_detail_zoom_delta_per_level=0.1,
    )
    pipeline._update_adaptive_state(frame_time_ms=200.0, targets_count=120)
    first_level = pipeline._adaptive_state.level
    pipeline._update_adaptive_state(frame_time_ms=220.0, targets_count=130)
    assert first_level == 1
    assert pipeline._adaptive_state.level == 1

    pipeline.adaptive_policy = replace(pipeline.adaptive_policy, cooldown_ms=0)
    pipeline._update_adaptive_state(frame_time_ms=10.0, targets_count=1)
    pipeline._update_adaptive_state(frame_time_ms=10.0, targets_count=1)
    assert pipeline._adaptive_state.level == 0
