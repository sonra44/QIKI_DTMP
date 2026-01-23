from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import unquote
from typing import Any, Callable


class BiosHttpHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for q-bios-service (stdlib-only)."""

    server_version = "q-bios-service/0.1"

    def __init__(
        self,
        *args: Any,
        get_status_payload: Callable[[], dict[str, Any]],
        get_component_payload: Callable[[str], dict[str, Any]],
        reload_config: Callable[[], dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        self._get_status_payload = get_status_payload
        self._get_component_payload = get_component_payload
        self._reload_config = reload_config
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Keep logs quiet; container stdout is already noisy under compose.
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if self.path == "/bios/status":
            self._send_json(HTTPStatus.OK, self._get_status_payload())
            return
        if self.path.startswith("/bios/component/"):
            raw = self.path.removeprefix("/bios/component/")
            device_id = unquote(raw).strip()
            if not device_id:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing_component_id"})
                return
            payload = self._get_component_payload(device_id)
            status = HTTPStatus.OK if payload.get("ok") else HTTPStatus.NOT_FOUND
            self._send_json(status, payload)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/bios/reload":
            payload = self._reload_config()
            self._send_json(HTTPStatus.OK, payload)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
