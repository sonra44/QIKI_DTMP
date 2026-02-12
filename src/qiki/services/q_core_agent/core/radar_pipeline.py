"""Radar rendering pipeline with backend auto-detect and runtime fallback."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import replace
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from .radar_backends import (
    KittyRadarBackend,
    RadarBackend,
    RadarScene,
    RenderOutput,
    SixelRadarBackend,
    UnicodeRadarBackend,
)
from .event_store import EventStore, TruthState
from .radar_clock import Clock, ReplayClock, ensure_clock
from .radar_fusion import (
    FusionConfig,
    FusionStateStore,
    FusedTrack,
    FusionCluster,
    fuse_tracks,
    fused_tracks_to_scene,
)
from .radar_ingestion import Observation, SourceTrack, ingest_observations, source_tracks_to_scene
from .radar_replay import RadarReplayEngine, TimelineState, load_trace
from .radar_policy_loader import load_effective_render_policy_result
from .radar_render_policy import DegradationState, RadarRenderPlan, RadarRenderPolicy
from .radar_situation_engine import RadarSituationEngine, Situation, SituationSeverity, SituationStatus
from .radar_trail_store import RadarTrailStore
from .radar_view_state import RadarViewState

_ALLOWED_VIEWS = {"top", "side", "front", "iso"}


@dataclass(frozen=True)
class RadarRenderConfig:
    renderer: str
    view: str
    fps_max: int
    color: bool

    @classmethod
    def from_env(cls) -> "RadarRenderConfig":
        renderer = os.getenv("RADAR_RENDERER", "auto").strip().lower() or "auto"
        view = os.getenv("RADAR_VIEW", "top").strip().lower() or "top"
        if view not in _ALLOWED_VIEWS:
            view = "top"
        try:
            fps_max = max(1, int(os.getenv("RADAR_FPS_MAX", "10")))
        except Exception:
            fps_max = 10
        color_raw = os.getenv("RADAR_COLOR", "1").strip().lower()
        color = color_raw not in {"0", "false", "no", "off"}
        return cls(renderer=renderer, view=view, fps_max=fps_max, color=color)


@dataclass(frozen=True)
class AdaptivePolicyState:
    level: int = 0
    ema_frame_ms: float | None = None
    ema_targets: float | None = None
    consecutive_high: int = 0
    consecutive_low: int = 0
    last_change_ts: float = 0.0


class RadarPipeline:
    def __init__(
        self,
        config: RadarRenderConfig | None = None,
        *,
        event_store: EventStore | None = None,
        clock: Clock | Callable[[], float] | None = None,
        replay_file: str | None = None,
    ):
        self.config = config or RadarRenderConfig.from_env()
        telemetry_raw = os.getenv("RADAR_TELEMETRY", "1").strip().lower()
        self.telemetry_enabled = telemetry_raw not in {"0", "false", "no", "off"}
        emit_observation_raw = os.getenv("RADAR_EMIT_OBSERVATION_RX", "0").strip().lower()
        self.emit_observation_rx = emit_observation_raw in {"1", "true", "yes", "on"}
        self.event_store = event_store
        self._clock = ensure_clock(clock)
        self._replay_engine: RadarReplayEngine | None = None
        self._replay_tracks: dict[str, dict[str, SourceTrack]] = {}
        self._replay_strict = os.getenv("RADAR_REPLAY_STRICT_DETERMINISM", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        replay_from_env = os.getenv("RADAR_REPLAY_FILE", "").strip()
        self._replay_file = (replay_file if replay_file is not None else replay_from_env).strip()
        try:
            replay_speed = float(os.getenv("RADAR_REPLAY_SPEED", "1.0") or "1.0")
        except Exception:
            replay_speed = 1.0
        self._replay_speed = max(0.1, replay_speed)
        self._replay_step = os.getenv("RADAR_REPLAY_STEP", "0").strip().lower() in {"1", "true", "yes", "on"}
        self._replay_init_warning = ""
        self._replay_init_payload: dict[str, Any] | None = None
        if self._replay_file:
            self._init_replay(self._replay_file)
        self.fusion_config = FusionConfig.from_env()
        self.view_state = RadarViewState.from_env()
        load_result = load_effective_render_policy_result()
        self.render_policy = load_result.render_policy
        self.adaptive_policy = load_result.adaptive_policy
        self.policy_profile = load_result.selected_profile
        self.policy_source = load_result.policy_source
        self.trail_store = RadarTrailStore(max_len=self.render_policy.trail_len)
        self.situation_engine = RadarSituationEngine(clock=self._clock)
        self.last_situations: tuple[Situation, ...] = ()
        self.session_id = str(uuid4())
        self._last_frame_time_ms = 0.0
        self._degradation_state = DegradationState(last_scale=self.render_policy.bitmap_scales[0])
        self._adaptive_state = AdaptivePolicyState()
        self._last_effective_policy = self.render_policy
        if self.config.view in _ALLOWED_VIEWS:
            self.view_state = RadarViewState(
                zoom=self.view_state.zoom,
                pan_x=self.view_state.pan_x,
                pan_y=self.view_state.pan_y,
                rot_yaw=self.view_state.rot_yaw,
                rot_pitch=self.view_state.rot_pitch,
                view=self.config.view,
                selected_target_id=self.view_state.selected_target_id,
                overlays_enabled=self.view_state.overlays_enabled,
                color_enabled=self.config.color and self.view_state.color_enabled,
                overlays=self.view_state.overlays,
                inspector=self.view_state.inspector,
            )
        self._unicode = UnicodeRadarBackend()
        self._kitty = KittyRadarBackend()
        self._sixel = SixelRadarBackend()
        self._active_backend = self.detect_best_backend()
        if load_result.warning_reason:
            self._append_policy_event(
                event_type="POLICY_FALLBACK",
                reason=load_result.warning_reason,
                payload={
                    "policy_profile": self.policy_profile,
                    "policy_source": self.policy_source,
                },
            )
        if self._replay_init_warning:
            self._append_policy_event(
                event_type="REPLAY_DISABLED",
                reason=self._replay_init_warning,
                payload={"replay_file": self._replay_file},
            )
        if self._replay_init_payload is not None:
            self._append_policy_event(
                event_type="REPLAY_ENABLED",
                reason="TRACE_SOURCE_ACTIVE",
                payload=self._replay_init_payload,
            )
        self._tracks_by_source: dict[str, list[SourceTrack]] = {}
        self._fusion_state = FusionStateStore()
        self._last_fused_signatures: dict[str, tuple[object, ...]] = {}
        self._last_cluster_signatures: set[tuple[object, ...]] = set()

    @property
    def active_backend_name(self) -> str:
        return self._active_backend.name

    @property
    def replay_enabled(self) -> bool:
        return self._replay_engine is not None

    @property
    def timeline_state(self) -> TimelineState | None:
        if self._replay_engine is None:
            return None
        return self._replay_engine.timeline

    def replay_pause(self) -> None:
        if self._replay_engine is not None:
            self._replay_engine.pause()

    def replay_resume(self) -> None:
        if self._replay_engine is not None:
            self._replay_engine.resume()

    def replay_jump_to_ts(self, ts: float) -> None:
        if self._replay_engine is not None:
            self._replay_engine.jump_to_ts(ts)

    def replay_jump_to_event_type(self, event_type: str) -> bool:
        if self._replay_engine is None:
            return False
        return self._replay_engine.jump_to_event_type(event_type)

    def replay_jump_to_situation_id(self, situation_id: str) -> bool:
        if self._replay_engine is None:
            return False
        return self._replay_engine.jump_to_situation_id(situation_id)

    def _init_replay(self, replay_file: str) -> None:
        try:
            events = load_trace(replay_file)
        except Exception as exc:  # noqa: BLE001
            if self._replay_strict:
                raise RuntimeError(f"Failed to load replay trace: {replay_file}: {exc}") from exc
            self._replay_init_warning = f"TRACE_LOAD_FAILED:{exc}"
            return
        initial_ts = float(events[0].get("ts", 0.0)) if events else 0.0
        replay_clock = ReplayClock(current_ts=initial_ts)
        self._clock = replay_clock
        self._replay_engine = RadarReplayEngine(
            events,
            speed=self._replay_speed,
            step=self._replay_step,
            clock=replay_clock,
        )
        self._replay_init_payload = {
            "replay_file": replay_file,
            "speed": self._replay_speed,
            "step": self._replay_step,
        }

    def set_policy_profile(self, profile: str) -> tuple[bool, str]:
        requested = (profile or "").strip().lower()
        if requested not in {"navigation", "docking", "combat"}:
            return False, f"Unsupported profile: {profile!r}"
        previous_profile = self.policy_profile
        previous_source = self.policy_source
        result = load_effective_render_policy_result(profile=requested)
        self.render_policy = result.render_policy
        self.adaptive_policy = result.adaptive_policy
        self.policy_profile = result.selected_profile
        self.policy_source = result.policy_source
        self._adaptive_state = AdaptivePolicyState()
        self._degradation_state = DegradationState(last_scale=self.render_policy.bitmap_scales[0])
        self._last_effective_policy = self.render_policy
        self.trail_store = RadarTrailStore(max_len=self.render_policy.trail_len)
        self._append_policy_event(
            event_type="POLICY_PROFILE_CHANGED",
            reason=f"{previous_profile}->{self.policy_profile}",
            payload={
                "previous_profile": previous_profile,
                "new_profile": self.policy_profile,
                "previous_source": previous_source,
                "new_source": self.policy_source,
            },
        )
        if result.warning_reason:
            self._append_policy_event(
                event_type="POLICY_FALLBACK",
                reason=result.warning_reason,
                payload={
                    "policy_profile": self.policy_profile,
                    "policy_source": self.policy_source,
                },
            )
        return True, f"profile={self.policy_profile} source={self.policy_source}"

    def cycle_policy_profile(self) -> tuple[bool, str]:
        order = ("navigation", "docking", "combat")
        try:
            idx = order.index(self.policy_profile)
        except ValueError:
            idx = 0
        return self.set_policy_profile(order[(idx + 1) % len(order)])

    def _append_policy_event(self, *, event_type: str, reason: str, payload: dict) -> None:
        if self.event_store is None:
            return
        full_payload = {
            "policy_profile": self.policy_profile,
            "policy_source": self.policy_source,
            **payload,
        }
        self.event_store.append_new(
            subsystem="RADAR",
            event_type=event_type,
            payload=full_payload,
            truth_state=TruthState.OK,
            reason=reason,
        )

    def _effective_policy(self) -> RadarRenderPolicy:
        if not self.adaptive_policy.enabled:
            return self.render_policy
        level = max(0, min(self._adaptive_state.level, self.adaptive_policy.max_level))
        if level == 0:
            return self.render_policy
        clutter_multiplier = max(0.05, 1.0 - (self.adaptive_policy.clutter_reduction_per_level * float(level)))
        clutter_targets = max(1, int(round(float(self.render_policy.clutter_targets_max) * clutter_multiplier)))
        return replace(
            self.render_policy,
            clutter_targets_max=clutter_targets,
            lod_label_zoom=self.render_policy.lod_label_zoom
            + (self.adaptive_policy.lod_label_zoom_delta_per_level * float(level)),
            lod_detail_zoom=self.render_policy.lod_detail_zoom
            + (self.adaptive_policy.lod_detail_zoom_delta_per_level * float(level)),
        )

    def _update_adaptive_state(self, *, frame_time_ms: float, targets_count: int) -> None:
        if not self.adaptive_policy.enabled:
            return
        alpha_frame = min(1.0, max(0.0, float(self.adaptive_policy.ema_alpha_frame_ms)))
        alpha_targets = min(1.0, max(0.0, float(self.adaptive_policy.ema_alpha_targets)))
        prev = self._adaptive_state
        ema_frame = float(frame_time_ms) if prev.ema_frame_ms is None else (
            (alpha_frame * float(frame_time_ms)) + ((1.0 - alpha_frame) * prev.ema_frame_ms)
        )
        ema_targets = float(targets_count) if prev.ema_targets is None else (
            (alpha_targets * float(targets_count)) + ((1.0 - alpha_targets) * prev.ema_targets)
        )
        budget = float(self.render_policy.frame_budget_ms)
        target_budget = float(self.render_policy.clutter_targets_max)
        high = (
            ema_frame > (budget * float(self.adaptive_policy.high_frame_ratio))
            or ema_targets > (target_budget * float(self.adaptive_policy.overload_target_ratio))
        )
        low = (
            ema_frame < (budget * float(self.adaptive_policy.low_frame_ratio))
            and ema_targets < (target_budget * float(self.adaptive_policy.underload_target_ratio))
        )
        consecutive_high = (prev.consecutive_high + 1) if high else 0
        consecutive_low = (prev.consecutive_low + 1) if low else 0
        now = self._clock.now()
        elapsed_ms = (
            (now - prev.last_change_ts) * 1000.0 if prev.last_change_ts > 0.0 else float(self.adaptive_policy.cooldown_ms) + 1.0
        )
        can_change = elapsed_ms >= float(self.adaptive_policy.cooldown_ms)
        level = prev.level
        last_change_ts = prev.last_change_ts
        if (
            can_change
            and high
            and consecutive_high >= int(self.adaptive_policy.degrade_confirm_frames)
            and level < int(self.adaptive_policy.max_level)
        ):
            level += 1
            consecutive_high = 0
            consecutive_low = 0
            last_change_ts = now
        elif can_change and low and consecutive_low >= int(self.adaptive_policy.recovery_confirm_frames) and level > 0:
            level -= 1
            consecutive_high = 0
            consecutive_low = 0
            last_change_ts = now
        self._adaptive_state = AdaptivePolicyState(
            level=level,
            ema_frame_ms=ema_frame,
            ema_targets=ema_targets,
            consecutive_high=consecutive_high,
            consecutive_low=consecutive_low,
            last_change_ts=last_change_ts,
        )

    def build_render_plan(self, scene: RadarScene, *, view_state: RadarViewState | None = None) -> RadarRenderPlan:
        active_view_state = view_state or self.view_state
        effective_policy = self._effective_policy()
        self._last_effective_policy = effective_policy
        plan, next_state = effective_policy.build_plan(
            view_state=active_view_state,
            targets_count=len(scene.points),
            frame_time_ms=self._last_frame_time_ms,
            backend_name=self._active_backend.name,
            degradation_state=self._degradation_state,
            now_ts=self._clock.now(),
        )
        self._degradation_state = next_state
        return plan

    def detect_best_backend(self) -> RadarBackend:
        requested = self.config.renderer
        if requested == "unicode":
            return self._unicode
        if requested == "kitty":
            if self._kitty.is_supported():
                return self._kitty
            raise RuntimeError("RADAR_RENDERER=kitty requested but Kitty backend is unsupported")
        if requested == "sixel":
            if self._sixel.is_supported():
                return self._sixel
            raise RuntimeError("RADAR_RENDERER=sixel requested but SIXEL backend is unsupported")

        # auto mode: prefer bitmap upgrades only when support is clear.
        if self._kitty.is_supported():
            return self._kitty
        if self._sixel.is_supported():
            return self._sixel
        return self._unicode

    def render_scene(self, scene: RadarScene, *, view_state: RadarViewState | None = None) -> RenderOutput:
        active_view_state = view_state or self.view_state
        self.trail_store.update_from_scene(scene)
        scene_with_trails = RadarScene(
            ok=scene.ok,
            reason=scene.reason,
            truth_state=scene.truth_state,
            is_fallback=scene.is_fallback,
            points=scene.points,
            trails={k: v for k, v in self.trail_store.get_all().items()},
        )
        plan = self.build_render_plan(scene_with_trails, view_state=active_view_state)
        situations, deltas = self.situation_engine.evaluate(
            scene_with_trails,
            trail_store=self.trail_store,
            view_state=active_view_state,
            render_stats=plan.stats,
        )
        active_view_state = self._apply_alert_selection(active_view_state, situations)
        self.view_state = active_view_state
        self.last_situations = tuple(situations)
        self._append_situation_events(scene_with_trails, deltas)
        render_start = self._clock.now()
        try:
            if self._active_backend.name == "unicode":
                output = self._active_backend.render(
                    scene_with_trails,
                    view_state=active_view_state,
                    color=(self.config.color and active_view_state.color_enabled),
                    render_plan=plan,
                    situations=tuple(situations),
                )
            else:
                output = self._active_backend.render(
                    scene_with_trails,
                    view_state=active_view_state,
                    color=(self.config.color and active_view_state.color_enabled),
                    render_plan=plan,
                )
            self._last_frame_time_ms = (self._clock.now() - render_start) * 1000.0
            self._update_adaptive_state(frame_time_ms=self._last_frame_time_ms, targets_count=len(scene_with_trails.points))
            self._append_render_tick_event(scene_with_trails, output)
            return output
        except Exception as exc:  # noqa: BLE001
            if self._active_backend.name == "unicode":
                raise
            previous = self._active_backend.name
            self._active_backend = self._unicode
            fallback = self._active_backend.render(
                scene_with_trails,
                view_state=active_view_state,
                color=(self.config.color and active_view_state.color_enabled),
                render_plan=plan,
                situations=tuple(situations),
            )
            marker = f"[RADAR RUNTIME FALLBACK {previous}->unicode: {exc}]"
            self._last_frame_time_ms = (self._clock.now() - render_start) * 1000.0
            self._update_adaptive_state(frame_time_ms=self._last_frame_time_ms, targets_count=len(scene_with_trails.points))
            output = RenderOutput(
                backend=fallback.backend,
                lines=[marker, *fallback.lines],
                used_runtime_fallback=True,
                plan=plan,
                stats=plan.stats,
            )
            self._append_render_tick_event(scene_with_trails, output)
            return output

    def _source_track_from_replay_event(self, event: dict[str, Any]) -> SourceTrack | None:
        if str(event.get("event_type", "")) != "SOURCE_TRACK_UPDATED":
            return None
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            return None
        source_id = str(payload.get("source_id", "")).strip()
        source_track_id = str(payload.get("source_track_id", "")).strip()
        if not source_id or not source_track_id:
            return None
        try:
            pos_raw = payload.get("pos", [0.0, 0.0])
            if not isinstance(pos_raw, (list, tuple)) or len(pos_raw) < 2:
                return None
            pos_xy = (float(pos_raw[0]), float(pos_raw[1]))
            vel_xy: tuple[float, float] | None = None
            vel_raw = payload.get("vel")
            if isinstance(vel_raw, (list, tuple)) and len(vel_raw) >= 2:
                vel_xy = (float(vel_raw[0]), float(vel_raw[1]))
            updated_t = float(payload.get("t", event.get("ts", self._clock.now())))
            quality = float(payload.get("quality", payload.get("trust", 0.5)))
            trust = float(payload.get("trust", quality))
        except Exception:
            return None
        return SourceTrack(
            source_id=source_id,
            source_track_id=source_track_id,
            last_update_t=updated_t,
            state_pos_xy=pos_xy,
            state_vel_xy=vel_xy,
            quality=quality,
            trust=trust,
            metadata={"replay": True},
        )

    def _replay_observation_ts(self, event: dict[str, Any]) -> float | None:
        if str(event.get("event_type", "")) != "SOURCE_TRACK_UPDATED":
            return None
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            return None
        try:
            return float(payload.get("t"))
        except Exception:
            return None

    def _ingest_replay_tracks(self) -> dict[str, list[SourceTrack]]:
        if self._replay_engine is None:
            return {}
        replay_batch = self._replay_engine.next_batch()
        if replay_batch:
            frame_t = self._replay_observation_ts(replay_batch[0])
            if frame_t is not None:
                while True:
                    next_event = self._replay_engine.peek_next()
                    next_t = self._replay_observation_ts(next_event) if next_event is not None else None
                    if next_t is None or abs(next_t - frame_t) > 1e-6:
                        break
                    replay_batch.extend(self._replay_engine.next_batch())
        now_ts = self._clock.now()
        for event in replay_batch:
            track = self._source_track_from_replay_event(event)
            if track is None:
                continue
            bucket = self._replay_tracks.setdefault(track.source_id, {})
            bucket[track.source_track_id] = track
        # Keep replay tracks fresh; stale tracks are removed to avoid immortal targets.
        for source_id in list(self._replay_tracks.keys()):
            source_bucket = self._replay_tracks[source_id]
            for track_id in list(source_bucket.keys()):
                if now_ts - float(source_bucket[track_id].last_update_t) > float(self.fusion_config.max_age_s):
                    del source_bucket[track_id]
            if not source_bucket:
                del self._replay_tracks[source_id]
        return {source_id: list(bucket.values()) for source_id, bucket in self._replay_tracks.items()}

    def ingest_observations(self, observations: list[Observation]) -> dict[str, list[SourceTrack]]:
        if self._replay_engine is not None:
            self._tracks_by_source = self._ingest_replay_tracks()
            return {source_id: list(tracks) for source_id, tracks in self._tracks_by_source.items()}
        self._tracks_by_source = ingest_observations(
            observations,
            event_store=self.event_store,
            emit_observation_rx=self.emit_observation_rx,
        )
        return {source_id: list(tracks) for source_id, tracks in self._tracks_by_source.items()}

    def render_observations(
        self,
        observations: list[Observation],
        *,
        view_state: RadarViewState | None = None,
        truth_state: str = "OK",
        reason: str = "OK",
        is_fallback: bool = False,
    ) -> RenderOutput:
        tracks_by_source = self.ingest_observations(observations)
        if self.fusion_config.enabled:
            fused_set, self._fusion_state = fuse_tracks(
                tracks_by_source,
                cfg=self.fusion_config,
                prev_state=self._fusion_state,
                now=self._clock.now(),
            )
            self._append_fusion_events(
                scene_truth_state=truth_state,
                fused_tracks=fused_set.tracks,
                clusters=fused_set.clusters,
            )
            scene = fused_tracks_to_scene(
                fused_set,
                truth_state=truth_state,
                reason=reason,
                is_fallback=is_fallback,
            )
        else:
            scene = source_tracks_to_scene(
                tracks_by_source,
                truth_state=truth_state,
                reason=reason,
                is_fallback=is_fallback,
            )
        return self.render_scene(scene, view_state=view_state)

    def _append_fusion_events(
        self,
        *,
        scene_truth_state: str,
        fused_tracks: tuple[FusedTrack, ...],
        clusters: tuple[FusionCluster, ...],
    ) -> None:
        if self.event_store is None:
            return
        truth_state = self._normalize_truth_state(scene_truth_state)
        current_cluster_signatures: set[tuple[object, ...]] = set()
        for cluster in clusters:
            signature = (
                tuple(f"{contributor.source_id}:{contributor.source_track_id}" for contributor in cluster.contributors),
                int(cluster.support_ok),
                round(float(cluster.spread_pos), 2),
            )
            current_cluster_signatures.add(signature)
            if signature in self._last_cluster_signatures:
                continue
            self.event_store.append_new(
                subsystem="FUSION",
                event_type="FUSION_CLUSTER_BUILT",
                payload={
                    "cluster_size": len(cluster.contributors),
                    "sources": sorted({contributor.source_id for contributor in cluster.contributors}),
                    "spread": float(cluster.spread_pos),
                    "support_ok": bool(cluster.support_ok),
                },
                truth_state=truth_state,
                reason="CLUSTER_BUILT",
            )
        self._last_cluster_signatures = current_cluster_signatures

        next_signatures: dict[str, tuple[object, ...]] = {}
        for track in fused_tracks:
            signature = (
                round(float(track.pos_xy[0]), 2),
                round(float(track.pos_xy[1]), 2),
                None if track.vel_xy is None else round(float(track.vel_xy[0]), 2),
                None if track.vel_xy is None else round(float(track.vel_xy[1]), 2),
                round(float(track.trust), 3),
                tuple(sorted(track.flags)),
                tuple(
                    sorted(f"{contributor.source_id}:{contributor.source_track_id}" for contributor in track.contributors)
                ),
            )
            next_signatures[track.fused_id] = signature
            if self._last_fused_signatures.get(track.fused_id) == signature:
                continue
            self.event_store.append_new(
                subsystem="FUSION",
                event_type="FUSED_TRACK_UPDATED",
                payload={
                    "fused_id": track.fused_id,
                    "contributors": [
                        {
                            "source_id": contributor.source_id,
                            "source_track_id": contributor.source_track_id,
                            "trust": float(contributor.trust),
                            "quality": float(contributor.quality),
                            "dt": float(contributor.dt),
                        }
                        for contributor in track.contributors
                    ],
                    "trust": float(track.trust),
                    "flags": sorted(track.flags),
                    "pos": [float(track.pos_xy[0]), float(track.pos_xy[1])],
                    "vel": (
                        None
                        if track.vel_xy is None
                        else [float(track.vel_xy[0]), float(track.vel_xy[1])]
                    ),
                    "support_ok": len({contributor.source_id for contributor in track.contributors})
                    >= int(self.fusion_config.min_support),
                },
                truth_state=truth_state,
                reason="TRACK_FUSED",
            )
        self._last_fused_signatures = next_signatures

    def _apply_alert_selection(self, view_state: RadarViewState, situations: list[Situation]) -> RadarViewState:
        def _severity_rank_local(s: Situation) -> int:
            if s.severity == SituationSeverity.CRITICAL:
                return 0
            if s.severity == SituationSeverity.WARN:
                return 1
            return 2

        def _status_rank_local(s: Situation) -> int:
            if s.status == SituationStatus.ACTIVE:
                return 0
            if s.status == SituationStatus.LOST:
                return 1
            return 2

        ordered = sorted(
            situations,
            key=lambda s: (_status_rank_local(s), _severity_rank_local(s), -float(s.last_update_ts), s.id),
        )
        if not ordered:
            return view_state
        cursor = view_state.alerts.cursor % len(ordered)
        selected_situation = ordered[cursor]
        selected_track = selected_situation.track_ids[0] if selected_situation.track_ids else None
        return replace(
            view_state,
            selected_target_id=selected_track or view_state.selected_target_id,
            alerts=replace(
                view_state.alerts,
                selected_situation_id=selected_situation.id,
                focus_track_id=selected_track,
            ),
        )

    def _append_situation_events(self, scene: RadarScene, deltas: list) -> None:
        if self.event_store is None or not deltas:
            return
        truth_state = self._normalize_truth_state(scene.truth_state)
        for delta in deltas:
            situation = delta.situation
            self.event_store.append_new(
                subsystem="SITUATION",
                event_type=delta.event_type,
                payload={
                    "schema_version": 1,
                    "timestamp": float(situation.last_update_ts),
                    "session_id": self.session_id,
                    "track_id": situation.track_ids[0] if situation.track_ids else "",
                    "situation_id": situation.id,
                    "status": situation.status.value,
                    "type": situation.type.value,
                    "severity": situation.severity.value,
                    "reason": situation.reason,
                    "track_ids": list(situation.track_ids),
                    "metrics": dict(situation.metrics),
                    "created_ts": float(situation.created_ts),
                    "last_update_ts": float(situation.last_update_ts),
                    "is_active": bool(situation.is_active),
                },
                truth_state=truth_state,
                reason=situation.reason,
            )

    def _append_render_tick_event(self, scene: RadarScene, output: RenderOutput) -> None:
        if not self.telemetry_enabled or self.event_store is None:
            return
        stats = output.stats
        plan = output.plan
        if stats is None or plan is None:
            return
        truth_state = self._normalize_truth_state(scene.truth_state)
        reasons = list(stats.clutter_reasons)
        self.event_store.append_new(
            subsystem="RADAR",
            event_type="RADAR_RENDER_TICK",
            payload={
                "frame_ms": float(stats.frame_time_ms),
                "fps_cap": int(self.config.fps_max),
                "targets_count": int(stats.targets_count),
                "lod_level": int(stats.lod_level),
                "degradation_level": int(stats.degradation_level),
                "bitmap_scale": float(stats.bitmap_scale),
                "dropped_overlays": list(stats.dropped_overlays),
                "clutter_reasons": reasons,
                "backend": output.backend,
                "policy_profile": self.policy_profile,
                "policy_source": self.policy_source,
                "adaptive_level": int(self._adaptive_state.level),
                "effective_frame_budget_ms": float(self._last_effective_policy.frame_budget_ms),
                "effective_clutter_max": int(self._last_effective_policy.clutter_targets_max),
            },
            truth_state=truth_state,
            reason=",".join(reasons) if reasons else "OK",
        )

    def _normalize_truth_state(self, value: str) -> TruthState:
        normalized = str(value or "").upper()
        if normalized == TruthState.NO_DATA.value:
            return TruthState.NO_DATA
        if normalized == TruthState.FALLBACK.value:
            return TruthState.FALLBACK
        if normalized in {TruthState.OK.value, TruthState.NO_DATA.value, TruthState.FALLBACK.value}:
            return TruthState.OK
        return TruthState.INVALID


def render_radar_scene(scene: RadarScene, *, pipeline: RadarPipeline | None = None) -> RenderOutput:
    active = pipeline or RadarPipeline()
    return active.render_scene(scene)
