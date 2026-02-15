from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

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

    client_a = SessionClient(host=host, port=port, client_id="client-a", role="controller")
    client_b = SessionClient(host=host, port=port, client_id="client-b", role="controller")
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

    client_a = SessionClient(host=host, port=port, client_id="client-a", role="controller")
    client_b = SessionClient(host=host, port=port, client_id="client-b", role="controller")
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

    client = SessionClient(host=host, port=port, client_id="client-a", role="controller")
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


def test_auth_required_rejects_bad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_SESSION_AUTH", "1")
    monkeypatch.setenv("QIKI_SESSION_TOKEN", "secret-token")
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=10.0)
    server.start()
    host, port = server.address

    bad_client = SessionClient(
        host=host,
        port=port,
        client_id="bad-client",
        role="controller",
        token="wrong-token",
    )
    bad_client.connect()
    try:
        assert _wait_until(lambda: any(err.get("code") == "auth_failed" for err in bad_client.recent_errors()))
        assert bad_client.session_lost
        assert any(event.event_type == "SESSION_CLIENT_AUTH_FAILED" for event in store.filter(subsystem="SESSION"))
    finally:
        bad_client.close()
        server.stop()
        pipeline.close()


def test_role_downgrade_non_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_SESSION_ALLOWED_ROLES", "viewer,controller")
    monkeypatch.delenv("QIKI_STRICT_MODE", raising=False)
    monkeypatch.delenv("QIKI_SESSION_STRICT", raising=False)

    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=10.0)
    server.start()
    host, port = server.address

    client = SessionClient(host=host, port=port, client_id="client-x", role="admin")
    client.connect()
    try:
        assert _wait_until(lambda: bool(client.latest_snapshot()))
        role_events = [
            event
            for event in store.filter(subsystem="SESSION")
            if event.event_type == "SESSION_ROLE_DOWNGRADED"
        ]
        assert role_events
        assert role_events[-1].payload.get("granted") == "viewer"
    finally:
        client.close()
        server.stop()
        pipeline.close()


def test_role_strict_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_SESSION_ALLOWED_ROLES", "viewer,controller")
    monkeypatch.setenv("QIKI_SESSION_STRICT", "1")
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=10.0)
    server.start()
    host, port = server.address

    client = SessionClient(host=host, port=port, client_id="client-y", role="admin")
    client.connect()
    try:
        assert _wait_until(lambda: any(err.get("code") == "role_forbidden" for err in client.recent_errors()))
        assert _wait_until(lambda: client.session_lost)
    finally:
        client.close()
        server.stop()
        pipeline.close()


def test_rate_limit_non_strict_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_SESSION_MAX_MSGS_PER_SEC", "2")
    monkeypatch.delenv("QIKI_SESSION_STRICT", raising=False)
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=10.0)
    server.start()
    host, port = server.address

    client = SessionClient(host=host, port=port, client_id="client-z", role="controller")
    client.connect()
    try:
        assert _wait_until(lambda: bool(client.latest_snapshot()))
        for _ in range(12):
            client.send_input_event({"kind": "key", "key": "1"})
        assert _wait_until(lambda: any(err.get("code") == "rate_limited" for err in client.recent_errors()))
        assert any(event.event_type == "SESSION_RATE_LIMITED" for event in store.filter(subsystem="SESSION"))
    finally:
        client.close()
        server.stop()
        pipeline.close()


def test_rate_limit_strict_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_SESSION_STRICT", "1")
    monkeypatch.setenv("QIKI_SESSION_MAX_MSGS_PER_SEC", "2")
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=10.0)
    server.start()
    host, port = server.address

    client = SessionClient(host=host, port=port, client_id="strict-client", role="controller")
    client.connect()
    try:
        assert _wait_until(lambda: bool(client.latest_snapshot()))
        for _ in range(16):
            client.send_input_event({"kind": "key", "key": "1"})
        assert _wait_until(lambda: client.session_lost, timeout_s=2.0)
        disconnect_events = [
            event
            for event in store.filter(subsystem="SESSION")
            if event.event_type == "SESSION_CLIENT_DISCONNECTED"
        ]
        assert disconnect_events
    finally:
        client.close()
        server.stop()
        pipeline.close()


def test_first_come_policy_denies_second_controller(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_CONTROL_POLICY", "first_come")
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    _seed_pipeline(pipeline)
    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=20.0)
    server.start()
    host, port = server.address

    client_a = SessionClient(host=host, port=port, client_id="client-a", role="controller")
    client_b = SessionClient(host=host, port=port, client_id="client-b", role="controller")
    client_a.connect()
    client_b.connect()
    try:
        assert _wait_until(lambda: bool(client_a.latest_snapshot()))
        client_a.request_control()
        assert _wait_until(lambda: any(item.get("type") == "CONTROL_GRANTED" for item in client_a.recent_controls()))
        client_b.request_control()
        assert _wait_until(lambda: any(err.get("code") == "control_denied" for err in client_b.recent_errors()))
        denied_events = [event for event in store.filter(subsystem="SESSION") if event.event_type == "CONTROL_DENIED"]
        assert denied_events
    finally:
        client_a.close()
        client_b.close()
        server.stop()
        pipeline.close()


def test_admin_grants_policy_requires_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QIKI_CONTROL_POLICY", "admin_grants")
    monkeypatch.setenv("QIKI_SESSION_ALLOWED_ROLES", "viewer,controller,admin")
    store = EventStore(maxlen=2000, enabled=True)
    pipeline = RadarPipeline(event_store=store)
    _seed_pipeline(pipeline)
    server = SessionServer(pipeline=pipeline, event_store=store, host="127.0.0.1", port=0, snapshot_hz=20.0)
    server.start()
    host, port = server.address

    controller = SessionClient(host=host, port=port, client_id="controller-a", role="controller")
    admin = SessionClient(host=host, port=port, client_id="admin-a", role="admin")
    controller.connect()
    admin.connect()
    try:
        assert _wait_until(lambda: bool(controller.latest_snapshot()))
        controller.request_control()
        assert _wait_until(lambda: any(err.get("code") == "control_denied" for err in controller.recent_errors()))
        admin._send({"type": "CONTROL_GRANT", "client_id": "admin-a", "target_client": "controller-a"})  # noqa: SLF001
        assert _wait_until(
            lambda: any(
                item.get("type") == "CONTROL_GRANTED" and item.get("client_id") == "controller-a"
                for item in controller.recent_controls()
            )
        )
    finally:
        controller.close()
        admin.close()
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
