from __future__ import annotations

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_fusion import (
    FusionConfig,
    FusionStateStore,
    associate,
    fuse,
    fuse_tracks,
)
from qiki.services.q_core_agent.core.radar_ingestion import Observation, ingest_observations
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig


def _tracks(observations: list[Observation]):
    return ingest_observations(observations, event_store=None, emit_observation_rx=False)


def _cfg(**kwargs) -> FusionConfig:
    defaults = dict(
        enabled=True,
        gate_dist_m=50.0,
        gate_vel_mps=20.0,
        min_support=2,
        max_age_s=2.0,
        conflict_dist_m=100.0,
        confirm_frames=1,
        cooldown_s=0.0,
    )
    defaults.update(kwargs)
    return FusionConfig(**defaults)


def test_association_merges_two_sources_for_one_target() -> None:
    tracks = _tracks(
        [
            Observation("radar-a", 100.0, "a-1", (10.0, 5.0), (1.0, 0.1), 0.8),
            Observation("radar-b", 100.2, "b-1", (12.0, 6.0), (1.2, 0.1), 0.7),
        ]
    )
    clusters, stale = associate(tracks, _cfg())
    assert stale == 0
    assert len(clusters) == 1
    assert clusters[0].support_ok is True


def test_association_separates_far_targets() -> None:
    tracks = _tracks(
        [
            Observation("radar-a", 100.0, "a-1", (10.0, 0.0), (1.0, 0.0), 0.8),
            Observation("radar-b", 100.0, "b-1", (300.0, 0.0), (1.0, 0.0), 0.7),
        ]
    )
    clusters, _stale = associate(tracks, _cfg(gate_dist_m=40.0))
    assert len(clusters) == 2


def test_association_respects_velocity_gate() -> None:
    tracks = _tracks(
        [
            Observation("radar-a", 100.0, "a-1", (20.0, 10.0), (2.0, 0.0), 0.8),
            Observation("radar-b", 100.0, "b-1", (21.0, 10.0), (80.0, 0.0), 0.9),
        ]
    )
    clusters, _stale = associate(tracks, _cfg(gate_dist_m=10.0, gate_vel_mps=5.0))
    assert len(clusters) == 2


def test_majority_support_boosts_trust_above_single_source() -> None:
    tracks = _tracks(
        [
            Observation("radar-a", 100.0, "a-1", (10.0, 5.0), (1.0, 0.1), 0.6),
            Observation("radar-b", 100.0, "b-1", (10.5, 5.2), (1.1, 0.1), 0.6),
        ]
    )
    clusters, _stale = associate(tracks, _cfg())
    fused = fuse(clusters, _cfg())
    assert len(fused) == 1
    assert fused[0].trust > 0.6
    assert "LOW_SUPPORT" not in fused[0].flags


def test_low_support_caps_trust_and_sets_flag() -> None:
    tracks = _tracks([Observation("radar-a", 100.0, "a-1", (5.0, 0.0), (0.0, 0.0), 0.95)])
    clusters, _stale = associate(tracks, _cfg(min_support=2))
    fused = fuse(clusters, _cfg(min_support=2))
    assert len(fused) == 1
    assert fused[0].trust <= 0.49
    assert "LOW_SUPPORT" in fused[0].flags


def test_conflict_flag_reduces_trust() -> None:
    tracks = _tracks(
        [
            Observation("radar-a", 100.0, "a-1", (0.0, 0.0), (0.0, 0.0), 0.9),
            Observation("radar-b", 100.0, "b-1", (40.0, 0.0), (0.0, 0.0), 0.9),
        ]
    )
    clusters, _stale = associate(tracks, _cfg(gate_dist_m=50.0, conflict_dist_m=10.0))
    fused = fuse(clusters, _cfg(gate_dist_m=50.0, conflict_dist_m=10.0))
    assert len(fused) == 1
    assert "CONFLICT" in fused[0].flags
    assert fused[0].trust < 0.9


def test_fusion_is_deterministic_for_same_input() -> None:
    tracks = _tracks(
        [
            Observation("radar-b", 100.0, "b-1", (9.9, 0.0), (1.0, 0.0), 0.6),
            Observation("radar-a", 100.0, "a-1", (10.0, 0.1), (1.1, 0.0), 0.8),
        ]
    )
    cfg = _cfg()
    set_one, _ = fuse_tracks(tracks, cfg=cfg, prev_state=FusionStateStore(), now=10.0)
    set_two, _ = fuse_tracks(tracks, cfg=cfg, prev_state=FusionStateStore(), now=10.0)
    assert [track.fused_id for track in set_one.tracks] == [track.fused_id for track in set_two.tracks]
    assert [track.pos_xy for track in set_one.tracks] == [track.pos_xy for track in set_two.tracks]


def test_antiflapping_keeps_fused_id_across_small_reassociation() -> None:
    cfg = _cfg(confirm_frames=1, cooldown_s=0.0)
    frame_one = _tracks(
        [
            Observation("radar-a", 100.0, "a-1", (10.0, 0.0), (1.0, 0.0), 0.8),
            Observation("radar-b", 100.0, "b-1", (10.4, 0.2), (1.0, 0.0), 0.7),
        ]
    )
    frame_two = _tracks(
        [
            Observation("radar-a", 101.0, "a-1", (10.3, 0.1), (1.0, 0.0), 0.8),
            Observation("radar-b", 101.0, "b-2", (10.2, 0.1), (1.0, 0.0), 0.7),
        ]
    )
    set_one, state = fuse_tracks(frame_one, cfg=cfg, prev_state=FusionStateStore(), now=100.0)
    set_two, _ = fuse_tracks(frame_two, cfg=cfg, prev_state=state, now=101.0)
    assert len(set_one.tracks) == 1
    assert len(set_two.tracks) == 1
    assert set_one.tracks[0].fused_id == set_two.tracks[0].fused_id


def test_pipeline_keeps_legacy_behavior_when_fusion_disabled(monkeypatch) -> None:
    monkeypatch.setenv("RADAR_FUSION_ENABLED", "0")
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    output = pipeline.render_observations(
        [
            Observation("radar-a", 100.0, "trk-1", (10.0, 0.0), (1.0, 0.0), 0.8),
            Observation("radar-b", 100.0, "trk-1", (10.1, 0.1), (1.0, 0.0), 0.7),
        ]
    )
    assert output.plan is not None
    assert output.plan.stats.targets_count == 2


def test_pipeline_fusion_enabled_reduces_target_count_and_emits_deduped_events(monkeypatch) -> None:
    monkeypatch.setenv("RADAR_FUSION_ENABLED", "1")
    monkeypatch.setenv("RADAR_FUSION_CONFIRM_FRAMES", "1")
    monkeypatch.setenv("RADAR_FUSION_COOLDOWN_S", "0")
    store = EventStore(maxlen=200, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=store,
    )
    observations = [
        Observation("radar-a", 100.0, "trk-a", (12.0, 5.0), (1.0, 0.0), 0.8),
        Observation("radar-b", 100.0, "trk-b", (11.8, 5.2), (1.1, 0.0), 0.7),
    ]
    output_one = pipeline.render_observations(observations)
    output_two = pipeline.render_observations(observations)

    assert output_one.plan is not None
    assert output_two.plan is not None
    assert output_one.plan.stats.targets_count == 1
    assert output_two.plan.stats.targets_count == 1

    fused_updates = store.filter(subsystem="FUSION", event_type="FUSED_TRACK_UPDATED")
    cluster_events = store.filter(subsystem="FUSION", event_type="FUSION_CLUSTER_BUILT")
    assert len(fused_updates) == 1
    assert len(cluster_events) == 1
