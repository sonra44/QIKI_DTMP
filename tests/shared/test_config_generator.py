"""Tests for configuration generator."""

import json
import tempfile
from pathlib import Path


from qiki.shared.config.generator import generate_bot_config_from_spec, save_bot_config


def test_generate_bot_config_from_spec():
    """Test that bot config is generated correctly from BotSpec."""
    config = generate_bot_config_from_spec()
    
    # Check basic structure
    assert "schema_version" in config
    assert "bot_id" in config
    assert "hardware_profile" in config
    assert "runtime_profile" in config
    
    # Check that required components are mapped
    hardware = config["hardware_profile"]
    assert "actuators" in hardware
    assert "sensors" in hardware
    
    # Check that BotSpec ID is used
    assert config["bot_id"] == "QIKI-DODECA-01"
    
    # Check runtime profile
    profile = config["runtime_profile"]
    assert "sensors" in profile
    assert "propulsion" in profile


def test_save_bot_config():
    """Test that bot config is saved correctly."""
    config = generate_bot_config_from_spec()
    
    # Save to temporary file
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"
        save_bot_config(config, config_path)
        
        # Check file was created
        assert config_path.exists()
        
        # Check content is valid JSON
        with config_path.open("r", encoding="utf-8") as f:
            saved_config = json.load(f)
        
        # Check content matches
        assert saved_config["bot_id"] == config["bot_id"]
        assert saved_config["schema_version"] == config["schema_version"]