from __future__ import annotations

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_backends.base import RadarPoint, RadarScene
from qiki.services.q_core_agent.core.radar_ingestion import Observation
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig


def test_invalid_observation_is_dropped_without_crash() -> None:
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=store,
    )
    tracks_by_source = pipeline.ingest_observations(
        [
            Observation(
                source_id="",
                t=123.0,
                track_key="trk-1",
                pos_xy=(1.0, 2.0),
                vel_xy=None,
                quality=0.8,
            )
        ]
    )
    assert tracks_by_source == {}
    dropped = store.filter(subsystem="SENSORS", event_type="SENSOR_OBSERVATION_DROPPED")
    assert dropped
    assert dropped[-1].reason == "MISSING_SOURCE_ID"


def test_multisource_ingestion_keeps_independent_source_tracks() -> None:
    pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    tracks_by_source = pipeline.ingest_observations(
        [
            Observation(
                source_id="radar-a",
                t=10.0,
                track_key="trk-1",
                pos_xy=(10.0, 0.0),
                vel_xy=(1.0, 0.0),
                quality=0.9,
            ),
            Observation(
                source_id="radar-b",
                t=10.1,
                track_key="trk-1",
                pos_xy=(9.8, 0.1),
                vel_xy=(0.9, -0.1),
                quality=0.7,
            ),
        ]
    )
    assert sorted(tracks_by_source.keys()) == ["radar-a", "radar-b"]
    assert len(tracks_by_source["radar-a"]) == 1
    assert len(tracks_by_source["radar-b"]) == 1
    assert tracks_by_source["radar-a"][0].source_track_id == "trk-1"
    assert tracks_by_source["radar-b"][0].source_track_id == "trk-1"


def test_single_source_render_scene_path_remains_compatible() -> None:
    legacy_pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    ingest_pipeline = RadarPipeline(RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False))
    legacy_scene = RadarScene(
        ok=True,
        reason="OK",
        truth_state="OK",
        is_fallback=False,
        points=[
            RadarPoint(
                x=12.0,
                y=3.0,
                z=0.0,
                vr_mps=2.0,
                metadata={"target_id": "trk-legacy"},
            )
        ],
    )
    legacy_output = legacy_pipeline.render_scene(legacy_scene)
    ingest_output = ingest_pipeline.render_observations(
        [
            Observation(
                source_id="radar-primary",
                t=55.0,
                track_key="trk-legacy",
                pos_xy=(12.0, 3.0),
                vel_xy=(2.0, 0.0),
                quality=0.8,
            )
        ]
    )
    assert legacy_output.plan is not None
    assert ingest_output.plan is not None
    assert legacy_output.plan.stats.targets_count == ingest_output.plan.stats.targets_count
    assert legacy_output.plan.stats.lod_level == ingest_output.plan.stats.lod_level


def test_source_track_updated_event_contains_contract_fields() -> None:
    store = EventStore(maxlen=50, enabled=True)
    pipeline = RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=store,
    )
    pipeline.ingest_observations(
        [
            Observation(
                source_id="radar-a",
                t=100.5,
                track_key="trk-42",
                pos_xy=(1.0, 2.0),
                vel_xy=(0.1, -0.2),
                quality=0.6,
            )
        ]
    )
    events = store.filter(subsystem="SENSORS", event_type="SOURCE_TRACK_UPDATED")
    assert events
    payload = events[-1].payload
    for key in ("source_id", "source_track_id", "t", "pos", "quality", "trust"):
        assert key in payload
    assert payload["source_id"] == "radar-a"
    assert payload["source_track_id"] == "trk-42"

