"""
Registrar Service - Event & Audit Logger.

Implemented using FastStream for NATS / JetStream integration.
Acts as a 'Black Box' recorder: subscribes to system streams and publishes audit records.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from faststream import FastStream, Logger
from faststream.nats import NatsBroker

from qiki.services.registrar.core.codes import RegistrarCode
from qiki.services.registrar.core.service import RegistrarService
from qiki.shared.events import build_cloudevent_headers
from qiki.shared.nats_subjects import (
    EVENTS_AUDIT,
    EVENTS_STREAM_NAME,
    EVENTS_V1_WILDCARD,
    RADAR_FRAMES,
    RADAR_STREAM_NAME,
)

# Configuration
NATS_URL = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

RADAR_STREAM = os.getenv("RADAR_STREAM", RADAR_STREAM_NAME)
EVENTS_STREAM = os.getenv("EVENTS_STREAM", EVENTS_STREAM_NAME)
AUDIT_SUBJECT = os.getenv("EVENTS_AUDIT_SUBJECT", EVENTS_AUDIT)

# Setup Logging
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("registrar")
logger.info("🔧 Registrar Configuration: NATS_URL=%s", NATS_URL)

# Initialize Services
registrar_service = RegistrarService(log_file="/var/log/qiki/registrar.log")

# Initialize Broker
broker = NatsBroker(NATS_URL)
app = FastStream(broker)


def _make_audit_record(
    *, event_type: str, source: str, payload: Dict[str, Any], severity: str = "INFO"
) -> Dict[str, Any]:
    ts = datetime.now(timezone.utc)
    event_id = f"audit-{ts.strftime('%Y%m%d-%H%M%S-%f')}"
    return {
        "event_id": event_id,
        "event_type": event_type,
        "source": source,
        "timestamp": ts.isoformat(),
        "payload": payload,
        "severity": severity,
    }


async def _publish_audit(record: Dict[str, Any], logger_: Logger) -> None:
    try:
        headers = build_cloudevent_headers(
            event_id=str(record["event_id"]),
            event_type="qiki.events.v1.AuditRecord",
            source="urn:qiki:registrar",
            event_time=datetime.fromisoformat(record["timestamp"]),
        )
        headers["Nats-Msg-Id"] = str(record["event_id"])
        await broker.publish(record, subject=AUDIT_SUBJECT, stream=EVENTS_STREAM, headers=headers)
    except Exception as exc:
        logger_.warning("Failed to publish audit record: %s", exc)


@app.after_startup
async def setup_service() -> None:
    """Called when the service starts."""
    logger.info("Starting Registrar Service via FastStream connected to %s", NATS_URL)

    registrar_service.register_boot_event(
        "SUCCESS",
        {
            "service": "registrar",
            "version": "2.0 (FastStream)",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@broker.subscriber(RADAR_FRAMES)
async def handle_radar_frame(msg: Dict[str, Any], logger: Logger) -> None:
    """Audit every radar frame received."""
    frame_id = msg.get("frame_id", "unknown")
    sensor_id = msg.get("sensor_id", "unknown")
    detections = len(msg.get("detections", []))

    registrar_service.register_sensor_event(
        sensor_id,
        "ACTIVE",
        {
            "event_code": RegistrarCode.RADAR_FRAME_RECEIVED,
            "frame_id": frame_id,
            "detections_count": detections,
            "description": "Radar frame processed",
        },
    )

    record = _make_audit_record(
        event_type="RADAR_FRAME_RECEIVED",
        source="registrar",
        payload={
            "frame_id": frame_id,
            "sensor_id": sensor_id,
            "detections_count": detections,
        },
        severity="INFO",
    )
    await _publish_audit(record, logger)
    logger.info("Audited Frame: %s from %s (%s objects)", frame_id, sensor_id, detections)


@broker.subscriber(EVENTS_V1_WILDCARD, description="System-wide Event Audit (v1)")
async def handle_system_events(msg: Dict[str, Any], logger: Logger) -> None:
    """Handle generic system events (errors, status changes)."""
    # Prevent infinite recursion: this handler must not audit its own audit messages.
    if msg.get("source") == "registrar" and msg.get("event_type") in {
        "SYSTEM_EVENT",
        "RADAR_FRAME_RECEIVED",
    }:
        return

    event_type = msg.get("type", "GENERIC_EVENT")
    logger.info("Audited Event: %s", event_type)

    registrar_service.register_system_event("SYSTEM", "INFO", msg)

    record = _make_audit_record(
        event_type="SYSTEM_EVENT",
        source="registrar",
        payload=msg,
        severity="INFO",
    )
    await _publish_audit(record, logger)


if __name__ == "__main__":
    asyncio.run(app.run())
