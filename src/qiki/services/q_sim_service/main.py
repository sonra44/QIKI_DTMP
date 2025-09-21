import time
import sys
import os
from pathlib import Path
import math

# Добавляем корневую директорию проекта в sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

GENERATED_DIR = os.path.join(ROOT_DIR, "generated")
if GENERATED_DIR not in sys.path:
    sys.path.append(GENERATED_DIR)

from qiki.services.q_sim_service.logger import setup_logging, logger
from qiki.services.q_sim_service.core.world_model import WorldModel
from generated.sensor_raw_in_pb2 import SensorReading  # type: ignore[attr-defined]
from generated.actuator_raw_out_pb2 import ActuatorCommand  # type: ignore[attr-defined]
from generated.common_types_pb2 import UUID  # type: ignore[attr-defined]
from generated.common_types_pb2 import Vector3 as ProtoVector3  # type: ignore[attr-defined]
from generated.common_types_pb2 import SensorType as ProtoSensorType  # type: ignore[attr-defined]
from generated.common_types_pb2 import Unit as ProtoUnit  # type: ignore[attr-defined]
from uuid import uuid4
from google.protobuf.timestamp_pb2 import Timestamp  # type: ignore[import]
from google.protobuf.json_format import MessageToDict  # type: ignore[import]
from qiki.shared.config_models import QSimServiceConfig, load_config
from qiki.shared.models.radar import (
    RadarDetectionModel,
    RadarFrameModel,
    TransponderModeEnum,
)
from qiki.services.q_sim_service.radar_publisher import RadarNatsPublisher
from qiki.shared.converters.radar_proto_pydantic import model_frame_to_proto
from qiki.shared.converters.protobuf_pydantic import pydantic_uuid_to_proto_uuid


