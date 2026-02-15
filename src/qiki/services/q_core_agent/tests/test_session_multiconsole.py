from __future__ import annotations

import json
import time
from pathlib import Path

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_ingestion import Observation
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline
from qiki.services.q_core_agent.core.session_client import SessionClient
from qiki.services.q_core_agent.core.session_server import SessionServer


def _wait_until(predicate, timeout_s: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _seed_pipeline(pipeline: RadarPipeline) -> None:
    now = pipeline._clock.now()  # noqa: SLF001
    pipeline.render_observations(
        [
            Observation(
                source_id="radar",
                t=now,
                track_key="t-1",
                pos_xy=(120.0, -25.0),
                vel_xy=(-1.0, 0.5),
                quality=0.9,
            )
        ]
    )


def test_session_server_two_clients_receive_same_snapshot() -> None:
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    _seed_pipeline(pipeline)

    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=20.0)
    server.start()
    host, port = server.address

    client_a = SessionClient(host=host, port=port, client_id="client-a")
    client_b = SessionClient(host=host, port=port, client_id="client-b")
    client_a.connect()
    client_b.connect()

    try:
        assert _wait_until(lambda: bool(client_a.latest_snapshot().get("scene")))
        assert _wait_until(lambda: bool(client_b.latest_snapshot().get("scene")))
        scene_a = client_a.latest_snapshot().get("scene", {})
        scene_b = client_b.latest_snapshot().get("scene", {})
        assert json.dumps(scene_a, sort_keys=True) == json.dumps(scene_b, sort_keys=True)
    finally:
        client_a.close()
        client_b.close()
        server.stop()
        pipeline.close()


def test_control_handover_rejects_non_controller_input() -> None:
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    _seed_pipeline(pipeline)

    server = SessionServer(
        pipeline=pipeline,
        event_store=store,
        host="127.0.0.1",
        port=0,
        snapshot_hz=20.0,
        lease_ms=500,
    )
    server.start()
    host, port = server.address

    client_a = SessionClient(host=host, port=port, client_id="client-a")
    client_b = SessionClient(host=host, port=port, client_id="client-b")
    client_a.connect()
    client_b.connect()

    try:
        assert _wait_until(lambda: bool(client_a.latest_snapshot().get("scene")))
        client_a.request_control()
        assert _wait_until(lambda: any(item.get("type") == "CONTROL_GRANTED" for item in client_a.recent_controls()))

        client_b.send_input_event({"kind": "key", "key": "1"})
        assert _wait_until(lambda: any(err.get("code") == "not_controller" for err in client_b.recent_errors()))

        client_a.release_control()
        client_b.request_control()
        assert _wait_until(
            lambda: any(
                item.get("type") == "CONTROL_GRANTED" and item.get("client_id") == "client-b"
                for item in client_b.recent_controls()
            )
        )
    finally:
        client_a.close()
        client_b.close()
        server.stop()
        pipeline.close()


def test_session_disconnect_sets_no_data_snapshot() -> None:
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)

    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=10.0)
    server.start()
    host, port = server.address

    client = SessionClient(host=host, port=port, client_id="client-a", event_store=store)
    client.connect()
    assert _wait_until(lambda: bool(client.latest_snapshot()))

    server.stop()
    assert _wait_until(lambda: client.session_lost)
    snapshot = client.latest_snapshot()
    assert snapshot.get("truth_state") == "NO_DATA"
    hud = snapshot.get("hud", {})
    assert isinstance(hud, dict)
    assert hud.get("session") == "SESSION LOST"
    assert any(event.event_type == "SESSION_LOST" for event in store.filter(subsystem="SESSION"))

    client.close()
    pipeline.close()


def test_control_expires_without_heartbeat() -> None:
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    _seed_pipeline(pipeline)

    server = SessionServer(
        pipeline=pipeline,
        event_store=store,
        host="127.0.0.1",
        port=0,
        snapshot_hz=20.0,
        lease_ms=300,
        lease_check_ms=100,
    )
    server.start()
    host, port = server.address

    client = SessionClient(host=host, port=port, client_id="client-a")
    client.connect()

    try:
        client.request_control()
        assert _wait_until(lambda: any(item.get("type") == "CONTROL_GRANTED" for item in client.recent_controls()))
        assert _wait_until(
            lambda: any(item.get("type") == "CONTROL_EXPIRED" for item in client.recent_controls()),
            timeout_s=1.5,
        )
        assert any(event.event_type == "CONTROL_EXPIRED" for event in store.filter(subsystem="SESSION"))
    finally:
        client.close()
        server.stop()
        pipeline.close()


def test_replay_server_streams_events_to_client(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "ts": 1.0,
                        "subsystem": "SENSORS",
                        "event_type": "SOURCE_TRACK_UPDATED",
                        "truth_state": "OK",
                        "reason": "TRACK_UPDATED",
                        "session_id": "replay-test",
                        "payload": {
                            "source_id": "r1",
                            "source_track_id": "t1",
                            "t": 1.0,
                            "pos": [10.0, 5.0],
                            "vel": [0.0, 0.0],
                            "quality": 0.9,
                            "trust": 0.9,
                        },
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "ts": 1.1,
                        "subsystem": "SENSORS",
                        "event_type": "SOURCE_TRACK_UPDATED",
                        "truth_state": "OK",
                        "reason": "TRACK_UPDATED",
                        "session_id": "replay-test",
                        "payload": {
                            "source_id": "r1",
                            "source_track_id": "t1",
                            "t": 1.1,
                            "pos": [9.5, 4.8],
                            "vel": [-0.5, -0.2],
                            "quality": 0.9,
                            "trust": 0.9,
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store, replay_file=str(trace_path))
    # Replay ticks to generate server-streamed telemetry events.
    pipeline.render_observations([])
    pipeline.render_observations([])

    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=20.0)
    server.start()
    host, port = server.address

    client = SessionClient(host=host, port=port, client_id="client-a")
    client.connect()

    try:
        assert _wait_until(
            lambda: any(evt.get("event_type") == "RADAR_RENDER_TICK" for evt in client.recent_events()),
            timeout_s=3.0,
        )
    finally:
        client.close()
        server.stop()
        pipeline.close()
