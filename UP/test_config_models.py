import json
from pathlib import Path

import sys
import pytest
from pydantic import ValidationError

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config_models import (
    ShipConfig,
    NetworkConfig,
    SecurityConfig,
    load_config,
)


def write_file(path: Path, data):
    if path.suffix in {'.yaml', '.yml'}:
        import yaml
        with path.open('w') as f:
            yaml.safe_dump(data, f)
    else:
        with path.open('w') as f:
            json.dump(data, f)


def test_ship_config_valid(tmp_path: Path):
    data = {"name": "Voyager", "max_speed": 1.5, "capacity": 10}
    file = tmp_path / 'ship.json'
    write_file(file, data)
    cfg = load_config(file, ShipConfig)
    assert cfg.max_speed == 1.5
    assert cfg.capacity == 10


def test_ship_config_negative_speed(tmp_path: Path):
    data = {"name": "Voyager", "max_speed": -1.0, "capacity": 10}
    file = tmp_path / 'ship.json'
    write_file(file, data)
    with pytest.raises(ValidationError):
        load_config(file, ShipConfig)


def test_network_config_invalid_port(tmp_path: Path):
    data = {"host": "localhost", "port": 0}
    file = tmp_path / 'net.yaml'
    write_file(file, data)
    with pytest.raises(ValidationError):
        load_config(file, NetworkConfig)


def test_security_config_invalid_ip(tmp_path: Path):
    data = {"use_tls": True, "allowed_ips": ["999.999.999.999"]}
    file = tmp_path / 'sec.json'
    write_file(file, data)
    with pytest.raises(ValidationError):
        load_config(file, SecurityConfig)
