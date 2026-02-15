"""Distributed multi-console session server (TCP JSON-lines transport)."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from typing import TYPE_CHECKING

from .event_store import EventStore, TruthState
from .radar_backends import RadarPoint, RadarScene
from .radar_controls import RadarInputController, RadarMouseEvent

if TYPE_CHECKING:
    from .radar_pipeline import RadarPipeline


@dataclass
class _ClientConn:
    client_id: str
    role: str
    conn: socket.socket
    lock: threading.Lock = field(default_factory=threading.Lock)

    def send(self, payload: dict[str, Any]) -> bool:
        raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self.lock:
            try:
                self.conn.sendall(raw)
                return True
            except OSError:
                return False


class SessionServer:
    """Server mode: owns pipeline and streams shared state/events to clients."""

    def __init__(
        self,
        *,
        pipeline: RadarPipeline,
        event_store: EventStore,
        host: str = "127.0.0.1",
        port: int = 8765,
        snapshot_hz: float = 8.0,
        lease_ms: int = 5000,
        lease_check_ms: int = 100,
    ) -> None:
        self.pipeline = pipeline
        self.event_store = event_store
        self.host = host
        self.port = int(port)
        self.snapshot_hz = max(1.0, float(snapshot_hz))
        self.lease_ms = max(500, int(lease_ms))
        self.lease_check_ms = max(50, int(lease_check_ms))
        self._controller = RadarInputController()

        self._sock: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._publisher_thread: threading.Thread | None = None
        self._lease_thread: threading.Thread | None = None
        self._running = threading.Event()
        self._stop = threading.Event()

        self._clients_lock = threading.Lock()
        self._clients: dict[str, _ClientConn] = {}

        self._control_lock = threading.Lock()
        self._controller_client_id = ""
        self._controller_deadline = 0.0

        self._seen_event_ids: deque[str] = deque(maxlen=4000)
        self._seen_event_ids_set: set[str] = set()

    def start(self) -> None:
        if self._running.is_set():
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(16)
        sock.settimeout(0.2)
        self._sock = sock
        self.host, self.port = sock.getsockname()[0], int(sock.getsockname()[1])

        self._stop.clear()
        self._running.set()
        self._accept_thread = threading.Thread(target=self._accept_loop, name="session-server-accept", daemon=True)
        self._publisher_thread = threading.Thread(
            target=self._publisher_loop,
            name="session-server-publisher",
            daemon=True,
        )
        self._lease_thread = threading.Thread(
            target=self._lease_loop,
            name="session-server-lease",
            daemon=True,
        )
        self._accept_thread.start()
        self._publisher_thread.start()
        self._lease_thread.start()

    def stop(self) -> None:
        if not self._running.is_set():
            return
        self._running.clear()
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        with self._clients_lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            try:
                client.conn.close()
            except OSError:
                pass
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=1.0)
        if self._publisher_thread is not None:
            self._publisher_thread.join(timeout=1.0)
        if self._lease_thread is not None:
            self._lease_thread.join(timeout=1.0)

    def __enter__(self) -> "SessionServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    @property
    def address(self) -> tuple[str, int]:
        return self.host, self.port

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            thread = threading.Thread(target=self._client_loop, args=(conn,), name="session-server-client", daemon=True)
            thread.start()

    def _client_loop(self, conn: socket.socket) -> None:
        conn.settimeout(1.0)
        try:
            reader = conn.makefile("r", encoding="utf-8")
        except OSError:
            conn.close()
            return

        client_ref: _ClientConn | None = None
        try:
            hello = self._read_message(reader)
            if hello is None:
                return
            if str(hello.get("type", "")).upper() != "HELLO":
                self._send_raw(conn, {"type": "ERROR", "code": "protocol", "message": "HELLO required"})
                return
            client_id = str(hello.get("client_id", "")).strip() or f"client-{id(conn)}"
            role = str(hello.get("role", "viewer")).strip() or "viewer"
            client_ref = _ClientConn(client_id=client_id, role=role, conn=conn)
            with self._clients_lock:
                self._clients[client_id] = client_ref

            client_ref.send(
                {
                    "type": "HELLO",
                    "client_id": client_id,
                    "role": role,
                    "session": {"mode": "server", "host": self.host, "port": self.port},
                }
            )

            # Send initial snapshot immediately.
            client_ref.send(self._build_snapshot_message())

            while not self._stop.is_set():
                msg = self._read_message(reader)
                if msg is None:
                    break
                self._handle_client_message(client_ref, msg)
        finally:
            if client_ref is not None:
                self._unregister_client(client_ref.client_id)
            try:
                reader.close()
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass

    def _read_message(self, reader) -> dict[str, Any] | None:
        try:
            line = reader.readline()
        except OSError:
            return None
        if not line:
            return None
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def _send_raw(self, conn: socket.socket, payload: dict[str, Any]) -> None:
        try:
            conn.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        except OSError:
            return

    def _handle_client_message(self, client: _ClientConn, msg: dict[str, Any]) -> None:
        mtype = str(msg.get("type", "")).upper()
        now_ts = self._now_ts()
        if mtype == "HEARTBEAT":
            with self._control_lock:
                if client.client_id == self._controller_client_id:
                    self._controller_deadline = now_ts + (float(self.lease_ms) / 1000.0)
            return
        if mtype == "CONTROL_REQUEST":
            self._request_control(client_id=client.client_id, now_ts=now_ts)
            return
        if mtype == "CONTROL_RELEASE":
            self._release_control(client_id=client.client_id, reason="RELEASED")
            return
        if mtype in {"INPUT", "INPUT_EVENT"}:
            self._apply_input(client, msg)
            return
        client.send({"type": "ERROR", "code": "unsupported", "message": f"unsupported type: {mtype}"})

    def _request_control(self, *, client_id: str, now_ts: float) -> None:
        with self._control_lock:
            owner = self._controller_client_id
            if owner and owner != client_id and now_ts <= self._controller_deadline:
                self._send_client_error(client_id, code="not_controller", message=f"controller busy: {owner}")
                return
            self._controller_client_id = client_id
            self._controller_deadline = now_ts + (float(self.lease_ms) / 1000.0)
        self._emit_control_event("CONTROL_GRANTED", client_id=client_id, reason="LEASE_GRANTED")
        self._broadcast(
            {
                "type": "CONTROL_GRANTED",
                "client_id": client_id,
                "lease_ms": self.lease_ms,
            }
        )

    def _release_control(self, *, client_id: str, reason: str) -> None:
        with self._control_lock:
            if client_id != self._controller_client_id:
                return
            self._controller_client_id = ""
            self._controller_deadline = 0.0
        event_type = "CONTROL_REVOKED" if reason == "REVOKED" else "CONTROL_RELEASED"
        self._emit_control_event(event_type, client_id=client_id, reason=reason)
        self._broadcast({"type": "CONTROL_RELEASE", "client_id": client_id, "reason": reason})

    def _apply_input(self, client: _ClientConn, msg: dict[str, Any]) -> None:
        with self._control_lock:
            is_controller = client.client_id == self._controller_client_id
        if not is_controller:
            client.send({"type": "ERROR", "code": "not_controller", "message": "input rejected: not controller"})
            return

        payload = msg.get("event") if isinstance(msg.get("event"), dict) else msg
        kind = str(payload.get("kind", "")).lower()
        if kind == "key":
            key = str(payload.get("key", ""))
            self.pipeline.view_state = self._controller.apply_key(self.pipeline.view_state, key)
        elif kind == "wheel":
            delta = float(payload.get("delta", 0.0))
            action = self._controller.handle_mouse(RadarMouseEvent(kind="wheel", delta=delta))
            self.pipeline.view_state = self._controller.apply_action(self.pipeline.view_state, action)
        elif kind == "drag":
            action = self._controller.handle_mouse(
                RadarMouseEvent(
                    kind="drag",
                    button="left",
                    is_button_down=True,
                    dx=float(payload.get("dx", 0.0)),
                    dy=float(payload.get("dy", 0.0)),
                )
            )
            self.pipeline.view_state = self._controller.apply_action(self.pipeline.view_state, action)
        elif kind == "click":
            scene = self._scene_from_events(self.event_store.recent(300))
            action = self._controller.handle_mouse(
                RadarMouseEvent(
                    kind="click",
                    button="left",
                    x=float(payload.get("x", 0.0)),
                    y=float(payload.get("y", 0.0)),
                )
            )
            self.pipeline.view_state = self._controller.apply_action(self.pipeline.view_state, action, scene=scene)
        else:
            client.send({"type": "ERROR", "code": "bad_input", "message": f"unsupported input kind: {kind}"})
            return

    def _publisher_loop(self) -> None:
        interval = 1.0 / self.snapshot_hz
        while not self._stop.wait(timeout=interval):
            self._broadcast_events()
            self._broadcast(self._build_snapshot_message())

    def _lease_loop(self) -> None:
        interval = max(0.05, float(self.lease_check_ms) / 1000.0)
        while not self._stop.wait(timeout=interval):
            self._expire_control_if_needed()

    def _broadcast_events(self) -> None:
        events = self.event_store.recent(500)
        allowed_subsystems = {"RADAR", "FUSION", "SITUATION", "FSM", "ACTUATORS", "SESSION"}
        for event in events:
            if event.subsystem not in allowed_subsystems:
                continue
            if event.event_id in self._seen_event_ids_set:
                continue
            self._seen_event_ids.append(event.event_id)
            self._seen_event_ids_set.add(event.event_id)
            while len(self._seen_event_ids_set) > self._seen_event_ids.maxlen:
                evicted = self._seen_event_ids.popleft()
                self._seen_event_ids_set.discard(evicted)
            self._broadcast(
                {
                    "type": "EVENT",
                    "ts": float(event.ts),
                    "subsystem": event.subsystem,
                    "event_type": event.event_type,
                    "payload": dict(event.payload),
                    "truth_state": event.truth_state.value,
                    "reason": event.reason,
                }
            )

    def _build_snapshot_message(self) -> dict[str, Any]:
        events = self.event_store.recent(300)
        scene = self._scene_from_events(events)
        now_ts = self._now_ts()
        with self._control_lock:
            owner = self._controller_client_id
            lease_left = max(0, int((self._controller_deadline - now_ts) * 1000.0)) if owner else 0
        return {
            "type": "STATE_SNAPSHOT",
            "ts": float(now_ts),
            "scene": self._scene_to_json(scene),
            "hud": self._build_hud(events),
            "truth_state": scene.truth_state,
            "control": {"controller": owner, "lease_ms": lease_left},
        }

    def _build_hud(self, events) -> dict[str, Any]:
        fsm_state = "UNKNOWN"
        for event in reversed(events):
            if event.subsystem == "FSM" and event.event_type == "FSM_TRANSITION":
                fsm_state = str(event.payload.get("to_state") or event.payload.get("state") or "UNKNOWN")
                break
        return {
            "fsm_state": fsm_state,
            "view": self.pipeline.view_state.view,
            "selected_target": self.pipeline.view_state.selected_target_id,
            "safe_mode_reason": self._extract_safe_mode_reason(events),
        }

    def _extract_safe_mode_reason(self, events) -> str:
        for event in reversed(events):
            if event.subsystem == "FSM" and event.event_type in {"SAFE_MODE_ENTER", "FSM_TRANSITION"}:
                reason = str(event.payload.get("reason", "")).strip()
                if reason:
                    return reason
        return ""

    def _scene_to_json(self, scene: RadarScene) -> dict[str, Any]:
        return {
            "ok": bool(scene.ok),
            "reason": scene.reason,
            "truth_state": scene.truth_state,
            "is_fallback": bool(scene.is_fallback),
            "points": [self._point_to_json(point) for point in scene.points],
        }

    @staticmethod
    def _point_to_json(point: RadarPoint) -> dict[str, Any]:
        payload = {
            "x": float(point.x),
            "y": float(point.y),
            "z": float(point.z),
            "vr_mps": float(point.vr_mps),
            "metadata": dict(point.metadata),
        }
        return payload

    def _scene_from_events(self, events: list[Any]) -> RadarScene:
        points: list[RadarPoint] = []
        truth_state = "NO_DATA"
        reason = "NO_DATA"
        is_fallback = False
        for event in reversed(events):
            event_type = getattr(event, "event_type", "")
            payload = getattr(event, "payload", {})
            if event_type != "FUSED_TRACK_UPDATED" or not isinstance(payload, dict):
                continue
            pos = payload.get("pos")
            if not isinstance(pos, list) or len(pos) < 2:
                continue
            vel = payload.get("vel")
            vr = 0.0
            if isinstance(vel, list) and len(vel) >= 2:
                try:
                    vx = float(vel[0])
                    vy = float(vel[1])
                except Exception:
                    vx = 0.0
                    vy = 0.0
                vr = (vx * vx + vy * vy) ** 0.5
            metadata = {"target_id": str(payload.get("fused_id", ""))}
            points.append(
                RadarPoint(
                    x=float(pos[0]),
                    y=float(pos[1]),
                    z=0.0,
                    vr_mps=vr,
                    metadata=metadata,
                )
            )
        if events:
            latest = events[-1]
            state = getattr(latest, "truth_state", TruthState.NO_DATA)
            truth_state = getattr(state, "value", str(state))
            reason = getattr(latest, "reason", "OK")
            is_fallback = truth_state == TruthState.FALLBACK.value
        return RadarScene(
            ok=bool(points),
            reason=reason if points else "NO_DATA",
            truth_state=truth_state if points else "NO_DATA",
            is_fallback=is_fallback,
            points=points,
        )

    def _expire_control_if_needed(self) -> None:
        now_ts = self._now_ts()
        expired_client = ""
        with self._control_lock:
            if self._controller_client_id and now_ts > self._controller_deadline:
                expired_client = self._controller_client_id
                self._controller_client_id = ""
                self._controller_deadline = 0.0
        if expired_client:
            self._emit_control_event("CONTROL_EXPIRED", client_id=expired_client, reason="HEARTBEAT_TIMEOUT")
            self._broadcast({"type": "CONTROL_EXPIRED", "client_id": expired_client, "reason": "EXPIRED"})

    def _send_client_error(self, client_id: str, *, code: str, message: str) -> None:
        with self._clients_lock:
            client = self._clients.get(client_id)
        if client is not None:
            client.send({"type": "ERROR", "code": code, "message": message})

    def _broadcast(self, payload: dict[str, Any]) -> None:
        with self._clients_lock:
            clients = list(self._clients.values())
        dead: list[str] = []
        for client in clients:
            if not client.send(payload):
                dead.append(client.client_id)
        for client_id in dead:
            self._unregister_client(client_id)

    def _unregister_client(self, client_id: str) -> None:
        with self._clients_lock:
            client = self._clients.pop(client_id, None)
        if client is not None:
            try:
                client.conn.close()
            except OSError:
                pass
        self._release_control(client_id=client_id, reason="REVOKED")

    def _emit_control_event(self, event_type: str, *, client_id: str, reason: str) -> None:
        self.event_store.append_new(
            subsystem="SESSION",
            event_type=event_type,
            payload={"client_id": client_id, "lease_ms": self.lease_ms},
            truth_state=TruthState.OK,
            reason=reason,
        )

    @staticmethod
    def _now_ts() -> float:
        return time.monotonic()
