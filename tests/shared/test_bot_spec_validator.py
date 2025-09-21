"""Тесты для BotSpec валидатора."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from qiki.shared.models.bot_spec import (
    REQUIRED_CHANNELS,
    REQUIRED_COMPONENTS,
    BotSpecModel,
    load_bot_spec,
)


def test_load_default_bot_spec() -> None:
    spec = load_bot_spec()

    assert spec.kind == "BotSpec"
    assert spec.version == 1
    assert REQUIRED_COMPONENTS == set(spec.components)
    assert REQUIRED_CHANNELS.issubset(set(spec.event_bus.channels))


def test_missing_component_validation() -> None:
    data = {
        "version": 1,
        "kind": "BotSpec",
        "metadata": {"id": "QIKI-TEST"},
        "components": {"hull": {"type": "structure"}},
        "event_bus": {"channels": list(REQUIRED_CHANNELS)},
    }

    with pytest.raises(ValidationError):
        BotSpecModel.model_validate(data)


def test_missing_channel_validation(tmp_path: Path) -> None:
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(
        """
version: 1
kind: BotSpec
metadata:
  id: QIKI-TEST
components:
  hull:
    type: structure
  power:
    type: dc_bus
  propulsion:
    type: propulsors
  sensors:
    type: sensing_suite
  comms:
    type: datalink
  shields:
    type: defensive
  navigation:
    type: nav_stack
  protocols:
    type: executor
event_bus:
  channels:
    - SensorFrame
    - TrackSet
    - ProtocolCmd
    - EnergyStatus
    - ShieldStatus
    - NavState
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_bot_spec(spec_file)


def test_get_component_returns_expected() -> None:
    spec = load_bot_spec()
    component = spec.get_component("sensors")

    assert component.type == "sensing_suite"
    assert "sensor_frame" in component.provides


def test_get_component_missing_raises_keyerror() -> None:
    spec = load_bot_spec()
    with pytest.raises(KeyError):
        spec.get_component("nonexistent")
