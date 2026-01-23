from __future__ import annotations

import os
from dataclasses import dataclass, field


def _parse_bool_env(name: str, default: str) -> bool:
    raw = os.getenv(name)
    value = (raw if raw is not None else default).strip().lower()
    return value not in {"", "0", "false", "no", "off"}


@dataclass(frozen=True, slots=True)
class BiosConfig:
    listen_host: str = os.getenv("BIOS_LISTEN_HOST", "0.0.0.0")
    listen_port: int = int(os.getenv("BIOS_LISTEN_PORT", "8080"))

    bot_config_path: str = os.getenv(
        "BOT_CONFIG_PATH",
        "/workspace/src/qiki/services/q_core_agent/config/bot_config.json",
    )

    sim_grpc_host: str = os.getenv("SIM_GRPC_HOST", "q-sim-service")
    sim_grpc_port: int = int(os.getenv("SIM_GRPC_PORT", "50051"))
    sim_health_check_timeout_s: float = float(os.getenv("SIM_HEALTH_CHECK_TIMEOUT", "2.0"))

    nats_url: str = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
    nats_subject: str = os.getenv("NATS_EVENT_SUBJECT", "qiki.events.v1.bios_status")
    publish_enabled: bool = field(default_factory=lambda: _parse_bool_env("BIOS_PUBLISH_ENABLED", "1"))
    publish_interval_s: float = float(os.getenv("BIOS_PUBLISH_INTERVAL_SEC", "5.0"))

    log_level: str = os.getenv("LOG_LEVEL", "INFO")
