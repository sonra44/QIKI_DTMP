"""M2: креды NATS берутся из env отдельными kwargs, URL остаётся чистым."""

from __future__ import annotations

from qiki.shared.nats_connect import nats_auth_kwargs


def test_empty_env_means_no_auth(monkeypatch):
    for var in ("NATS_TOKEN", "NATS_USER", "NATS_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    assert nats_auth_kwargs() == {}


def test_user_password_pair(monkeypatch):
    monkeypatch.delenv("NATS_TOKEN", raising=False)
    monkeypatch.setenv("NATS_USER", "qiki")
    monkeypatch.setenv("NATS_PASSWORD", "secret")
    assert nats_auth_kwargs() == {"user": "qiki", "password": "secret"}


def test_incomplete_pair_ignored(monkeypatch):
    monkeypatch.delenv("NATS_TOKEN", raising=False)
    monkeypatch.setenv("NATS_USER", "qiki")
    monkeypatch.delenv("NATS_PASSWORD", raising=False)
    assert nats_auth_kwargs() == {}


def test_token_wins_over_pair(monkeypatch):
    monkeypatch.setenv("NATS_TOKEN", "tok")
    monkeypatch.setenv("NATS_USER", "qiki")
    monkeypatch.setenv("NATS_PASSWORD", "secret")
    assert nats_auth_kwargs() == {"token": "tok"}


def test_whitespace_only_ignored(monkeypatch):
    monkeypatch.setenv("NATS_TOKEN", "  ")
    monkeypatch.setenv("NATS_USER", " ")
    monkeypatch.setenv("NATS_PASSWORD", "x")
    assert nats_auth_kwargs() == {}
