"""Integration tests for Registrar service with event codes."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from qiki.services.registrar.core.service import RegistrarService, RegistrarEvent
from qiki.services.registrar.core.codes import RegistrarCode


def test_registrar_with_event_codes():
    """Test registrar service with event codes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        registrar = RegistrarService(str(log_path))
        
        # Create an event with a code
        event = RegistrarEvent(
            event_id="boot-001",
            event_type="BOOT_EVENT",
            source="system",
            timestamp=datetime.now(timezone.utc),
            payload={
                "event_code": RegistrarCode.BOOT_OK,
                "description": "System boot completed successfully"
            }
        )
        
        registrar.register_event(event)
        
        # Check that event was written to file with code
        assert log_path.exists()
        with log_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            # Parse the JSON
            logged_event = json.loads(lines[0])
            assert logged_event["event_type"] == "BOOT_EVENT"
            assert logged_event["payload"]["event_code"] == RegistrarCode.BOOT_OK
            assert "boot completed successfully" in logged_event["payload"]["description"]


def test_multiple_events_with_different_codes():
    """Test registering multiple events with different codes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        registrar = RegistrarService(str(log_path))
        
        # Register boot event
        boot_event = RegistrarEvent(
            event_id="boot-001",
            event_type="BOOT_EVENT",
            source="system",
            timestamp=datetime.now(timezone.utc),
            payload={
                "event_code": RegistrarCode.BOOT_OK,
                "description": "System boot completed"
            }
        )
        registrar.register_event(boot_event)
        
        # Register sensor event
        sensor_event = RegistrarEvent(
            event_id="sensor-001",
            event_type="SENSOR_EVENT",
            source="radar_01",
            timestamp=datetime.now(timezone.utc),
            payload={
                "event_code": RegistrarCode.RADAR_FRAME_RECEIVED,
                "description": "Radar frame received"
            }
        )
        registrar.register_event(sensor_event)
        
        # Register communication event
        comm_event = RegistrarEvent(
            event_id="comm-001",
            event_type="COMM_EVENT",
            source="nats_client",
            timestamp=datetime.now(timezone.utc),
            payload={
                "event_code": RegistrarCode.NATS_CONNECTED,
                "description": "NATS connection established"
            }
        )
        registrar.register_event(comm_event)
        
        # Check that all events were written to file
        assert log_path.exists()
        with log_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 3
            
            # Parse the JSON events
            events = [json.loads(line) for line in lines]
            
            # Check event codes
            event_codes = [event["payload"]["event_code"] for event in events]
            assert RegistrarCode.BOOT_OK in event_codes
            assert RegistrarCode.RADAR_FRAME_RECEIVED in event_codes
            assert RegistrarCode.NATS_CONNECTED in event_codes