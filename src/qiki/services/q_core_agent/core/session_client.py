"""Distributed multi-console session client (TCP JSON-lines transport)."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .event_store import EventStore, TruthState


@dataclass
class SessionClientState:
    latest_snapshot: dict[str, Any] = field(default_factory=dict)
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=500))
    errors: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    controls: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    connected: bool = False
    session_lost: bool = False


class SessionClient:
    """Client mode: subscribes to shared session feed and sends control/input messages."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        client_id: str,
        role: str = "viewer",
        token: str = "",
        event_store: EventStore | None = None,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.client_id = client_id
        self.role = (role or "viewer").strip().lower() or "viewer"
        env_token = str(os.getenv("QIKI_SESSION_TOKEN", "")).strip()
        self.token = str(token).strip() or env_token
        self.event_store = event_store

        self._sock: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._state_lock = threading.Lock()
        self._state = SessionClientState()
        self._session_lost_emitted = False

    def connect(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection((self.host, self.port), timeout=2.0)
        sock.settimeout(1.0)
        self._sock = sock
        self._send(
            {
                "type": "HELLO",
                "client_id": self.client_id,
                "role": self.role,
                "token": self.token,
            }
        )
        self._stop.clear()
        self._reader = threading.Thread(target=self._reader_loop, name="session-client-reader", daemon=True)
        self._reader.start()
        with self._state_lock:
            self._state.connected = True
            self._state.session_lost = False
            self._session_lost_emitted = False

    def close(self) -> None:
        self._stop.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if self._reader is not None:
            self._reader.join(timeout=1.0)
        with self._state_lock:
            self._state.connected = False
            self._state.session_lost = True
            if not self._state.latest_snapshot:
                self._state.latest_snapshot = self._session_lost_snapshot()
        self._emit_session_lost(reason="CLIENT_CLOSED")

    def request_control(self) -> None:
        self._send({"type": "CONTROL_REQUEST", "client_id": self.client_id})

    def release_control(self) -> None:
        self._send({"type": "CONTROL_RELEASE", "client_id": self.client_id})

    def send_heartbeat(self) -> None:
        self._send({"type": "HEARTBEAT", "client_id": self.client_id})

    def send_input_event(self, event: dict[str, Any]) -> None:
        self._send({"type": "INPUT_EVENT", "client_id": self.client_id, "event": event})

    def latest_snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            snapshot = dict(self._state.latest_snapshot)
            if not snapshot and self._state.session_lost:
                return self._session_lost_snapshot()
            return snapshot

    def recent_events(self) -> list[dict[str, Any]]:
        with self._state_lock:
            return list(self._state.events)

    def recent_errors(self) -> list[dict[str, Any]]:
        with self._state_lock:
            return list(self._state.errors)

    def recent_controls(self) -> list[dict[str, Any]]:
        with self._state_lock:
            return list(self._state.controls)

    @property
    def session_lost(self) -> bool:
        with self._state_lock:
            return bool(self._state.session_lost)

    def _send(self, payload: dict[str, Any]) -> None:
        if self._sock is None:
            return
        raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            self._sock.sendall(raw)
        except OSError:
            self._mark_session_lost()

    def _reader_loop(self) -> None:
        sock = self._sock
        if sock is None:
            return
        try:
            reader = sock.makefile("r", encoding="utf-8")
        except OSError:
            self._mark_session_lost()
            return
        try:
            while not self._stop.is_set():
                try:
                    line = reader.readline()
                except OSError:
                    break
                if not line:
                    break
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict):
                    continue
                self._ingest_message(msg)
        finally:
            try:
                reader.close()
            except OSError:
                pass
            self._mark_session_lost()

    def _ingest_message(self, message: dict[str, Any]) -> None:
        mtype = str(message.get("type", "")).upper()
        with self._state_lock:
            if mtype == "STATE_SNAPSHOT":
                self._state.latest_snapshot = dict(message)
                self._state.session_lost = False
                return
            if mtype == "EVENT":
                self._state.events.append(dict(message))
                return
            if mtype in {"CONTROL_GRANTED", "CONTROL_RELEASE", "CONTROL_EXPIRED"}:
                self._state.controls.append(dict(message))
                return
            if mtype == "ERROR":
                self._state.errors.append(dict(message))
                code = str(message.get("code", "")).strip().lower()
                if code in {"auth_failed", "role_forbidden", "banned"}:
                    self._state.session_lost = True
                    self._state.latest_snapshot = self._session_lost_snapshot()
                return

    def _mark_session_lost(self) -> None:
        already_lost = False
        with self._state_lock:
            already_lost = bool(self._state.session_lost)
            self._state.connected = False
            self._state.session_lost = True
            self._state.latest_snapshot = self._session_lost_snapshot()
        if not already_lost:
            self._emit_session_lost(reason="DISCONNECTED")

    @staticmethod
    def _session_lost_snapshot() -> dict[str, Any]:
        return {
            "type": "STATE_SNAPSHOT",
            "ts": 0.0,
            "scene": {"ok": False, "points": []},
            "hud": {"session": "SESSION LOST"},
            "truth_state": "NO_DATA",
            "reason": "SESSION_LOST",
        }

    def _emit_session_lost(self, *, reason: str) -> None:
        if self.event_store is None:
            return
        with self._state_lock:
            if self._session_lost_emitted:
                return
            self._session_lost_emitted = True
        self.event_store.append_new(
            subsystem="SESSION",
            event_type="SESSION_LOST",
            payload={"client_id": self.client_id, "ts": time.monotonic(), "reason": reason},
            truth_state=TruthState.NO_DATA,
            reason=reason,
        )
