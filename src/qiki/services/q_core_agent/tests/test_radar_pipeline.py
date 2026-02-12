from __future__ import annotations

import time
from pathlib import Path

import pytest

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.plugin_manager import PluginManager, PluginSpec
from qiki.services.q_core_agent.core.radar_backends.kitty_backend import KittyRadarBackend
from qiki.services.q_core_agent.core.radar_backends.sixel_backend import SixelRadarBackend
from qiki.services.q_core_agent.core.radar_backends.base import RadarPoint, RadarScene
from qiki.services.q_core_agent.core.radar_fusion import FusionCluster, FusedTrack
from qiki.services.q_core_agent.core.radar_ingestion import SourceTrack
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.radar_plugins import register_builtin_radar_plugins
from qiki.services.q_core_agent.core.radar_situation_engine import RadarSituationEngine, SituationConfig
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


def _happy_events() -> list[dict]:
    return [
        _event(
            subsystem="FSM",
            event_type="FSM_TRANSITION",
            payload={
                "from_state": "DOCKING_APPROACH",
                "to_state": "DOCKING_APPROACH",
                "trigger_event": "DOCKING_CONFIRMING_1_OF_3",
                "context": {"docking_confirm_hits": 1, "safe_mode_reason": ""},
            },
            reason="DOCKING_CONFIRMING_1_OF_3",
        ),
        _event(
            subsystem="SENSORS",
            event_type="SENSOR_TRUST_VERDICT",
            payload={
                "ok": True,
                "reason": "OK",
                "is_fallback": False,
                "data": {"range_m": 8.0, "vr_mps": 0.2, "azimuth_deg": 45.0, "elevation_deg": 10.0},
            },
            reason="OK",
        ),
    ]


def test_forced_unicode_backend_always_selected() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True))
    assert pipeline.active_backend_name == "unicode"


def test_auto_without_bitmap_support_falls_back_to_unicode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.radar_backends.kitty_backend.KittyRadarBackend.is_supported",
        lambda _self: False,
    )
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.radar_backends.sixel_backend.SixelRadarBackend.is_supported",
        lambda _self: False,
    )
    pipeline = RadarPipeline(RadarRenderConfig(renderer="auto", view="top", fps_max=10, color=True))
    assert pipeline.active_backend_name == "unicode"


def test_bitmap_backends_blocked_in_tmux_without_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TMUX", "1")
    monkeypatch.setenv("TERM", "xterm-kitty")
    monkeypatch.delenv("QIKI_ALLOW_TMUX_BITMAP", raising=False)
    monkeypatch.delenv("QIKI_FORCE_KITTY_SUPPORTED", raising=False)
    monkeypatch.delenv("QIKI_FORCE_SIXEL_SUPPORTED", raising=False)
    assert KittyRadarBackend().is_supported() is False
    assert SixelRadarBackend().is_supported() is False


def test_bitmap_backends_can_be_enabled_in_tmux_with_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TMUX", "1")
    monkeypatch.setenv("TERM", "xterm-kitty")
    monkeypatch.setenv("QIKI_ALLOW_TMUX_BITMAP", "1")
    monkeypatch.setenv("QIKI_ALLOW_SSH_BITMAP", "1")
    assert KittyRadarBackend().is_supported() is True


def test_forced_kitty_backend_unsupported_fails_fast() -> None:
    with pytest.raises(RuntimeError, match="RADAR_RENDERER=kitty requested"):
        RadarPipeline(RadarRenderConfig(renderer="kitty", view="top", fps_max=10, color=True))


def test_runtime_backend_error_switches_to_unicode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.radar_backends.kitty_backend.KittyRadarBackend.is_supported",
        lambda _self: True,
    )

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated render failure")

    monkeypatch.setattr(
        "qiki.services.q_core_agent.core.radar_backends.kitty_backend.KittyRadarBackend.render",
        _boom,
    )

    pipeline = RadarPipeline(RadarRenderConfig(renderer="auto", view="top", fps_max=10, color=True))
    output = pipeline.render_scene(
        RadarScene(ok=False, reason="NO_DATA", truth_state="NO_DATA", is_fallback=False, points=[])
    )
    assert output.backend == "unicode"
    assert output.used_runtime_fallback is True
    assert output.lines[0].startswith("[RADAR RUNTIME FALLBACK kitty->unicode")


def test_pipeline_boots_with_default_plugins_yaml_and_emits_lifecycle_events() -> None:
    store = EventStore(maxlen=200, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True),
        event_store=store,
    )
    assert pipeline.fusion_plugin is not None
    loaded = store.filter(subsystem="PLUGINS", event_type="PLUGIN_LOADED")
    assert loaded


