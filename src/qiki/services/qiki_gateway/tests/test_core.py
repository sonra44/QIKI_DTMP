"""M3: тесты ядра gateway — авторизация, лимиты, редакция секрета, аудит."""

from __future__ import annotations

from qiki.services.qiki_gateway.core import (
    MODE_AUDIT,
    MODE_ENFORCE,
    REASON_BAD_VKEY,
    REASON_CONCURRENCY,
    REASON_NO_VKEY,
    REASON_RATE,
    REASON_TOKENS,
    GatewayConfig,
    authorize,
    bearer_from_header,
    build_audit_event,
    check_limits,
    redact_secret,
    upstream_headers,
    vkey_fingerprint,
)


def _cfg(mode=MODE_AUDIT, vkeys=("vk-alpha",), real_key="sk-REAL-secret") -> GatewayConfig:
    return GatewayConfig(
        real_api_key=real_key,
        upstream_base_url="https://api.openai.com/v1",
        virtual_keys=frozenset(vkeys),
        mode=mode,
        requests_per_min=60,
        max_tokens_per_request=2000,
        max_concurrency=4,
    )


def test_authorize_missing_and_bad_vkey_hard_denied():
    cfg = _cfg()
    d_none = authorize(cfg, None)
    assert d_none.hard_denied and REASON_NO_VKEY in d_none.violations
    d_bad = authorize(cfg, "vk-forged")
    assert d_bad.hard_denied and REASON_BAD_VKEY in d_bad.violations


def test_authorize_valid_vkey():
    assert authorize(_cfg(), "vk-alpha").allowed


def test_limits_audit_mode_passes_but_records():
    cfg = _cfg(mode=MODE_AUDIT)
    d = check_limits(cfg, requested_max_tokens=9999, current_concurrency=10, requests_in_last_min=999)
    assert d.allowed is True  # audit-only неделя: пропускаем
    assert set(d.violations) == {REASON_TOKENS, REASON_CONCURRENCY, REASON_RATE}


def test_limits_enforce_mode_blocks():
    cfg = _cfg(mode=MODE_ENFORCE)
    d = check_limits(cfg, requested_max_tokens=9999, current_concurrency=0, requests_in_last_min=0)
    assert d.allowed is False
    assert d.violations == (REASON_TOKENS,)


def test_limits_within_bounds_allowed_no_violations():
    cfg = _cfg(mode=MODE_ENFORCE)
    d = check_limits(cfg, requested_max_tokens=100, current_concurrency=1, requests_in_last_min=1)
    assert d.allowed and d.violations == ()


def test_redact_removes_real_key():
    secret = "sk-REAL-secret"
    text = f"upstream error with key {secret} leaked"
    out = redact_secret(text, secret)
    assert secret not in out
    assert "***REDACTED***" in out


def test_upstream_headers_use_real_key_only_here():
    cfg = _cfg(real_key="sk-REAL-secret")
    headers = upstream_headers(cfg)
    assert headers["Authorization"] == "Bearer sk-REAL-secret"


def test_audit_event_never_contains_real_or_virtual_key():
    cfg = _cfg()
    d = authorize(cfg, "vk-alpha")
    event = build_audit_event(
        vkey_fingerprint=vkey_fingerprint("vk-alpha"),
        decision=d,
        mode=cfg.mode,
        requested_max_tokens=100,
    )
    blob = str(event)
    assert "sk-REAL-secret" not in blob
    assert "vk-alpha" not in blob  # только fingerprint
    assert event["vkey_fingerprint"].startswith("vk_")


def test_fingerprint_stable_and_irreversible():
    fp1 = vkey_fingerprint("vk-alpha")
    fp2 = vkey_fingerprint("vk-alpha")
    assert fp1 == fp2 and "vk-alpha" not in fp1
    assert vkey_fingerprint(None) == "none"


def test_bearer_parsing():
    assert bearer_from_header("Bearer vk-alpha") == "vk-alpha"
    assert bearer_from_header("bearer vk-beta") == "vk-beta"
    assert bearer_from_header("Basic xxx") is None
    assert bearer_from_header(None) is None
    assert bearer_from_header("Bearer   ") is None


def test_is_serviceable_fail_closed():
    assert _cfg().is_serviceable() is True
    assert _cfg(real_key="").is_serviceable() is False  # нет реального ключа
    assert _cfg(vkeys=()).is_serviceable() is False  # нет ни одного vkey
