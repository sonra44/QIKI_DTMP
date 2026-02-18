from __future__ import annotations

from qiki.services.q_core_agent.core.orion_shell_runtime import (
    OrionShellRuntimeConfig,
    apply_training_defaults,
)


def test_runtime_config_defaults_and_client_id() -> None:
    env: dict[str, str] = {}
    cfg = OrionShellRuntimeConfig.from_env(env, pid=4242, hostname="host-a")
    assert cfg.qiki_mode == "production"
    assert cfg.session_mode == "standalone"
    assert cfg.session_host == "127.0.0.1"
    assert cfg.session_port == 8765
    assert cfg.session_client_id == "host-a-4242"
    assert cfg.session_client_role == "controller"
    assert cfg.session_token == ""


def test_runtime_config_invalid_port_falls_back() -> None:
    env = {"QIKI_SESSION_PORT": "oops"}
    cfg = OrionShellRuntimeConfig.from_env(env, pid=1, hostname="h")
    assert cfg.session_port == 8765


def test_training_defaults_applied_without_overrides() -> None:
    env: dict[str, str] = {"QIKI_MODE": "training", "EVENTSTORE_BACKEND": "memory"}
    cfg = OrionShellRuntimeConfig.from_env(env, pid=12, hostname="trainer")
    assert cfg.qiki_mode == "training"
    assert env["QIKI_PLUGINS_PROFILE"] == "training"
    assert env["EVENTSTORE_BACKEND"] == "memory"
    assert env["EVENTSTORE_DB_PATH"] == "artifacts/training_eventstore.sqlite"
    assert env["RADAR_EMIT_OBSERVATION_RX"] == "0"


def test_apply_training_defaults_is_idempotent() -> None:
    env: dict[str, str] = {"EVENTSTORE_DB_PATH": "/tmp/custom.sqlite"}
    apply_training_defaults(env)
    apply_training_defaults(env)
    assert env["EVENTSTORE_DB_PATH"] == "/tmp/custom.sqlite"