def test_pipeline_can_swap_fusion_plugin_via_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _DummyFusionPlugin:
        config = type("Cfg", (), {"enabled": True, "min_support": 1, "max_age_s": 2.0})()

        def fuse(
            self,
            tracks_by_source: dict[str, list[SourceTrack]],
            *,
            now: float,
            truth_state: str,
            reason: str,
            is_fallback: bool,
        ) -> tuple[RadarScene, tuple[FusedTrack, ...], tuple[FusionCluster, ...]]:
            _ = tracks_by_source, now
            scene = RadarScene(
                ok=True,
                reason=reason,
                truth_state=truth_state,
                is_fallback=is_fallback,
                points=[RadarPoint(x=1.0, y=2.0, z=0.0, vr_mps=0.0, metadata={"target_id": "dummy"})],
            )
            return scene, (), ()

    def _register(manager: PluginManager) -> None:
        register_builtin_radar_plugins(manager)
        manager.register(
            PluginSpec(
                name="dummy.fusion",
                kind="fusion",
                version="1.0.0",
                provides=("fusion",),
                requires=("builtin.sensor_input",),
                factory=lambda _ctx, _params: _DummyFusionPlugin(),
            )
        )

    plugin_yaml = tmp_path / "plugins.yaml"
    plugin_yaml.write_text(
        """
schema_version: 1
profiles:
  swap:
    sensor_input:
      name: builtin.sensor_input
    fusion:
      name: dummy.fusion
    render_policy:
      name: builtin.render_policy_v3
    render_backend:
      name: builtin.render_backends
    situational_analysis:
      name: builtin.situational_v2
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("QIKI_PLUGINS_STRICT", "1")
    monkeypatch.setenv("QIKI_PLUGINS_PROFILE", "swap")
    monkeypatch.setenv("QIKI_PLUGINS_YAML", str(plugin_yaml))

    store = EventStore(maxlen=200, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True),
        event_store=store,
        register_plugins=_register,
    )
    output = pipeline.render_observations([], truth_state="OK", reason="OK")
    assert output.backend == "unicode"
    assert pipeline.fusion_plugin.__class__.__name__ == "_DummyFusionPlugin"
    loaded = store.filter(subsystem="PLUGINS", event_type="PLUGIN_LOADED")
    assert loaded


def test_pipeline_with_disabled_situational_plugin_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_PLUGINS_PROFILE", "no_situational")
    store = EventStore(maxlen=200, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True),
        event_store=store,
    )
    pipeline.render_scene(RadarScene(ok=True, reason="OK", truth_state="OK", is_fallback=False, points=[]))
    situation_events = store.filter(subsystem="SITUATION")
    assert not situation_events
    fallback_events = store.filter(subsystem="PLUGINS", event_type="PLUGIN_FALLBACK_USED")
    assert fallback_events


def test_no_data_screen_prints_no_data_without_target_markers() -> None:
    events = [
        _event(
            subsystem="SENSORS",
            event_type="SENSOR_TRUST_VERDICT",
            payload={"ok": False, "reason": "NO_DATA", "is_fallback": False, "data": None},
            reason="NO_DATA",
            truth_state="NO_DATA",
        )
    ]
    screen = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True)),
    )
    assert "NO DATA: NO_DATA" in screen
    assert "→" not in screen
    assert "←" not in screen


def test_fallback_sensor_marked_in_hud() -> None:
    events = [
        _event(
            subsystem="SENSORS",
            event_type="SENSOR_TRUST_VERDICT",
            payload={
                "ok": True,
                "reason": "OK",
                "is_fallback": True,
                "data": {"range_m": 4.0, "vr_mps": 0.1},
            },
            reason="OK",
            truth_state="FALLBACK",
        )
    ]
    screen = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True)),
    )
    assert "FALLBACK" in screen


def test_event_log_prints_recent_n_events() -> None:
    events = [
        _event(subsystem="FSM", event_type="FSM_TRANSITION", payload={}, reason="A"),
        _event(subsystem="ACTUATORS", event_type="ACTUATION_RECEIPT", payload={}, reason="B"),
        _event(subsystem="SENSORS", event_type="SENSOR_TRUST_VERDICT", payload={}, reason="C"),
    ]
    screen = render_terminal_screen(
        events,
        event_log_size=2,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True)),
    )
    assert "ACTUATION_RECEIPT" in screen
    assert "SENSOR_TRUST_VERDICT" in screen
    assert "FSM_TRANSITION" not in screen


def test_radar_view_changes_projection() -> None:
    events = _happy_events()
    top = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True)),
    )
    side = render_terminal_screen(
        events,
        pipeline=RadarPipeline(RadarRenderConfig(renderer="unicode", view="side", fps_max=10, color=True)),
    )
    assert "view=top" in top
    assert "view=side" in side
    assert top != side


def test_render_tick_telemetry_event_is_written() -> None:
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True),
        event_store=store,
    )
    pipeline.render_scene(RadarScene(ok=False, reason="NO_DATA", truth_state="NO_DATA", is_fallback=False, points=[]))
    ticks = store.filter(subsystem="RADAR", event_type="RADAR_RENDER_TICK")
    assert ticks
    payload = ticks[-1].payload
    expected_keys = (
        "frame_ms",
        "fps_cap",
        "targets_count",
        "lod_level",
        "degradation_level",
        "bitmap_scale",
        "clutter_reasons",
        "backend",
        "policy_profile",
        "policy_source",
        "adaptive_level",
        "effective_frame_budget_ms",
        "effective_clutter_max",
    )
    for key in expected_keys:
        assert key in payload


def test_render_tick_reflects_selected_policy_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_POLICY_PROFILE", "combat")
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True),
        event_store=store,
    )
    pipeline.render_scene(RadarScene(ok=True, reason="OK", truth_state="OK", is_fallback=False, points=[]))
    tick = store.filter(subsystem="RADAR", event_type="RADAR_RENDER_TICK")[-1]
    assert tick.payload["policy_profile"] == "combat"
    assert tick.payload["policy_source"] == "yaml"
    assert tick.payload["effective_frame_budget_ms"] == pytest.approx(60.0)


def test_render_tick_telemetry_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_TELEMETRY", "0")
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=True),
        event_store=store,
    )
    pipeline.render_scene(RadarScene(ok=True, reason="OK", truth_state="OK", is_fallback=False, points=[]))
    ticks = store.filter(subsystem="RADAR", event_type="RADAR_RENDER_TICK")
    assert not ticks


def test_alert_selection_order_is_severity_then_recency_then_id() -> None:
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=EventStore(),
    )
    pipeline.situation_engine = RadarSituationEngine(
        SituationConfig(
            enabled=True,
            cpa_warn_t=20.0,
            cpa_crit_t=8.0,
            cpa_crit_dist=150.0,
            closing_speed_warn=5.0,
                near_dist=300.0,
                near_recent_s=5.0,
                confirm_frames=1,
                cooldown_s=0.0,
                lost_contact_window_s=0.02,
                auto_resolve_after_lost_s=0.02,
            )
        )
    scene = RadarScene(
        ok=True,
        reason="OK",
        truth_state="OK",
        is_fallback=False,
        points=[
            RadarPoint(
                x=80.0,
                y=0.0,
                z=0.0,
                vr_mps=-14.0,
                metadata={"target_id": "critical", "object_type": "friend"},
            ),
            RadarPoint(
                x=100.0,
                y=5.0,
                z=0.0,
                vr_mps=-7.0,
                metadata={"target_id": "warn", "object_type": "friend"},
            ),
        ],
    )
    pipeline.render_scene(scene)
    assert pipeline.view_state.selected_target_id == "critical"
    assert pipeline.view_state.alerts.selected_situation_id is not None


def test_focus_moves_when_selected_situation_resolved() -> None:
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=EventStore(),
    )
    pipeline.situation_engine = RadarSituationEngine(
        SituationConfig(
            enabled=True,
            cpa_warn_t=20.0,
            cpa_crit_t=8.0,
            cpa_crit_dist=150.0,
            closing_speed_warn=5.0,
            near_dist=300.0,
            near_recent_s=5.0,
            confirm_frames=1,
            cooldown_s=0.0,
            lost_contact_window_s=0.02,
            auto_resolve_after_lost_s=0.02,
        )
    )
    critical_scene = RadarScene(
        ok=True,
        reason="OK",
        truth_state="OK",
        is_fallback=False,
        points=[
            RadarPoint(x=80.0, y=0.0, z=0.0, vr_mps=-14.0, metadata={"target_id": "critical", "object_type": "friend"}),
            RadarPoint(x=100.0, y=5.0, z=0.0, vr_mps=-7.0, metadata={"target_id": "warn", "object_type": "friend"}),
        ],
    )
    pipeline.render_scene(critical_scene)
    assert pipeline.view_state.selected_target_id == "critical"

    # Resolve critical by moving it far/safe; warn remains.
    warn_only_scene = RadarScene(
        ok=True,
        reason="OK",
        truth_state="OK",
        is_fallback=False,
        points=[
            RadarPoint(x=900.0, y=0.0, z=0.0, vr_mps=-1.0, metadata={"target_id": "critical", "object_type": "friend"}),
            RadarPoint(x=100.0, y=5.0, z=0.0, vr_mps=-7.0, metadata={"target_id": "warn", "object_type": "friend"}),
        ],
    )
    pipeline.render_scene(warn_only_scene)
    time.sleep(0.03)
    pipeline.render_scene(warn_only_scene)
    assert pipeline.view_state.selected_target_id == "warn"


def test_pipeline_loads_combat_profile_from_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_POLICY_PROFILE", "combat")
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    assert pipeline.render_policy.frame_budget_ms == pytest.approx(60.0)
    assert pipeline.render_policy.degrade_confirm_frames == 1
    assert pipeline.policy_profile == "combat"
    assert pipeline.policy_source == "yaml"


def test_pipeline_env_override_has_priority_over_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_POLICY_PROFILE", "combat")
    monkeypatch.setenv("RADAR_CLUTTER_TARGETS_MAX", "88")
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    assert pipeline.render_policy.clutter_targets_max == 88


def test_pipeline_non_strict_invalid_yaml_emits_policy_fallback_event(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    broken = tmp_path / "broken_policy.yaml"
    broken.write_text("schema_version: 99\n", encoding="utf-8")
    monkeypatch.setenv("RADAR_POLICY_YAML", str(broken))
    monkeypatch.setenv("RADAR_POLICY_STRICT", "0")
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=store,
    )
    assert pipeline.policy_source in {"default", "env"}
    events = store.filter(subsystem="RADAR", event_type="POLICY_FALLBACK")
    assert events
    assert "POLICY_FALLBACK" in events[-1].reason


def test_pipeline_strict_invalid_yaml_fails_fast(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    broken = tmp_path / "broken_policy.yaml"
    broken.write_text("schema_version: 99\n", encoding="utf-8")
    monkeypatch.setenv("RADAR_POLICY_YAML", str(broken))
    monkeypatch.setenv("RADAR_POLICY_STRICT", "1")
    with pytest.raises(RuntimeError, match="Failed to load radar policy v3"):
        RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))


def test_set_policy_profile_emits_change_event() -> None:
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=store,
    )
    ok, message = pipeline.set_policy_profile("combat")
    assert ok is True
    assert "profile=combat" in message
    events = store.filter(subsystem="RADAR", event_type="POLICY_PROFILE_CHANGED")
    assert events
    payload = events[-1].payload
    assert payload["previous_profile"] == "navigation"
    assert payload["new_profile"] == "combat"


def test_adaptive_hysteresis_and_cooldown_without_sleep() -> None:
    class _Clock:
        def __init__(self) -> None:
            self.now = 0.0

        def tick(self, dt: float = 0.1) -> float:
            self.now += dt
            return self.now

        def __call__(self) -> float:
            return self.now

    clock = _Clock()
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        clock=clock,
    )
    pipeline.adaptive_policy = pipeline.adaptive_policy.__class__(
        enabled=True,
        ema_alpha_frame_ms=1.0,
        ema_alpha_targets=1.0,
        high_frame_ratio=1.1,
        low_frame_ratio=0.8,
        overload_target_ratio=1.0,
        underload_target_ratio=0.8,
        degrade_confirm_frames=3,
        recovery_confirm_frames=4,
        cooldown_ms=500,
        max_level=2,
        clutter_reduction_per_level=0.2,
        lod_label_zoom_delta_per_level=0.1,
        lod_detail_zoom_delta_per_level=0.1,
    )
    up_changes: list[float] = []
    down_changes: list[float] = []
    previous_level = pipeline._adaptive_state.level
    for _ in range(120):
        clock.tick(0.1)
        pipeline._update_adaptive_state(frame_time_ms=400.0, targets_count=999)
        level = pipeline._adaptive_state.level
        if level != previous_level:
            if level > previous_level:
                up_changes.append(clock.now)
            previous_level = level
    for idx in range(1, len(up_changes)):
        assert (up_changes[idx] - up_changes[idx - 1]) >= 0.5

    for _ in range(120):
        clock.tick(0.1)
        pipeline._update_adaptive_state(frame_time_ms=2.0, targets_count=1)
        level = pipeline._adaptive_state.level
        if level != previous_level:
            if level < previous_level:
                down_changes.append(clock.now)
            previous_level = level
    for idx in range(1, len(down_changes)):
        assert (down_changes[idx] - down_changes[idx - 1]) >= 0.5
    assert pipeline._adaptive_state.level == 0
