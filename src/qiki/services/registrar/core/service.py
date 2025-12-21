"""Registrar service for event registration and auditing."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RegistrarEvent:
    """Represents a registered event."""

    def __init__(
        self,
        event_id: str,
        event_type: str,
        source: str,
        timestamp: datetime,
        payload: Dict[str, Any],
        severity: str = "INFO"
    ):
        self.event_id = event_id
        self.event_type = event_type
        self.source = source
        self.timestamp = timestamp
        self.payload = payload
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "severity": self.severity
        }


class RegistrarService:
    """Service for registering and auditing events."""

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = Path(log_file) if log_file else None
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def register_event(self, event: RegistrarEvent) -> None:
        """Register an event."""
        # Log to standard logger
        logger.info(
            "Registrar Event [%s] %s from %s: %s",
            event.severity,
            event.event_type,
            event.source,
            json.dumps(event.payload, ensure_ascii=False)
        )

        # Write to file if configured
        if self.log_file:
            self._write_to_file(event)

        # In a real implementation, we would also:
        # - Publish to NATS JetStream topic qiki.events.v1.audit
        # - Store in database
        # - Send to external monitoring systems

    def _write_to_file(self, event: RegistrarEvent) -> None:
        """Write event to log file."""
        try:
            if self.log_file:
                with self.log_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to write event to file: %s", e)

    def register_boot_event(self, boot_status: str, details: Dict[str, Any]) -> None:
        """Register a boot event."""
        event = RegistrarEvent(
            event_id=f"boot-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            event_type="BOOT_EVENT",
            source="registrar_service",
            timestamp=datetime.now(timezone.utc),
            payload={
                "status": boot_status,
                "details": details
            },
            severity="INFO"
        )
        self.register_event(event)

    def register_sensor_event(self, sensor_id: str, status: str, details: Dict[str, Any]) -> None:
        """Register a sensor event."""
        event = RegistrarEvent(
            event_id=f"sensor-{sensor_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            event_type="SENSOR_EVENT",
            source=f"sensor_{sensor_id}",
            timestamp=datetime.now(timezone.utc),
            payload={
                "sensor_id": sensor_id,
                "status": status,
                "details": details
            },
            severity="INFO"
        )
        self.register_event(event)

    def register_system_event(self, source: str, severity: str, details: Dict[str, Any]) -> None:
        """Register a generic system event."""
        event = RegistrarEvent(
            event_id=f"sys-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}",
            event_type="SYSTEM_EVENT",
            source=source,
            timestamp=datetime.now(timezone.utc),
            payload=details,
            severity=severity
        )
        self.register_event(event)
