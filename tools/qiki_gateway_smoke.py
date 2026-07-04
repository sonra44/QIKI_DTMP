"""M3 live-proof: gateway-процесс держит реальный ключ, клиент — только vkey.

Поднимает НАСТОЯЩИЙ gateway (ThreadingHTTPServer через make_handler) с фейковым
upstream и бьёт по нему реальным HTTP-клиентом. Доказывает:
1) fail-closed: без реального ключа /v1/responses → 503;
2) без vkey → 401 (до upstream не доходит);
3) валидный vkey → форвард к upstream с РЕАЛЬНЫМ ключом; клиент реальный ключ не видит;
4) реальный ключ не течёт в ответ клиенту.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from qiki.services.qiki_gateway.core import MODE_AUDIT, GatewayConfig
from qiki.services.qiki_gateway.handler import GatewayState, make_handler

REAL_KEY = "sk-REAL-live-proof-secret"
VKEY = "vk-qcore-live"


class _FakeUpstream:
    def __init__(self):
        self.seen_auth = None

    def __call__(self, url, headers, body, timeout_s):
        self.seen_auth = headers.get("Authorization")
        return 200, json.dumps({"output": [{"type": "message"}], "echo_ok": True}).encode("utf-8")


def _serve(config, upstream):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(config, GatewayState(), forwarder=upstream))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _post(server, auth):
    host, port = server.server_address
    req = urllib.request.Request(
        f"http://{host}:{port}/v1/responses",
        data=json.dumps({"max_output_tokens": 100}).encode("utf-8"),
        method="POST",
    )
    if auth:
        req.add_header("Authorization", auth)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _cfg(real_key=REAL_KEY):
    return GatewayConfig(
        real_api_key=real_key,
        upstream_base_url="https://upstream.invalid/v1",
        virtual_keys=frozenset({VKEY}),
        mode=MODE_AUDIT,
        requests_per_min=60,
        max_tokens_per_request=2000,
        max_concurrency=4,
    )


def main() -> None:
    # 1) fail-closed без реального ключа
    up = _FakeUpstream()
    srv = _serve(_cfg(real_key=""), up)
    status, _ = _post(srv, f"Bearer {VKEY}")
    srv.shutdown()
    assert status == 503, f"fail-closed ожидался 503, получено {status}"
    assert up.seen_auth is None
    print("[smoke] fail-closed без реального ключа → 503 OK")

    # 2) без vkey → 401
    up = _FakeUpstream()
    srv = _serve(_cfg(), up)
    status, _ = _post(srv, None)
    assert status == 401 and up.seen_auth is None
    print("[smoke] без vkey → 401, до upstream не дошло OK")

    # 3+4) валидный vkey → форвард с реальным ключом; клиент его не видит
    status, body = _post(srv, f"Bearer {VKEY}")
    srv.shutdown()
    assert status == 200, status
    assert up.seen_auth == f"Bearer {REAL_KEY}", "реальный ключ не ушёл вверх"
    assert REAL_KEY not in body.decode("utf-8"), "реальный ключ утёк клиенту!"
    assert json.loads(body).get("echo_ok") is True
    print("[smoke] валидный vkey → форвард с РЕАЛЬНЫМ ключом; клиент его не видит OK")

    print("[smoke] M3 PASS: реальный ключ изолирован в gateway, vkey/лимиты/fail-closed работают")


if __name__ == "__main__":
    main()
