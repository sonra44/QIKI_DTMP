from __future__ import annotations

import asyncio
import math
import os
import time
from datetime import datetime, timezone
from uuid import uuid4

from google.protobuf.json_format import MessageToDict
from google.protobuf.timestamp_pb2 import Timestamp

from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import (
    SensorType as ProtoSensorType,
    UUID,
    Unit as ProtoUnit,
    Vector3 as ProtoVector3,
)
from generated.sensor_raw_in_pb2 import SensorReading

from qiki.services.q_sim_service.core.world_model import WorldModel
from qiki.services.q_sim_service.logger import logger
from qiki.services.q_sim_service.radar_publisher import RadarNatsPublisher
from qiki.services.q_sim_service.telemetry_publisher import TelemetryNatsPublisher
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.converters.radar_proto_pydantic import model_frame_to_proto
from qiki.shared.converters.protobuf_pydantic import pydantic_uuid_to_proto_uuid
from qiki.shared.models.radar import (
    RadarDetectionModel,
    RadarFrameModel,
    TransponderModeEnum,
)
from qiki.shared.models.telemetry import TelemetrySnapshotModel


class QSimService:
    def __init__(self, config: QSimServiceConfig):
        self.config = config
        self.world_model = WorldModel()
        self.sensor_data_queue: list[SensorReading] = []
        self.actuator_command_queue: list[ActuatorCommand] = []
        env_flag = os.getenv("RADAR_ENABLED", "0").strip().lower()
        self.radar_enabled = env_flag not in ("0", "false", "")
        self.radar_frames: list[RadarFrameModel] = []
        nats_flag = os.getenv("RADAR_NATS_ENABLED", "0").strip().lower()
        self.radar_nats_enabled = nats_flag not in ("0", "false", "")
        self._radar_publisher: RadarNatsPublisher | None = None
        if self.radar_enabled and self.radar_nats_enabled:
            nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
            sr_threshold = self.config.radar.sr_threshold_m
            self._radar_publisher = RadarNatsPublisher(nats_url, sr_threshold)

        telemetry_flag = os.getenv("TELEMETRY_NATS_ENABLED", "0").strip().lower()
        self.telemetry_nats_enabled = telemetry_flag not in ("0", "false", "")
        self._telemetry_publisher: TelemetryNatsPublisher | None = None
        self._telemetry_interval_sec = float(os.getenv("TELEMETRY_INTERVAL_SEC", "1.0"))
        self._telemetry_last_sent_mono = 0.0
        if self.telemetry_nats_enabled:
            nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
            subject = os.getenv("SYSTEM_TELEMETRY_SUBJECT", "qiki.telemetry")
            self._telemetry_publisher = TelemetryNatsPublisher(nats_url, subject=subject)

        mode_str = os.getenv("RADAR_TRANSPONDER_MODE", "ON").strip().upper()
        self.transponder_mode = self._parse_transponder_mode(mode_str)
        default_transponder_id = f"ALLY-{uuid4().hex[:6].upper()}"
        self.transponder_id = os.getenv("RADAR_TRANSPONDER_ID", default_transponder_id)
        logger.info("QSimService initialized.")
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

    async def get_sensor_data(self) -> SensorReading:
        while not self.sensor_data_queue:
            await asyncio.sleep(0.1)
        return self.sensor_data_queue.pop(0)

    def generate_sensor_data(self) -> SensorReading:
        world_state = self.world_model.get_state()
        sensor_type = self._sensor_cycle[self._sensor_index]
        self._sensor_index = (self._sensor_index + 1) % len(self._sensor_cycle)

        if sensor_type == int(ProtoSensorType.LIDAR):
            timestamp = Timestamp()
            timestamp.GetCurrentTime()
            return SensorReading(
                sensor_id=UUID(value=str(uuid4())),
                sensor_type=sensor_type,
                timestamp=timestamp,
                scalar_data=world_state["position"]["x"],
                unit=ProtoUnit.METERS,
                is_valid=True,
            )
        if sensor_type == int(ProtoSensorType.IMU):
            timestamp = Timestamp()
            timestamp.GetCurrentTime()
            att = world_state.get("attitude") if isinstance(world_state, dict) else None
            att = att if isinstance(att, dict) else {}
            roll_rad = float(att.get("roll_rad", 0.0))
            pitch_rad = float(att.get("pitch_rad", 0.0))
            yaw_rad = float(att.get("yaw_rad", math.radians(world_state.get("heading", 0.0))))
            roll = math.degrees(roll_rad)
            pitch = math.degrees(pitch_rad)
            yaw = math.degrees(yaw_rad)
            return SensorReading(
                sensor_id=UUID(value=str(uuid4())),
                sensor_type=sensor_type,
                timestamp=timestamp,
                vector_data=ProtoVector3(x=roll, y=pitch, z=yaw),
                unit=ProtoUnit.DEGREES,
                is_valid=True,
            )
        if sensor_type == int(ProtoSensorType.RADAR) and self.radar_enabled:
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
            sr.signal_strength = 1.0
            return sr

        timestamp = Timestamp()
        timestamp.GetCurrentTime()
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
        self.world_model.update(command)

    def generate_radar_frame(self) -> RadarFrameModel:
        state = self.world_model.get_state()
        x = float(state["position"]["x"])
        y = float(state["position"]["y"])
        z = float(state["position"]["z"])
        rng = max(0.0, math.hypot(x, y))
        bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
        horiz = max(1e-9, math.hypot(x, y))
        elev = math.degrees(math.atan2(z, horiz))
        vr = 0.0
        snr_db = 20.0
        rcs_dbsm = 1.0

        sr_threshold = self.config.radar.sr_threshold_m
        bearing_deg = bearing
        elev_deg = elev

        lr_detection = RadarDetectionModel(
            range_m=max(sr_threshold * 1.5, rng + sr_threshold),
            bearing_deg=bearing_deg,
            elev_deg=elev_deg,
            vr_mps=vr,
            snr_db=snr_db,
            rcs_dbsm=rcs_dbsm,
            transponder_on=False,
            transponder_mode=TransponderModeEnum.OFF,
            transponder_id=None,
        )

        sr_detection = RadarDetectionModel(
            range_m=max(sr_threshold * 0.5, min(rng, sr_threshold * 0.8)),
            bearing_deg=bearing_deg,
            elev_deg=elev_deg,
            vr_mps=vr,
            snr_db=snr_db,
            rcs_dbsm=rcs_dbsm,
            transponder_on=self._is_transponder_active(),
            transponder_mode=self.transponder_mode,
            transponder_id=self._resolve_transponder_id(),
        )

        frame = RadarFrameModel(sensor_id=uuid4(), detections=[lr_detection, sr_detection])
        return frame

    def run(self):
        logger.info("QSimService started.")
        try:
            while True:
                self.step()
                time.sleep(self.config.sim_tick_interval)
        except KeyboardInterrupt:
            logger.info("QSimService stopped by user.")

    def step(self):
        delta_time = self.config.sim_tick_interval
        self.world_model.set_runtime_load_inputs(
            radar_enabled=self.radar_enabled,
            sensor_queue_depth=len(self.sensor_data_queue),
            actuator_queue_depth=len(self.actuator_command_queue),
            transponder_active=self._is_transponder_active(),
        )
        self.world_model.step(delta_time)

        self._maybe_publish_telemetry()

        sensor_data = self.generate_sensor_data()
        self.sensor_data_queue.append(sensor_data)
        logger.debug(f"Generated sensor data: {MessageToDict(sensor_data)}")

        if self.radar_enabled and getattr(self.world_model, "radar_allowed", True):
            rf = self.generate_radar_frame()
            self.radar_frames.append(rf)
            if self.radar_nats_enabled and self._radar_publisher is not None:
                self._radar_publisher.publish_frame(rf)

    def _maybe_publish_telemetry(self) -> None:
        if not self.telemetry_nats_enabled:
            return
        if self._telemetry_publisher is None:
            return

        now_mono = time.monotonic()
        if now_mono - self._telemetry_last_sent_mono < self._telemetry_interval_sec:
            return
        self._telemetry_last_sent_mono = now_mono

        state = self.world_model.get_state()
        payload = self._build_telemetry_payload(state)
        self._telemetry_publisher.publish_snapshot(payload)

    def _build_telemetry_payload(self, state: dict) -> dict:
        ts_dt = datetime.now(timezone.utc)
        ts = ts_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        ts_unix_ms = int(ts_dt.timestamp() * 1000)
        pos = state.get("position") if isinstance(state, dict) else None
        pos = pos if isinstance(pos, dict) else {}
        att = state.get("attitude") if isinstance(state, dict) else None
        att = att if isinstance(att, dict) else {}

        # Contract: position is always 3D, z must be present.
        x = float(pos.get("x", 0.0))
        y = float(pos.get("y", 0.0))
        z = float(pos.get("z", 0.0))
        roll = float(att.get("roll_rad", 0.0))
        pitch = float(att.get("pitch_rad", 0.0))
        yaw = float(att.get("yaw_rad", math.radians(state.get("heading", 0.0))))

        payload = TelemetrySnapshotModel(
            source="q_sim_service",
            timestamp=ts,
            ts_unix_ms=ts_unix_ms,
            position={"x": x, "y": y, "z": z},
            velocity=float(state.get("speed", 0.0)),
            heading=float(state.get("heading", 0.0)),
            attitude={"roll_rad": roll, "pitch_rad": pitch, "yaw_rad": yaw},
            battery=float(state.get("battery_level", 0.0)),
            cpu_usage=None if state.get("cpu_usage") is None else float(state.get("cpu_usage")),
            memory_usage=None if state.get("memory_usage") is None else float(state.get("memory_usage")),
            hull={"integrity": float(state.get("hull_integrity", 100.0))},
            power=state.get("power", {}),
            thermal=state.get("thermal", {"nodes": []}),
            radiation_usvh=float(state.get("radiation_usvh", 0.0)),
            temp_external_c=float(state.get("temp_external_c", -60.0)),
            temp_core_c=float(state.get("temp_core_c", 25.0)),
        )
        return payload.model_dump(mode="json")

    def _parse_transponder_mode(self, raw: str) -> TransponderModeEnum:
        mapping = {
            "ON": TransponderModeEnum.ON,
            "OFF": TransponderModeEnum.OFF,
            "SILENT": TransponderModeEnum.SILENT,
            "SPOOF": TransponderModeEnum.SPOOF,
        }
        return mapping.get(raw.upper(), TransponderModeEnum.ON)

    def _is_transponder_active(self) -> bool:
        if not getattr(self.world_model, "transponder_allowed", True):
            return False
        return self.transponder_mode in (TransponderModeEnum.ON, TransponderModeEnum.SPOOF)

    def _resolve_transponder_id(self) -> str | None:
        if self.transponder_mode == TransponderModeEnum.ON:
            return self.transponder_id
        if self.transponder_mode == TransponderModeEnum.SPOOF:
            return f"SPOOF-{uuid4().hex[:6].upper()}"
        return None
