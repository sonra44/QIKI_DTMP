"""M3: HTTP-слой gateway с fake upstream — сквозной контракт безопасности."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer


from qiki.services.qiki_gateway.core import MODE_AUDIT, MODE_ENFORCE, GatewayConfig
from qiki.services.qiki_gateway.handler import GatewayState, make_handler

REAL_KEY = "sk-REAL-secret-must-not-leak"
VKEY = "vk-alpha"


def _cfg(mode=MODE_AUDIT, real_key=REAL_KEY, vkeys=(VKEY,), max_tokens=2000) -> GatewayConfig:
    return GatewayConfig(
        real_api_key=real_key,
        upstream_base_url="https://upstream.invalid/v1",
        virtual_keys=frozenset(vkeys),
        mode=mode,
        requests_per_min=60,
        max_tokens_per_request=max_tokens,
        max_concurrency=4,
    )


class _CapturingUpstream:
    """Фейковый провайдер: запоминает заголовки/тело, отвечает фиксировано."""

    def __init__(self, response=None, status=200):
        self.seen_headers = None
        self.seen_body = None
        self._response = response if response is not None else {"output": [{"type": "message"}]}
        self._status = status

    def __call__(self, url, headers, body, timeout_s):
        self.seen_headers = dict(headers)
        self.seen_body = body
        return self._status, json.dumps(self._response).encode("utf-8")


def _serve(config, upstream):
    state = GatewayState()
    handler = make_handler(config, state, forwarder=upstream, now_fn=time.time)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _post(server, *, path="/v1/responses", auth=f"Bearer {VKEY}", body=None):
    host, port = server.server_address
    data = json.dumps(body or {"max_output_tokens": 100}).encode("utf-8")
    req = urllib.request.Request(f"http://{host}:{port}{path}", data=data, method="POST")
    if auth is not None:
        req.add_header("Authorization", auth)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:  # type: ignore[name-defined]
        return exc.code, exc.read()


def test_valid_vkey_forwards_with_real_key_client_never_sees_it():
    upstream = _CapturingUpstream()
    server, _ = _serve(_cfg(), upstream)
    try:
        status, body = _post(server)
        assert status == 200
        # Реальный ключ ушёл ТОЛЬКО вверх:
        assert upstream.seen_headers["Authorization"] == f"Bearer {REAL_KEY}"
        # Клиент прислал только виртуальный ключ, реальный в теле ответа не течёт:
        assert REAL_KEY not in body.decode("utf-8")
    finally:
        server.shutdown()


def test_missing_vkey_rejected_401():
    upstream = _CapturingUpstream()
    server, _ = _serve(_cfg(), upstream)
    try:
        status, _ = _post(server, auth=None)
        assert status == 401
        assert upstream.seen_headers is None  # до upstream не дошло
    finally:
        server.shutdown()


def test_forged_vkey_rejected_401():
    upstream = _CapturingUpstream()
    server, _ = _serve(_cfg(), upstream)
    try:
        status, _ = _post(server, auth="Bearer vk-forged")
        assert status == 401
        assert upstream.seen_headers is None
    finally:
        server.shutdown()


def test_enforce_mode_blocks_oversized_tokens_429():
    upstream = _CapturingUpstream()
    server, _ = _serve(_cfg(mode=MODE_ENFORCE, max_tokens=500), upstream)
    try:
        status, _ = _post(server, body={"max_output_tokens": 100000})
        assert status == 429
        assert upstream.seen_headers is None  # заблокировано ДО upstream
    finally:
        server.shutdown()


def test_audit_mode_passes_oversized_but_forwards():
    upstream = _CapturingUpstream()
    server, _ = _serve(_cfg(mode=MODE_AUDIT, max_tokens=500), upstream)
    try:
        status, _ = _post(server, body={"max_output_tokens": 100000})
        assert status == 200  # audit-only неделя: пропустили
        assert upstream.seen_headers is not None  # дошло до upstream
    finally:
        server.shutdown()


def test_not_serviceable_without_real_key_503():
    upstream = _CapturingUpstream()
    server, _ = _serve(_cfg(real_key=""), upstream)
    try:
        status, _ = _post(server)
        assert status == 503
        assert upstream.seen_headers is None
    finally:
        server.shutdown()


def test_healthz_reports_mode_without_secret():
    server, _ = _serve(_cfg(), _CapturingUpstream())
    try:
        host, port = server.server_address
        with urllib.request.urlopen(f"http://{host}:{port}/healthz", timeout=5) as resp:
            payload = json.loads(resp.read())
        assert payload["ok"] is True
        assert payload["serviceable"] is True
        assert REAL_KEY not in json.dumps(payload)
    finally:
        server.shutdown()
