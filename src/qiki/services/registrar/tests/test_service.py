"""Tests for Registrar service."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from qiki.services.registrar.core.service import RegistrarService, RegistrarEvent


def test_registrar_event_creation():
    """Test creating a registrar event."""
    payload = {"test": "data", "value": 42}
    event = RegistrarEvent(
        event_id="test-123",
        event_type="TEST_EVENT",
        source="test_source",
        timestamp=datetime.now(timezone.utc),
        payload=payload
    )
    
    # Check attributes
    assert event.event_id == "test-123"
    assert event.event_type == "TEST_EVENT"
    assert event.source == "test_source"
    assert event.payload == payload
    
    # Check dictionary conversion
    event_dict = event.to_dict()
    assert event_dict["event_id"] == "test-123"
    assert event_dict["event_type"] == "TEST_EVENT"
    assert event_dict["source"] == "test_source"
    assert event_dict["payload"] == payload


def test_registrar_service_creation():
    """Test creating a registrar service."""
    # Test without log file
    registrar = RegistrarService()
    assert registrar.log_file is None
    
    # Test with log file
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        registrar = RegistrarService(str(log_path))
        assert registrar.log_file == log_path


def test_registrar_service_register_event():
    """Test registering an event."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        registrar = RegistrarService(str(log_path))
        
        # Create and register an event
        payload = {"test": "data"}
        event = RegistrarEvent(
            event_id="test-123",
            event_type="TEST_EVENT",
            source="test_source",
            timestamp=datetime.now(timezone.utc),
            payload=payload
        )
        
        registrar.register_event(event)
        
        # Check that event was written to file
        assert log_path.exists()
        with log_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            # Parse the JSON
            logged_event = json.loads(lines[0])
            assert logged_event["event_id"] == "test-123"
            assert logged_event["event_type"] == "TEST_EVENT"
            assert logged_event["source"] == "test_source"
            assert logged_event["payload"] == payload


def test_registrar_service_register_boot_event():
    """Test registering a boot event."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        registrar = RegistrarService(str(log_path))
        
        # Register a boot event
        details = {"version": "1.0", "modules": ["core", "radar"]}
        registrar.register_boot_event("SUCCESS", details)
        
        # Check that event was written to file
        assert log_path.exists()
        with log_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            # Parse the JSON
            logged_event = json.loads(lines[0])
            assert logged_event["event_type"] == "BOOT_EVENT"
            assert logged_event["payload"]["status"] == "SUCCESS"
            assert logged_event["payload"]["details"] == details


def test_registrar_service_register_sensor_event():
    """Test registering a sensor event."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        registrar = RegistrarService(str(log_path))
        
        # Register a sensor event
        details = {"frame_id": "frame-123", "detections": 5}
        registrar.register_sensor_event("radar_01", "ACTIVE", details)
        
        # Check that event was written to file
        assert log_path.exists()
        with log_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            # Parse the JSON
            logged_event = json.loads(lines[0])
            assert logged_event["event_type"] == "SENSOR_EVENT"
            assert logged_event["payload"]["sensor_id"] == "radar_01"
            assert logged_event["payload"]["status"] == "ACTIVE"
            assert logged_event["payload"]["details"] == details