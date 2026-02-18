"""Unified runtime configuration for Orion shell/mission terminal modes."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from typing import Mapping, MutableMapping


@dataclass(frozen=True)
class OrionShellRuntimeConfig:
    """Resolved runtime settings for mission terminal session behavior."""

    qiki_mode: str
    session_mode: str
    session_host: str
    session_port: int
    session_client_id: str
    session_client_role: str
    session_token: str

    @classmethod
    def from_env(
        cls,
        env: MutableMapping[str, str] | None = None,
        *,
        pid: int | None = None,
        hostname: str | None = None,
    ) -> "OrionShellRuntimeConfig":
        active_env = env if env is not None else os.environ
        qiki_mode = str(active_env.get("QIKI_MODE", "production")).strip().lower() or "production"
        if qiki_mode == "training":
            apply_training_defaults(active_env)
        session_mode = str(active_env.get("QIKI_SESSION_MODE", "standalone")).strip().lower() or "standalone"
        session_host = str(active_env.get("QIKI_SESSION_HOST", "127.0.0.1")).strip() or "127.0.0.1"
        try:
            session_port = int(str(active_env.get("QIKI_SESSION_PORT", "8765")))
        except Exception:
            session_port = 8765
        resolved_host = hostname or socket.gethostname()
        resolved_pid = os.getpid() if pid is None else int(pid)
        session_client_id = (
            str(active_env.get("QIKI_SESSION_CLIENT_ID", "")).strip() or f"{resolved_host}-{resolved_pid}"
        )
        session_client_role = str(active_env.get("QIKI_SESSION_ROLE", "controller")).strip().lower() or "controller"
        session_token = str(active_env.get("QIKI_SESSION_TOKEN", "")).strip()
        return cls(
            qiki_mode=qiki_mode,
            session_mode=session_mode,
            session_host=session_host,
            session_port=session_port,
            session_client_id=session_client_id,
            session_client_role=session_client_role,
            session_token=session_token,
        )


def apply_training_defaults(env: MutableMapping[str, str]) -> None:
    """Apply deterministic defaults for training mode without overriding explicit env."""

    env.setdefault("QIKI_PLUGINS_PROFILE", "training")
    env.setdefault("EVENTSTORE_BACKEND", "sqlite")
    env.setdefault("EVENTSTORE_DB_PATH", "artifacts/training_eventstore.sqlite")
    env.setdefault("RADAR_EMIT_OBSERVATION_RX", "0")


def runtime_summary(config: OrionShellRuntimeConfig) -> Mapping[str, str]:
    """Return a stable summary map for logs/debug output."""

    return {
        "qiki_mode": config.qiki_mode,
        "session_mode": config.session_mode,
        "session_host": config.session_host,
        "session_port": str(config.session_port),
        "session_client_id": config.session_client_id,
        "session_client_role": config.session_client_role,
        "session_token_present": "1" if bool(config.session_token) else "0",
    }
