from .interfaces import IBiosHandler
from .agent_logger import logger
from .bot_core import BotCore
from generated.bios_status_pb2 import BiosStatusReport, DeviceStatus
from generated.common_types_pb2 import UUID


class BiosHandler(IBiosHandler):
    """
    Handles the processing of BIOS status reports.
    In a real scenario, this would involve more complex logic,
    potentially interacting with a dedicated BIOS microservice.
    """

    def __init__(self, bot_core: BotCore):
        self.bot_core = bot_core
        logger.info("BiosHandler initialized.")

    def process_bios_status(self, bios_status: BiosStatusReport) -> BiosStatusReport:
        logger.debug(f"Processing BIOS status: {bios_status}")

        # Simulate some processing based on bot_core's hardware profile
        # In a real system, this would involve actual checks against hardware
        updated_bios_status = BiosStatusReport()
        updated_bios_status.CopyFrom(
            bios_status
        )  # Start with a copy of the incoming status

        all_systems_go = True
        hardware_profile = self.bot_core.get_property("hardware_profile")
        if hardware_profile:
            expected_devices = {
                act["id"] for act in hardware_profile.get("actuators", [])
            }.union({sens["id"] for sens in hardware_profile.get("sensors", [])})

            current_devices = {ds.device_id.value for ds in bios_status.post_results}

            # Check for missing devices
            for expected_device_id in expected_devices:
                if expected_device_id not in current_devices:
                    logger.warning(
                        f"Device {expected_device_id} from hardware profile not found in BIOS report."
                    )
                    all_systems_go = False
                    # Add a missing device status to the report
                    missing_device_status = DeviceStatus(
                        device_id=UUID(value=expected_device_id),
                        status=DeviceStatus.Status.NOT_FOUND,
                        error_message="Device not reported by BIOS",
                        status_code=DeviceStatus.StatusCode.COMPONENT_NOT_FOUND,  # Component not found
                    )
                    updated_bios_status.post_results.append(missing_device_status)

            # Check status of reported devices
            for device_status in updated_bios_status.post_results:
                if device_status.status != DeviceStatus.Status.OK:
                    all_systems_go = False
                    logger.warning(
                        f"Device {device_status.device_id.value} reported status {device_status.status}"
                    )
        else:
            logger.warning(
                "No hardware profile found in bot_config. Assuming all systems go for minimal mode."
            )

        updated_bios_status.all_systems_go = all_systems_go

        logger.info(
            f"BIOS processing complete. All systems go: {updated_bios_status.all_systems_go}"
        )
        return updated_bios_status
