"""QIKI Gateway HTTP-обработчик (M3): OpenAI-совместимый /v1/responses.

Клиент шлёт виртуальный ключ (Authorization: Bearer <vkey>); gateway
авторизует, проверяет лимиты (audit/enforce), пишет аудит, форвардит к
реальному провайдеру с РЕАЛЬНЫМ ключом (подставляется только здесь).

Секрет не логируется и не возвращается клиенту (redact_secret).
Паттерн http.server — как q_bios_service (без новых зависимостей).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler
from typing import Deque

from qiki.services.qiki_gateway.core import (
    GatewayConfig,
    authorize,
    bearer_from_header,
    build_audit_event,
    check_limits,
    redact_secret,
    upstream_headers,
    vkey_fingerprint,
)
from qiki.services.qiki_gateway.upstream import Forwarder, as_json, http_forward

logger = logging.getLogger("qiki_gateway")

_RESPONSES_PATH = "/v1/responses"
# Allowlist форвардируемых upstream-путей (M3): Responses API (OpenAI-новый) и
# chat/completions (Mercury/Inception и большинство совместимых). Форвардим
# ТОЛЬКО эти — не открытый прокси. Весь конверт auth/rate/audit одинаков.
_FORWARD_PATHS = ("/v1/responses", "/v1/chat/completions")
_HEALTH_PATH = "/healthz"


class GatewayState:
    """Разделяемое состояние лимитов (rate/concurrency) — потокобезопасно."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_times: Deque[float] = deque(maxlen=10_000)
        self._concurrency = 0

    def snapshot_and_enter(self, now: float) -> tuple[int, int]:
        """Вернуть (requests_in_last_min, current_concurrency) и войти в запрос."""
        with self._lock:
            cutoff = now - 60.0
            while self._request_times and self._request_times[0] < cutoff:
                self._request_times.popleft()
            requests_in_last_min = len(self._request_times)
            current_concurrency = self._concurrency
            self._request_times.append(now)
            self._concurrency += 1
            return requests_in_last_min, current_concurrency

    def leave(self) -> None:
        with self._lock:
            self._concurrency = max(0, self._concurrency - 1)


def make_handler(
    config: GatewayConfig,
    state: GatewayState,
    *,
    forwarder: Forwarder = http_forward,
    now_fn=time.time,
    timeout_s: float = 30.0,
) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # заглушаем дефолтный access-log
            return

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_raw(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == _HEALTH_PATH:
                self._send_json(200, {"ok": True, "serviceable": config.is_serviceable(), "mode": config.mode})
                return
            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if self.path not in _FORWARD_PATHS:
                self._send_json(404, {"error": "not_found"})
                return

            # Fail-closed: нет реального ключа/vkeys — не обслуживаем.
            if not config.is_serviceable():
                self._send_json(503, {"error": "gateway_unavailable", "reason": "GATEWAY_NOT_SERVICEABLE"})
                return

            vkey = bearer_from_header(self.headers.get("Authorization"))
            fp = vkey_fingerprint(vkey)

            auth = authorize(config, vkey)
            if auth.hard_denied:
                self._emit_audit(fp, auth, requested_max_tokens=0)
                self._send_json(401, {"error": "unauthorized", "reason": list(auth.violations)})
                return

            length = int(self.headers.get("Content-Length") or 0)
            raw_body = self.rfile.read(length) if length > 0 else b""
            body_json = as_json(raw_body)
            # chat/completions зовёт лимит max_tokens; responses — max_output_tokens
            requested_max_tokens = int(
                body_json.get("max_output_tokens") or body_json.get("max_tokens") or 0
            )

            now = now_fn()
            requests_in_last_min, current_concurrency = state.snapshot_and_enter(now)
            try:
                limit = check_limits(
                    config,
                    requested_max_tokens=requested_max_tokens,
                    current_concurrency=current_concurrency,
                    requests_in_last_min=requests_in_last_min,
                )
                self._emit_audit(fp, limit, requested_max_tokens=requested_max_tokens)
                if not limit.allowed:
                    self._send_json(429, {"error": "rate_limited", "reason": list(limit.violations)})
                    return

                # Форвардим на ТОТ ЖЕ subpath, что запросил клиент (из allowlist).
                subpath = self.path[len("/v1"):]  # "/responses" | "/chat/completions"
                url = f"{config.upstream_base_url.rstrip('/')}{subpath}"
                status, resp_body = forwarder(url, upstream_headers(config), raw_body, timeout_s)
                # Страховка: секрет никогда не должен просочиться в ответ клиенту.
                safe = redact_secret(resp_body.decode("utf-8", "replace"), config.real_api_key)
                self._send_raw(status, safe.encode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("gateway_forward_failed: %s", redact_secret(str(exc), config.real_api_key))
                self._send_json(502, {"error": "upstream_failed"})
            finally:
                state.leave()

        def _emit_audit(self, fp: str, decision, *, requested_max_tokens: int) -> None:
            event = build_audit_event(
                vkey_fingerprint=fp,
                decision=decision,
                mode=config.mode,
                requested_max_tokens=requested_max_tokens,
            )
            logger.info("gateway_audit %s", json.dumps(event, ensure_ascii=False))

    return _Handler
