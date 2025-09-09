from __future__ import annotations

from pathlib import Path
from typing import List, Type, TypeVar
import json
import yaml

from pydantic import BaseModel, PositiveFloat, conint, IPvAnyAddress


class ShipConfig(BaseModel):
    """Конфигурация корабля."""

    name: str
    max_speed: PositiveFloat
    capacity: conint(ge=0)


class NetworkConfig(BaseModel):
    """Параметры сети."""

    host: str
    port: conint(gt=0, lt=65536)


class SecurityConfig(BaseModel):
    """Настройки безопасности."""

    use_tls: bool = False
    allowed_ips: List[IPvAnyAddress] = []


class QSimServiceConfig(BaseModel):
    """Конфигурация для Q-Sim Service."""

    sim_tick_interval: int
    sim_sensor_type: int
    log_level: str


class QCoreAgentConfig(BaseModel):
    """Конфигурация для Q-Core Agent."""

    tick_interval: int
    log_level: str
    recovery_delay: int
    proposal_confidence_threshold: float
    mock_neural_proposals_enabled: bool
    grpc_server_address: str


T = TypeVar("T", bound=BaseModel)


def load_config(path: Path, model: Type[T]) -> T:
    """Загрузить конфигурацию из JSON или YAML с валидацией."""
    with path.open() as f:
        if path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(f)
        else:
            data = json.load(f)
    return (
        model.model_validate(data)
        if hasattr(model, "model_validate")
        else model.parse_obj(data)
    )
