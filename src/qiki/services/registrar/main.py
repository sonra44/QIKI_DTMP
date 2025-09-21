"""Main entry point for Registrar service."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from qiki.services.registrar.core.service import RegistrarService
from qiki.services.registrar.core.codes import RegistrarCode


def main():
    """Main function for Registrar service."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Registrar service")
    
    # Create registrar service
    registrar = RegistrarService(log_file="/var/log/qiki/registrar.log")
    
    # Register boot event
    registrar.register_boot_event(
        "SUCCESS", 
        {
            "service": "registrar",
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )
    
    # Register a sample sensor event
    registrar.register_sensor_event(
        "radar_01",
        "ACTIVE",
        {
            "event_code": RegistrarCode.RADAR_FRAME_RECEIVED,
            "description": "Radar frame received and processed"
        }
    )
    
    logger.info("Registrar service initialized and running")
    
    # In a real implementation, this would be a long-running service
    # that listens for events and registers them
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Registrar service")


if __name__ == "__main__":
    main()