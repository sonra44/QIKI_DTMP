"""Radar plugin interfaces and built-in plugin implementations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Protocol, runtime_checkable

from .plugin_manager import PluginContext, PluginManager, PluginSpec
from .radar_backends import (
    KittyRadarBackend,
    RadarBackend,
    RadarScene,
    SixelRadarBackend,
    UnicodeRadarBackend,
)
from .radar_fusion import (
    FusionCluster,
    FusionConfig,
    FusionStateStore,
    FusedTrack,
    fuse_tracks,
    fused_tracks_to_scene,
)
from .radar_ingestion import Observation, SourceTrack, ingest_observations, source_tracks_to_scene
from .radar_policy_loader import AdaptivePolicyConfig, RadarPolicyLoadResult, load_effective_render_policy_result
from .radar_render_policy import RadarRenderPolicy, RadarRenderStats
from .radar_situation_engine import RadarSituationEngine, Situation
from .radar_trail_store import RadarTrailStore
from .radar_view_state import RadarViewState
from .session_client import SessionClient
from .session_server import SessionServer


@runtime_checkable
class SensorInputPlugin(Protocol):
    def poll(self) -> list[Observation]:
        ...

    def health(self) -> dict[str, Any]:
        ...

    def ingest(
        self,
        observations: list[Observation],
        *,
        emit_observation_rx: bool,
    ) -> dict[str, list[SourceTrack]]:
        ...


@runtime_checkable
class FusionPlugin(Protocol):
    @property
    def config(self) -> FusionConfig:
        ...

    def fuse(
        self,
        tracks_by_source: dict[str, list[SourceTrack]],
        *,
        now: float,
        truth_state: str,
        reason: str,
        is_fallback: bool,
    ) -> tuple[RadarScene, tuple[FusedTrack, ...], tuple[FusionCluster, ...]]:
        ...


@runtime_checkable
class RenderPolicyPlugin(Protocol):
    @property
    def adaptive_policy(self) -> AdaptivePolicyConfig:
        ...

    @property
    def profile(self) -> str:
        ...

    @property
    def policy_source(self) -> str:
        ...

    @property
    def warning_reason(self) -> str:
        ...

    def current_policy(self) -> RadarRenderPolicy:
        ...

    def load_profile(self, profile: str | None = None) -> RadarPolicyLoadResult:
        ...

    def effective_policy(
        self,
        *,
        base_policy: RadarRenderPolicy,
        adaptive_level: int,
    ) -> RadarRenderPolicy:
        ...


@runtime_checkable
class RenderBackendPlugin(Protocol):
    @property
    def unicode_backend(self) -> RadarBackend:
        ...

    def select_backend(self, requested: str) -> RadarBackend:
        ...


@runtime_checkable
class SituationalAnalysisPlugin(Protocol):
    def update(
        self,
        *,
        scene: RadarScene,
        trail_store: RadarTrailStore,
        view_state: RadarViewState,
        render_stats: RadarRenderStats,
    ) -> tuple[list[Situation], list[Any]]:
        ...


@runtime_checkable
class SessionTransportPlugin(Protocol):
    def create_server(self, *, pipeline: Any, event_store: Any, host: str, port: int) -> SessionServer:
        ...

    def create_client(self, *, host: str, port: int, client_id: str, role: str) -> SessionClient:
        ...


@runtime_checkable
class InputRouterPlugin(Protocol):
    def can_accept_input(self, *, controller_id: str, client_id: str) -> bool:
        ...


@dataclass
class BuiltinSensorInputPlugin:
    context: PluginContext

    def poll(self) -> list[Observation]:
        return []

    def health(self) -> dict[str, Any]:
        return {"ok": True, "mode": "ingest-by-call"}

    def ingest(
        self,
        observations: list[Observation],
        *,
        emit_observation_rx: bool,
    ) -> dict[str, list[SourceTrack]]:
        return ingest_observations(
            observations,
            event_store=self.context.event_store,
            emit_observation_rx=emit_observation_rx,
        )


@dataclass
class BuiltinFusionPlugin:
    context: PluginContext
    config: FusionConfig
    _state: FusionStateStore

    def fuse(
        self,
        tracks_by_source: dict[str, list[SourceTrack]],
        *,
        now: float,
        truth_state: str,
        reason: str,
        is_fallback: bool,
    ) -> tuple[RadarScene, tuple[FusedTrack, ...], tuple[FusionCluster, ...]]:
        if self.config.enabled:
            fused_set, self._state = fuse_tracks(
                tracks_by_source,
                cfg=self.config,
                prev_state=self._state,
                now=now,
            )
            scene = fused_tracks_to_scene(
                fused_set,
                truth_state=truth_state,
                reason=reason,
                is_fallback=is_fallback,
            )
            return scene, fused_set.tracks, fused_set.clusters
        scene = source_tracks_to_scene(
            tracks_by_source,
            truth_state=truth_state,
            reason=reason,
            is_fallback=is_fallback,
        )
        return scene, (), ()


@dataclass
class BuiltinRenderPolicyPlugin:
    context: PluginContext
    _result: RadarPolicyLoadResult

    @property
    def adaptive_policy(self) -> AdaptivePolicyConfig:
        return self._result.adaptive_policy

    @property
    def profile(self) -> str:
        return self._result.selected_profile

    @property
    def policy_source(self) -> str:
        return self._result.policy_source

    @property
    def warning_reason(self) -> str:
        return self._result.warning_reason

    def current_policy(self) -> RadarRenderPolicy:
        return self._result.render_policy

    def load_profile(self, profile: str | None = None) -> RadarPolicyLoadResult:
        requested = (profile or "").strip().lower() or None
        self._result = load_effective_render_policy_result(profile=requested)
        return self._result

    def effective_policy(
        self,
        *,
        base_policy: RadarRenderPolicy,
        adaptive_level: int,
    ) -> RadarRenderPolicy:
        if not self.adaptive_policy.enabled or adaptive_level <= 0:
            return base_policy
        level = max(0, min(int(adaptive_level), int(self.adaptive_policy.max_level)))
        clutter_multiplier = max(0.05, 1.0 - (self.adaptive_policy.clutter_reduction_per_level * float(level)))
        clutter_targets = max(1, int(round(float(base_policy.clutter_targets_max) * clutter_multiplier)))
        return replace(
            base_policy,
            clutter_targets_max=clutter_targets,
            lod_label_zoom=base_policy.lod_label_zoom + (self.adaptive_policy.lod_label_zoom_delta_per_level * float(level)),
            lod_detail_zoom=base_policy.lod_detail_zoom
            + (self.adaptive_policy.lod_detail_zoom_delta_per_level * float(level)),
        )


@dataclass
class BuiltinRenderBackendPlugin:
    unicode_backend: RadarBackend
    kitty_backend: RadarBackend
    sixel_backend: RadarBackend

    def select_backend(self, requested: str) -> RadarBackend:
        mode = (requested or "auto").strip().lower() or "auto"
        if mode == "unicode":
            return self.unicode_backend
        if mode == "kitty":
            if self.kitty_backend.is_supported():
                return self.kitty_backend
            raise RuntimeError("RADAR_RENDERER=kitty requested but Kitty backend is unsupported")
        if mode == "sixel":
            if self.sixel_backend.is_supported():
                return self.sixel_backend
            raise RuntimeError("RADAR_RENDERER=sixel requested but SIXEL backend is unsupported")
        if self.kitty_backend.is_supported():
            return self.kitty_backend
        if self.sixel_backend.is_supported():
            return self.sixel_backend
        return self.unicode_backend


@dataclass
class BuiltinSituationalAnalysisPlugin:
    engine: RadarSituationEngine

    def update(
        self,
        *,
        scene: RadarScene,
        trail_store: RadarTrailStore,
        view_state: RadarViewState,
        render_stats: RadarRenderStats,
    ) -> tuple[list[Situation], list[Any]]:
        return self.engine.evaluate(
            scene,
            trail_store=trail_store,
            view_state=view_state,
            render_stats=render_stats,
        )


@dataclass
class BuiltinSessionTransportPlugin:
    def create_server(self, *, pipeline: Any, event_store: Any, host: str, port: int) -> SessionServer:
        return SessionServer(pipeline=pipeline, event_store=event_store, host=host, port=port)

    def create_client(self, *, host: str, port: int, client_id: str, role: str) -> SessionClient:
        return SessionClient(host=host, port=port, client_id=client_id, role=role)


@dataclass
class BuiltinInputRouterPlugin:
    def can_accept_input(self, *, controller_id: str, client_id: str) -> bool:
        return bool(controller_id) and controller_id == client_id


def register_builtin_radar_plugins(manager: PluginManager) -> None:
    manager.register_many(
        [
            PluginSpec(
                name="builtin.sensor_input",
                kind="sensor_input",
                version="1.0.0",
                provides=("sensor_input",),
                requires=(),
                factory=lambda ctx, _params: BuiltinSensorInputPlugin(context=ctx),
            ),
            PluginSpec(
                name="builtin.fusion_majority",
                kind="fusion",
                version="1.0.0",
                provides=("fusion",),
                requires=("builtin.sensor_input",),
                factory=lambda ctx, _params: BuiltinFusionPlugin(
                    context=ctx,
                    config=FusionConfig.from_env(),
                    _state=FusionStateStore(),
                ),
            ),
            PluginSpec(
                name="builtin.render_policy_v3",
                kind="render_policy",
                version="1.0.0",
                provides=("render_policy",),
                requires=(),
                factory=lambda ctx, _params: BuiltinRenderPolicyPlugin(
                    context=ctx,
                    _result=load_effective_render_policy_result(),
                ),
            ),
            PluginSpec(
                name="builtin.render_backends",
                kind="render_backend",
                version="1.0.0",
                provides=("render_backend",),
                requires=(),
                factory=lambda _ctx, _params: BuiltinRenderBackendPlugin(
                    unicode_backend=UnicodeRadarBackend(),
                    kitty_backend=KittyRadarBackend(),
                    sixel_backend=SixelRadarBackend(),
                ),
            ),
            PluginSpec(
                name="builtin.situational_v2",
                kind="situational_analysis",
                version="1.0.0",
                provides=("situational_analysis",),
                requires=(),
                factory=lambda ctx, _params: BuiltinSituationalAnalysisPlugin(engine=RadarSituationEngine(clock=ctx.clock)),
            ),
            PluginSpec(
                name="builtin.session_transport",
                kind="session_transport",
                version="1.0.0",
                provides=("session_transport",),
                requires=(),
                factory=lambda _ctx, _params: BuiltinSessionTransportPlugin(),
            ),
            PluginSpec(
                name="builtin.input_router",
                kind="input_router",
                version="1.0.0",
                provides=("input_router",),
                requires=(),
                factory=lambda _ctx, _params: BuiltinInputRouterPlugin(),
            ),
        ]
    )
