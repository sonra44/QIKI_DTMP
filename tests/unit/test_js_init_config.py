
from tools.js_init import (
    JsConfig,
    JsConsumerConfig,
    build_stream_params,
    build_consumer_params,
    _parse_consumer_env,
)


def test_build_stream_params_basic():
    cfg = JsConfig(
        nats_url="nats://localhost:4222",
        stream="QIKI_RADAR_V1",
        subjects=["qiki.radar.v1.*"],
        duplicate_window_sec=120,
        max_bytes=10 * 1024 * 1024,
        max_age_sec=3600,
    )
    params = build_stream_params(cfg)
    assert params["name"] == "QIKI_RADAR_V1"
    assert params["subjects"] == ["qiki.radar.v1.*"]
    assert params["duplicate_window"] == 120
    assert params["max_bytes"] == 10 * 1024 * 1024
    assert params["max_age"] == 3600


def test_parse_consumer_env_defaults(monkeypatch):
    monkeypatch.delenv("RADAR_CONSUMER_ACK_WAIT_SEC", raising=False)
    monkeypatch.delenv("RADAR_CONSUMER_MAX_DELIVER", raising=False)
    monkeypatch.delenv("RADAR_CONSUMER_MAX_ACK_PENDING", raising=False)
    monkeypatch.delenv("RADAR_FRAMES_SUBJECT", raising=False)
    monkeypatch.delenv("RADAR_TRACKS_SUBJECT", raising=False)
    monkeypatch.delenv("RADAR_FRAMES_DURABLE", raising=False)
    monkeypatch.delenv("RADAR_TRACKS_DURABLE", raising=False)

    consumers = _parse_consumer_env("QIKI_RADAR_V1")
    assert len(consumers) == 2

    frames, tracks = consumers
    assert isinstance(frames, JsConsumerConfig)
    assert frames.stream == "QIKI_RADAR_V1"
    assert frames.durable_name == "radar_frames_pull"
    assert frames.filter_subject == "qiki.radar.v1.frames"
    assert frames.ack_wait_sec == 30
    assert frames.max_deliver == 5
    assert frames.max_ack_pending == 256

    assert tracks.durable_name == "radar_tracks_pull"
    assert tracks.filter_subject == "qiki.radar.v1.tracks"


def test_parse_consumer_env_overrides(monkeypatch):
    monkeypatch.setenv("RADAR_CONSUMER_ACK_WAIT_SEC", "45")
    monkeypatch.setenv("RADAR_CONSUMER_MAX_DELIVER", "7")
    monkeypatch.setenv("RADAR_CONSUMER_MAX_ACK_PENDING", "512")
    monkeypatch.setenv("RADAR_FRAMES_SUBJECT", "custom.frames")
    monkeypatch.setenv("RADAR_TRACKS_SUBJECT", "custom.tracks")
    monkeypatch.setenv("RADAR_FRAMES_DURABLE", "frames_durable")
    monkeypatch.setenv("RADAR_TRACKS_DURABLE", "tracks_durable")

    consumers = _parse_consumer_env("STREAM")
    frames, tracks = consumers

    assert frames.ack_wait_sec == 45
    assert frames.max_deliver == 7
    assert frames.max_ack_pending == 512
    assert frames.filter_subject == "custom.frames"
    assert frames.durable_name == "frames_durable"
    assert tracks.filter_subject == "custom.tracks"
    assert tracks.durable_name == "tracks_durable"


def test_build_consumer_params_uses_timedelta():
    consumer = JsConsumerConfig(
        stream="STREAM",
        durable_name="durable",
        filter_subject="subject",
        ack_wait_sec=45,
        max_deliver=7,
        max_ack_pending=512,
    )
    params = build_consumer_params(consumer)

    assert params["durable_name"] == "durable"
    assert params["filter_subject"] == "subject"
    assert params["ack_wait"] == 45
    assert params["max_deliver"] == 7
    assert params["max_ack_pending"] == 512
