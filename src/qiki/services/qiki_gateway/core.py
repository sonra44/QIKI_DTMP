"""QIKI Gateway — ядро политики (M3, F5 design §6).

Чистая логика без HTTP/сети: конфигурация, авторизация виртуальных ключей,
лимиты (audit-only vs enforce), редакция секрета, сборка аудит-событий.

Инвариант безопасности: РЕАЛЬНЫЙ ключ провайдера живёт ТОЛЬКО в окружении
gateway (real_api_key). Клиенты предъявляют ВИРТУАЛЬНЫЙ ключ; реальный ключ
никогда не уходит клиенту и не попадает в аудит/логи (redact_secret).

Fail-closed: без реального ключа gateway не обслуживает (see is_serviceable).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Sequence

# audit-only неделя (плана §6, M3): нарушения фиксируются, но НЕ блокируются.
MODE_AUDIT = "audit"
MODE_ENFORCE = "enforce"

REASON_NO_VKEY = "GATEWAY_VKEY_MISSING"
REASON_BAD_VKEY = "GATEWAY_VKEY_INVALID"
REASON_RATE = "GATEWAY_RATE_EXCEEDED"
REASON_TOKENS = "GATEWAY_TOKENS_EXCEEDED"
REASON_CONCURRENCY = "GATEWAY_CONCURRENCY_EXCEEDED"
REASON_NO_UPSTREAM_KEY = "GATEWAY_UPSTREAM_KEY_MISSING"


@dataclass(frozen=True)
class GatewayConfig:
    real_api_key: str
    upstream_base_url: str
    virtual_keys: frozenset[str]
    mode: str
    requests_per_min: int
    max_tokens_per_request: int
    max_concurrency: int

    @staticmethod
    def from_env() -> "GatewayConfig":
        raw_vkeys = os.getenv("QIKI_GATEWAY_VKEYS", "").strip()
        vkeys = frozenset(v.strip() for v in raw_vkeys.split(",") if v.strip())
        mode = os.getenv("QIKI_GATEWAY_MODE", MODE_AUDIT).strip().lower()
        if mode not in {MODE_AUDIT, MODE_ENFORCE}:
            mode = MODE_AUDIT
        return GatewayConfig(
            real_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            upstream_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
            virtual_keys=vkeys,
            mode=mode,
            requests_per_min=int(os.getenv("QIKI_GATEWAY_REQUESTS_PER_MIN", "60")),
            max_tokens_per_request=int(os.getenv("QIKI_GATEWAY_MAX_TOKENS", "2000")),
            max_concurrency=int(os.getenv("QIKI_GATEWAY_MAX_CONCURRENCY", "4")),
        )

    def is_serviceable(self) -> bool:
        """Fail-closed: без реального ключа и хотя бы одного vkey не обслуживаем."""
        return bool(self.real_api_key) and bool(self.virtual_keys)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    violations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def hard_denied(self) -> bool:
        """Жёсткий отказ (auth) — независимо от режима."""
        return not self.allowed


def authorize(config: GatewayConfig, presented_vkey: str | None) -> Decision:
    """Авторизация виртуального ключа. Auth-отказ жёсткий в ЛЮБОМ режиме."""
    if not presented_vkey:
        return Decision(allowed=False, violations=(REASON_NO_VKEY,))
    if presented_vkey not in config.virtual_keys:
        return Decision(allowed=False, violations=(REASON_BAD_VKEY,))
    return Decision(allowed=True)


def check_limits(
    config: GatewayConfig,
    *,
    requested_max_tokens: int,
    current_concurrency: int,
    requests_in_last_min: int,
) -> Decision:
    """Проверка лимитов. В audit-режиме нарушения НЕ блокируют (allowed=True),
    но всегда перечислены в violations для аудита. В enforce — блокируют.
    """
    violations: list[str] = []
    if requests_in_last_min >= config.requests_per_min:
        violations.append(REASON_RATE)
    if requested_max_tokens > config.max_tokens_per_request:
        violations.append(REASON_TOKENS)
    if current_concurrency >= config.max_concurrency:
        violations.append(REASON_CONCURRENCY)

    if not violations:
        return Decision(allowed=True)
    allowed = config.mode == MODE_AUDIT  # audit-only неделя: пропускаем, но пишем
    return Decision(allowed=allowed, violations=tuple(violations))


def redact_secret(text: str, secret: str) -> str:
    """Вырезать реальный ключ из любой строки перед логом/аудитом/ответом клиенту."""
    if secret and secret in text:
        return text.replace(secret, "***REDACTED***")
    return text


def build_audit_event(
    *,
    vkey_fingerprint: str,
    decision: Decision,
    mode: str,
    requested_max_tokens: int,
) -> dict[str, object]:
    """Аудит-событие обращения к gateway. Секрет сюда не попадает по построению
    (только fingerprint виртуального ключа, не сам ключ и не реальный ключ).
    """
    return {
        "event_type": "GATEWAY_REQUEST",
        "source": "qiki_gateway",
        "mode": mode,
        "vkey_fingerprint": vkey_fingerprint,
        "allowed": decision.allowed,
        "violations": list(decision.violations),
        "requested_max_tokens": requested_max_tokens,
    }


def vkey_fingerprint(presented_vkey: str | None) -> str:
    """Короткий необоротимый отпечаток vkey для аудита (не сам ключ)."""
    import hashlib

    if not presented_vkey:
        return "none"
    return "vk_" + hashlib.sha256(presented_vkey.encode("utf-8")).hexdigest()[:12]


def bearer_from_header(auth_header: str | None) -> str | None:
    """Достать токен из 'Authorization: Bearer <token>'."""
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def upstream_headers(config: GatewayConfig, extra: Sequence[tuple[str, str]] = ()) -> dict[str, str]:
    """Заголовки к реальному провайдеру: реальный ключ подставляется ТОЛЬКО здесь."""
    headers = {"Authorization": f"Bearer {config.real_api_key}", "Content-Type": "application/json"}
    for key, value in extra:
        headers[key] = value
    return headers
