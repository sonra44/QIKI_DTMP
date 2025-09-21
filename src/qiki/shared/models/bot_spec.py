"""BotSpec loader и валидатор для каркасного Этапа-0."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Обязательные сущности, зафиксированные в каркасе.
REQUIRED_COMPONENTS = {
    "hull",
    "power",
    "propulsion",
    "sensors",
    "comms",
    "shields",
    "navigation",
    "protocols",
}

REQUIRED_CHANNELS = {
    "SensorFrame",
    "TrackSet",
    "ProtocolCmd",
    "EnergyStatus",
    "ShieldStatus",
    "NavState",
    "RegistrarEvent",
}


class ComponentModel(BaseModel):
    """Описывает компонент платформы из BotSpec."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    type: str
    provides: List[str] = Field(default_factory=list)
    consumes: List[str] = Field(default_factory=list)


class MetadataModel(BaseModel):
    """Метаданные спецификации."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str


class EventBusModel(BaseModel):
    """Описание каналов событийной шины."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    channels: List[str]

    @field_validator("channels")
    @classmethod
    def _channels_contain_required(cls, value: List[str]) -> List[str]:
        missing = REQUIRED_CHANNELS - set(value)
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(
                f"missing required channels in event_bus: {missing_list}"
            )
        return value


class BotSpecModel(BaseModel):
    """Основная Pydantic модель BotSpec."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    version: int
    kind: Literal["BotSpec"]
    metadata: MetadataModel
    components: Dict[str, ComponentModel]
    event_bus: EventBusModel

    @model_validator(mode="after")
    def _components_complete(self) -> "BotSpecModel":
        missing = REQUIRED_COMPONENTS - set(self.components)
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(f"missing required components: {missing_list}")
        return self

    def to_runtime_profile(self) -> Dict[str, Dict[str, List[str]]]:
        """Формирует словарь с provides/consumes для сервисных конфигов."""

        profile: Dict[str, Dict[str, List[str]]] = {}
        for name, component in self.components.items():
            profile[name] = {
                "provides": list(component.provides),
                "consumes": list(component.consumes),
            }
        return profile

    def get_component(self, name: str) -> ComponentModel:
        """Возвращает описание компонента из спецификации."""

        if name not in self.components:
            raise KeyError(f"Component '{name}' not defined in BotSpec")
        return self.components[name]


def _default_spec_path() -> Path:
    return Path(__file__).resolve().parents[4] / "shared" / "specs" / "BotSpec.yaml"


def load_bot_spec(path: str | Path | None = None) -> BotSpecModel:
    """Загружает и валидирует BotSpec из YAML."""

    spec_path = Path(path) if path else _default_spec_path()
    if not spec_path.exists():
        raise FileNotFoundError(f"BotSpec file not found: {spec_path}")

    with spec_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    return BotSpecModel.model_validate(raw)