class QSimService:
    def __init__(self, config: QSimServiceConfig):
        self.config = config
        self.world_model = WorldModel()
        self.sensor_data_queue: list[SensorReading] = []
        self.actuator_command_queue: list[ActuatorCommand] = []
        # Feature flags
        env_flag = os.getenv("RADAR_ENABLED", "0").strip().lower()
        self.radar_enabled = env_flag not in ("0", "false", "")
        self.radar_frames: list[RadarFrameModel] = []
        nats_flag = os.getenv("RADAR_NATS_ENABLED", "0").strip().lower()
        self.radar_nats_enabled = nats_flag not in ("0", "false", "")
        self._radar_publisher: RadarNatsPublisher | None = None
        if self.radar_enabled and self.radar_nats_enabled:
            nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
            subject = os.getenv("RADAR_FRAMES_SUBJECT", "qiki.radar.v1.frames")
            self._radar_publisher = RadarNatsPublisher(nats_url, subject=subject)
        mode_str = os.getenv("RADAR_TRANSPONDER_MODE", "ON").strip().upper()
        self.transponder_mode = self._parse_transponder_mode(mode_str)
        default_transponder_id = f"ALLY-{uuid4().hex[:6].upper()}"
        self.transponder_id = os.getenv("RADAR_TRANSPONDER_ID", default_transponder_id)
        logger.info("QSimService initialized.")
        # Cycle between primary sim sensor and IMU to provide minimal multi-sensor stream
        primary = int(self.config.sim_sensor_type)
        imu = int(ProtoSensorType.IMU)
        cycle: list[int] = [primary]
        if self.radar_enabled:
            cycle.append(int(ProtoSensorType.RADAR))
        if primary != imu:
            cycle.append(imu)
        else:
            cycle.append(int(ProtoSensorType.LIDAR))
        self._sensor_cycle = cycle
        self._sensor_index = 0

    def generate_sensor_data(self) -> SensorReading:
        # Generate sensor data based on world model state
        world_state = self.world_model.get_state()
        # Choose sensor type from cycle (LIDAR <-> IMU)
        sensor_type = self._sensor_cycle[self._sensor_index]
        self._sensor_index = (self._sensor_index + 1) % len(self._sensor_cycle)

        if sensor_type == int(ProtoSensorType.LIDAR):
            timestamp = Timestamp()
            timestamp.GetCurrentTime()
            # Simple range-like scalar: use X position as placeholder
            return SensorReading(
                sensor_id=UUID(value=str(uuid4())),
                sensor_type=sensor_type,
                timestamp=timestamp,
                scalar_data=world_state["position"]["x"],
                unit=ProtoUnit.METERS,
                is_valid=True,
            )
        elif sensor_type == int(ProtoSensorType.IMU):
            timestamp = Timestamp()
            timestamp.GetCurrentTime()
            # IMU orientation as Euler (roll, pitch, yaw) in degrees using heading from world model
            roll = 0.0
            pitch = 0.0
            yaw = float(world_state["heading"])  # degrees
            return SensorReading(
                sensor_id=UUID(value=str(uuid4())),
                sensor_type=sensor_type,
                timestamp=timestamp,
                vector_data=ProtoVector3(x=roll, y=pitch, z=yaw),
                unit=ProtoUnit.DEGREES,
                is_valid=True,
            )
        elif sensor_type == int(ProtoSensorType.RADAR) and self.radar_enabled:
            frame = self.generate_radar_frame()
            proto_frame = model_frame_to_proto(frame)
            sr = SensorReading(
                sensor_id=pydantic_uuid_to_proto_uuid(frame.sensor_id),
                sensor_type=ProtoSensorType.RADAR,
                timestamp=proto_frame.timestamp,
                radar_data=proto_frame,
                is_valid=True,
                encoding="qiki.radar.v1",
                source_module="q_sim_service",
            )
            # signal_strength not part of proto_frame; leave default 0.0 or set nominal value
            sr.signal_strength = 1.0
            return sr
        else:
            timestamp = Timestamp()
            timestamp.GetCurrentTime()
            # Fallback to LIDAR-like scalar if unknown type
            return SensorReading(
                sensor_id=UUID(value=str(uuid4())),
                sensor_type=int(ProtoSensorType.LIDAR),
                timestamp=timestamp,
                scalar_data=world_state["position"]["x"],
                unit=ProtoUnit.METERS,
                is_valid=True,
            )

    def receive_actuator_command(self, command: ActuatorCommand):
        self.actuator_command_queue.append(command)
        logger.info(f"QSim received actuator command: {MessageToDict(command)}")
        self.world_model.update(command)  # Update world model based on command

    # ----------------------------- Radar generation -----------------------------
    def generate_radar_frame(self) -> RadarFrameModel:
        """Generate a minimal RadarFrame based on current WorldModel.

        Produces a single detection derived from simulated position/heading.
        Values respect model validators.
        """
        state = self.world_model.get_state()
        x = float(state["position"]["x"])  # meters
        y = float(state["position"]["y"])  # meters
        z = float(state["position"]["z"])  # meters
        rng = max(0.0, math.hypot(x, y))
        # Bearing: [0,360). atan2 returns [-pi, pi], convert to degrees and normalize
        bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
        # Elevation: [-90, 90]
        horiz = max(1e-9, math.hypot(x, y))
        elev = math.degrees(math.atan2(z, horiz))
        # Radial velocity (m/s): use forward speed projection on bearing (simplified)
        vr = 0.0
        snr_db = 20.0
        rcs_dbsm = 1.0

        det = RadarDetectionModel(
            range_m=rng,
            bearing_deg=bearing,
            elev_deg=elev,
            vr_mps=vr,
            snr_db=snr_db,
            rcs_dbsm=rcs_dbsm,
            transponder_on=self._is_transponder_active(),
            transponder_mode=self.transponder_mode,
            transponder_id=self._resolve_transponder_id(),
        )
        frame = RadarFrameModel(sensor_id=uuid4(), detections=[det])
        return frame

    def run(self):
        logger.info("QSimService started.")
        try:
            while True:
                self.step()  # Call the new step method
                time.sleep(self.config.sim_tick_interval)
        except KeyboardInterrupt:
            logger.info("QSimService stopped by user.")

    def step(self):
        """
        Performs one step of the simulation.
        """
        # Advance world model state
        delta_time = self.config.sim_tick_interval
        self.world_model.step(delta_time)

        # Generate sensor data
        sensor_data = self.generate_sensor_data()
        self.sensor_data_queue.append(sensor_data)
        logger.debug(f"Generated sensor data: {MessageToDict(sensor_data)}")

        # Optionally generate radar data
        if self.radar_enabled:
            rf = self.generate_radar_frame()
            self.radar_frames.append(rf)
            logger.debug(
                "Generated radar frame: range=%.1f, bearing=%.1f, elev=%.1f",
                rf.detections[0].range_m,
                rf.detections[0].bearing_deg,
                rf.detections[0].elev_deg,
            )
            if self.radar_nats_enabled and self._radar_publisher is not None:
                self._radar_publisher.publish_frame(rf)

    def _parse_transponder_mode(self, raw: str) -> TransponderModeEnum:
        mapping = {
            "ON": TransponderModeEnum.ON,
            "OFF": TransponderModeEnum.OFF,
            "SILENT": TransponderModeEnum.SILENT,
            "SPOOF": TransponderModeEnum.SPOOF,
        }
        return mapping.get(raw.upper(), TransponderModeEnum.ON)

    def _is_transponder_active(self) -> bool:
        return self.transponder_mode in (TransponderModeEnum.ON, TransponderModeEnum.SPOOF)

    def _resolve_transponder_id(self) -> str | None:
        if self.transponder_mode == TransponderModeEnum.ON:
            return self.transponder_id
        if self.transponder_mode == TransponderModeEnum.SPOOF:
            return f"SPOOF-{uuid4().hex[:6].upper()}"
        return None


if __name__ == "__main__":
    # Настройка логирования - используем абсолютный путь к config.yaml
    config_path = Path(__file__).resolve().parent / "config.yaml"
    setup_logging(default_path=str(config_path))

    # Загрузка конфигурации через Pydantic
    config = load_config(config_path, QSimServiceConfig)

    sim_service = QSimService(config)
    sim_service.run()
