from __future__ import annotations

import json
import threading
from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from qiki.services.q_bios_service.handlers import BiosHttpHandler


def _request_json(host: str, port: int, method: str, path: str) -> tuple[int, dict]:
    conn = HTTPConnection(host, port, timeout=3)
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        raw = resp.read()
        body = json.loads(raw.decode("utf-8")) if raw else {}
        return resp.status, body
    finally:
        conn.close()


def test_bios_http_endpoints_status_component_reload() -> None:
    payload = {
        "bios_version": "1.0",
        "hardware_profile_hash": "sha256:test",
        "timestamp": "2026-01-01T00:00:00Z",
        "post_results": [
            {"device_id": "motor_left", "device_name": "wheel_motor", "status": 1, "status_message": "OK"},
        ],
    }

    def get_status_payload() -> dict:
        return dict(payload)

    def get_component_payload(device_id: str) -> dict:
        rows = payload.get("post_results", [])
        for row in rows:
            if row.get("device_id") == device_id:
                return {"ok": True, "device": dict(row)}
        return {"ok": False, "error": "component_not_found", "device_id": device_id}

    did_reload = {"value": False}

    def reload_config() -> dict:
        did_reload["value"] = True
        return {"ok": True, "reloaded": True}

    handler_factory = partial(
        BiosHttpHandler,
        get_status_payload=get_status_payload,
        get_component_payload=get_component_payload,
        reload_config=reload_config,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        host, port = server.server_address

        status, body = _request_json(host, port, "GET", "/healthz")
        assert status == 200
        assert body.get("ok") is True

        status, body = _request_json(host, port, "GET", "/bios/status")
        assert status == 200
        assert body.get("bios_version") == "1.0"

        status, body = _request_json(host, port, "GET", "/bios/component/motor_left")
        assert status == 200
        assert body.get("ok") is True
        assert body.get("device", {}).get("device_id") == "motor_left"

        status, body = _request_json(host, port, "GET", "/bios/component/does_not_exist")
        assert status == 404
        assert body.get("ok") is False

        status, body = _request_json(host, port, "POST", "/bios/reload")
        assert status == 200
        assert body.get("ok") is True
        assert did_reload["value"] is True
    finally:
        server.shutdown()
        server.server_close()

