from __future__ import annotations

import asyncio
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
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
from qiki.services.q_sim_service.events_publisher import SimEventsNatsPublisher
from qiki.services.q_sim_service.logger import logger
from qiki.services.q_sim_service.radar_publisher import RadarNatsPublisher
from qiki.services.q_sim_service.telemetry_publisher import TelemetryNatsPublisher
from qiki.shared.config.hardware_profile_hash import compute_hardware_profile_hash
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.converters.radar_proto_pydantic import model_frame_to_proto
from qiki.shared.converters.protobuf_pydantic import pydantic_uuid_to_proto_uuid
from qiki.shared.models.radar import (
    RadarDetectionModel,
    RadarFrameModel,
    TransponderModeEnum,
)
from qiki.shared.models.core import CommandMessage
from qiki.shared.models.telemetry import TelemetrySnapshotModel
from qiki.shared.nats_subjects import SIM_POWER_BUS, SIM_SENSOR_THERMAL


class QSimService:
    def __init__(self, config: QSimServiceConfig):
        self.config = config
        self._bot_config = self._load_bot_config()
        self._comms_enabled = True
        if isinstance(self._bot_config, dict):
            hp = self._bot_config.get("hardware_profile")
            if isinstance(hp, dict):
                comms_plane = hp.get("comms_plane")
                if isinstance(comms_plane, dict):
                    self._comms_enabled = bool(comms_plane.get("enabled", True))
        self._hardware_profile_hash: str | None = None
        if isinstance(self._bot_config, dict):
            try:
                self._hardware_profile_hash = compute_hardware_profile_hash(self._bot_config)
            except Exception:
                self._hardware_profile_hash = None
        self.world_model = WorldModel(bot_config=self._bot_config)
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

        events_flag_default = "1" if self.telemetry_nats_enabled else "0"
        events_flag = os.getenv("EVENTS_NATS_ENABLED", events_flag_default).strip().lower()
        self.events_nats_enabled = events_flag not in ("0", "false", "")
        self._events_publisher: SimEventsNatsPublisher | None = None
        self._events_interval_sec = float(os.getenv("EVENTS_INTERVAL_SEC", str(self._telemetry_interval_sec)))
        self._events_last_sent_mono = 0.0
        if self.events_nats_enabled:
            nats_url = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
            self._events_publisher = SimEventsNatsPublisher(nats_url)

        # Transponder (XPDR) mode: canonical runtime source is bot_config.json (if present),
        # but we keep env overrides for debugging.
        mode_str = os.getenv("RADAR_TRANSPONDER_MODE", "").strip().upper()
        if not mode_str:
            hp = (self._bot_config or {}).get("hardware_profile") if isinstance(self._bot_config, dict) else {}
            comms = hp.get("comms_plane") if isinstance(hp, dict) else None
            if isinstance(comms, dict):
                mode_str = str(comms.get("xpdr_mode_init") or "").strip().upper()
        if not mode_str:
            mode_str = "ON"
        if not self._comms_enabled:
            # Canonical: if comms plane is disabled in bot_config.json, XPDR is forced OFF
            # (env override is ignored to keep sim truth deterministic and operator-explainable).
            mode_str = "OFF"
        self.transponder_mode = self._parse_transponder_mode(mode_str)
        default_transponder_id = f"ALLY-{uuid4().hex[:6].upper()}"
        self.transponder_id = os.getenv("RADAR_TRANSPONDER_ID", default_transponder_id)
        self._spoof_transponder_id: str | None = None
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

        # Simulation runtime state (single source of truth).
        self._sim_running = True
        self._sim_paused = False
        self._sim_speed = 1.0

    @property
    def comms_enabled(self) -> bool:
        return bool(self._comms_enabled)

    def get_sim_state(self) -> dict:
        fsm_state = "STOPPED"
        if self._sim_running and self._sim_paused:
            fsm_state = "PAUSED"
        elif self._sim_running:
            fsm_state = "RUNNING"
        return {
            "running": bool(self._sim_running),
            "paused": bool(self._sim_paused),
            "speed": float(self._sim_speed),
            "fsm_state": fsm_state,
        }

    def reset_simulation(self) -> None:
        # Keep publishers and config; reset simulation truth.
        self.world_model = WorldModel(bot_config=self._bot_config)
        self.sensor_data_queue.clear()
        self.actuator_command_queue.clear()
        self.radar_frames.clear()
        self._sensor_index = 0
        self._telemetry_last_sent_mono = 0.0
        self._events_last_sent_mono = 0.0

    def apply_control_command(self, cmd: CommandMessage) -> bool:
        """
        Applies a control command to the simulation state (no mocks).

        This is intentionally limited to runtime toggles that do not require proto changes.
        """
        name = (cmd.command_name or "").strip()
        if not name:
            return False

        if name == "power.dock.on":
            self.world_model.set_dock_connected(True)
            return True
        if name == "power.dock.off":
            self.world_model.set_dock_connected(False)
            return True
        if name == "power.nbl.on":
            self.world_model.set_nbl_active(True)
            return True
        if name == "power.nbl.off":
            self.world_model.set_nbl_active(False)
            return True
        if name == "power.nbl.set_max":
            raw = (cmd.parameters or {}).get("max_power_w")
            if raw is None:
                return False
            self.world_model.set_nbl_max_power_w(raw)
            return True

        if name == "sim.start":
            raw_speed = (cmd.parameters or {}).get("speed", 1.0)
            try:
                speed = float(raw_speed)
            except Exception:
                speed = 1.0
            if speed <= 0:
                speed = 1.0
            self._sim_running = True
            self._sim_paused = False
            self._sim_speed = speed
            return True

        if name == "sim.pause":
            self._sim_running = True
            self._sim_paused = True
            return True

        if name == "sim.stop":
            self._sim_running = False
            self._sim_paused = False
            return True

        if name == "sim.reset":
            # Decision: reset implies stop.
            # Rationale: reset should be deterministic and never keep the world ticking implicitly.
            self._sim_running = False
            self._sim_paused = False
            self._sim_speed = 1.0
            self.reset_simulation()
            return True

        # Docking Plane (mechanical) operator control (no new proto).
        # NOTE: power bridge is still controlled via power.dock.on/off.
        if name == "sim.dock.engage":
            params = cmd.parameters or {}
            port = params.get("port")
            if port is not None and not self.world_model.set_docking_port(str(port)):
                return False
            if port is None and not self.world_model.set_docking_port(None):
                return False
            self.world_model.set_dock_connected(True)
            return True
        if name == "sim.dock.release":
            self.world_model.set_dock_connected(False)
            return True

        # RCS operator control (no new proto): drive existing RCS simulation via COMMANDS_CONTROL.
        if name == "sim.rcs.stop":
            return self.world_model.set_rcs_command(None, 0.0, 0.0)
        if name == "sim.rcs.fire":
            params = cmd.parameters or {}
            axis = params.get("axis")
            pct = params.get("pct")
            if pct is None:
                pct = params.get("percent")
            duration_s = params.get("duration_s")
            if duration_s is None:
                duration_s = params.get("duration")
            if axis is None or pct is None or duration_s is None:
                return False
            return self.world_model.set_rcs_command(str(axis), float(pct), float(duration_s))

        # Comms/XPDR operator control (no new proto): set transponder mode.
        if name == "sim.xpdr.mode":
            if not self._comms_enabled:
                return False
            params = cmd.parameters or {}
            raw_mode = str(params.get("mode") or "").strip().upper()
            if raw_mode not in {"ON", "OFF", "SILENT", "SPOOF"}:
                return False
            self.transponder_mode = self._parse_transponder_mode(raw_mode)
            # If switching into SPOOF, keep a stable spoof id for the session.
            if self.transponder_mode == TransponderModeEnum.SPOOF and not self._spoof_transponder_id:
                self._spoof_transponder_id = f"SPOOF-{uuid4().hex[:6].upper()}"
            return True

        return False

    def _load_bot_config(self) -> dict | None:
        env_path = os.getenv("QIKI_BOT_CONFIG_PATH", "").strip()
        candidates: list[Path] = []
        if env_path:
            candidates.append(Path(env_path))

        # Works both in repo runs and inside Docker (/workspace/src/...).
        repo_root = Path(__file__).resolve().parents[4]
        candidates.append(repo_root / "src/qiki/services/q_core_agent/config/bot_config.json")

        for path in candidates:
            try:
                if not path.exists():
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    logger.info(f"Loaded bot_config.json for simulation: {path}")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load bot_config.json from {path}: {e}")
        logger.warning("bot_config.json not found; simulation will use fallback defaults.")
        return None

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
                self.tick()
                time.sleep(self.config.sim_tick_interval)
        except KeyboardInterrupt:
            logger.info("QSimService stopped by user.")

    def tick(self) -> None:
        if self._sim_running and not self._sim_paused:
            delta_time = self.config.sim_tick_interval * float(self._sim_speed)
            self.step(delta_time=delta_time, advance_world=True, publish_radar=True)
            return
        # Paused/stopped: keep telemetry + sensor data alive, but freeze world and do not publish radar frames.
        self.step(delta_time=0.0, advance_world=False, publish_radar=False)

    def step(
        self,
        delta_time: float | None = None,
        *,
        advance_world: bool = True,
        publish_radar: bool = True,
    ) -> None:
        if delta_time is None:
            delta_time = float(self.config.sim_tick_interval)

        self.world_model.set_runtime_load_inputs(
            radar_enabled=self.radar_enabled,
            sensor_queue_depth=len(self.sensor_data_queue),
            actuator_queue_depth=len(self.actuator_command_queue),
            transponder_active=self._is_transponder_active(),
        )
        if advance_world:
            self.world_model.step(delta_time)

        # Commands are applied immediately on receipt, so treat the queue as a per-tick backlog/activity counter.
        # Clear it each tick to avoid unbounded growth impacting load simulation.
        self.actuator_command_queue.clear()

        self._maybe_publish_telemetry()
        self._maybe_publish_events()

        sensor_data = self.generate_sensor_data()
        self.sensor_data_queue.append(sensor_data)
        logger.debug(f"Generated sensor data: {MessageToDict(sensor_data)}")

        if publish_radar and self.radar_enabled and getattr(self.world_model, "radar_allowed", True):
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

    def _maybe_publish_events(self) -> None:
        if not self.events_nats_enabled:
            return
        if self._events_publisher is None:
            return

        now_mono = time.monotonic()
        if now_mono - self._events_last_sent_mono < self._events_interval_sec:
            return
        self._events_last_sent_mono = now_mono

        ts_epoch = time.time()
        # Minimal no-mocks sim events used by IncidentStore rules:
        # - TEMP_CORE_SPIKE: type=sensor, source=thermal, subject=core, payload.temp
        # - POWER_BUS_OVERLOAD: type=power, source=bus, subject=main, payload.current
        self._events_publisher.publish_event(
            SIM_SENSOR_THERMAL,
            {
                "schema_version": 1,
                "category": "sensor",
                "source": "thermal",
                "subject": "core",
                "temp": float(getattr(self.world_model, "temp_core_c", 0.0)),
                "ts_epoch": ts_epoch,
                "unit": "C",
            },
            event_type="qiki.events.v1.SensorReading",
            source="urn:qiki:q-sim-service:thermal",
        )
        self._events_publisher.publish_event(
            SIM_POWER_BUS,
            {
                "schema_version": 1,
                "category": "power",
                "source": "bus",
                "subject": "main",
                "current": float(getattr(self.world_model, "power_bus_a", 0.0)),
                "bus_v": float(getattr(self.world_model, "power_bus_v", 0.0)),
                "ts_epoch": ts_epoch,
                "unit": "A",
            },
            event_type="qiki.events.v1.PowerBusReading",
            source="urn:qiki:q-sim-service:power",
        )

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

        # Canonical: SoC lives under power.soc_pct. Keep top-level `battery` as legacy alias
        # to avoid breaking old consumers, but ensure it matches the canonical field.
        soc_pct: float | None = None
        try:
            power_block = state.get("power") if isinstance(state, dict) else None
            if isinstance(power_block, dict) and power_block.get("soc_pct") is not None:
                soc_pct = float(power_block.get("soc_pct"))
        except Exception:
            soc_pct = None
        if soc_pct is None:
            soc_pct = float(state.get("battery_level", 0.0))

        comms_plane = {}
        try:
            hp = (self._bot_config or {}).get("hardware_profile") if isinstance(self._bot_config, dict) else {}
            comms_plane = hp.get("comms_plane") if isinstance(hp, dict) else {}
            if not isinstance(comms_plane, dict):
                comms_plane = {}
        except Exception:
            comms_plane = {}

        comms = {
            "enabled": bool(comms_plane.get("enabled", True)),
            "xpdr": {
                "mode": self.transponder_mode.name,
                "active": bool(self._is_transponder_active()),
                "allowed": bool(getattr(self.world_model, "transponder_allowed", True)),
                "id": self._resolve_transponder_id(),
            },
        }

        payload = TelemetrySnapshotModel(
            source="q_sim_service",
            timestamp=ts,
            ts_unix_ms=ts_unix_ms,
            position={"x": x, "y": y, "z": z},
            velocity=float(state.get("speed", 0.0)),
            heading=float(state.get("heading", 0.0)),
            attitude={"roll_rad": roll, "pitch_rad": pitch, "yaw_rad": yaw},
            battery=float(soc_pct),
            cpu_usage=None if state.get("cpu_usage") is None else float(state.get("cpu_usage")),
            memory_usage=None if state.get("memory_usage") is None else float(state.get("memory_usage")),
            hull={"integrity": float(state.get("hull_integrity", 100.0))},
            power=state.get("power", {}),
            docking=state.get("docking", {}),
            sensor_plane=state.get("sensor_plane", {}),
            comms=comms,
            thermal=state.get("thermal", {"nodes": []}),
            propulsion=state.get("propulsion", {}),
            radiation_usvh=float(state.get("radiation_usvh", 0.0)),
            temp_external_c=float(state.get("temp_external_c", -60.0)),
            temp_core_c=float(state.get("temp_core_c", 25.0)),
        )
        out = payload.model_dump(mode="json")
        # Top-level extra key (TelemetrySnapshot v1 allows extras): trace which hardware profile is active.
        # No-mocks: if we cannot compute it (missing/bad config) -> omit.
        if self._hardware_profile_hash:
            out["hardware_profile_hash"] = self._hardware_profile_hash
        out["sim_state"] = self.get_sim_state()
        return out

    def _parse_transponder_mode(self, raw: str) -> TransponderModeEnum:
        mapping = {
            "ON": TransponderModeEnum.ON,
            "OFF": TransponderModeEnum.OFF,
            "SILENT": TransponderModeEnum.SILENT,
            "SPOOF": TransponderModeEnum.SPOOF,
        }
        return mapping.get(raw.upper(), TransponderModeEnum.ON)

    def _is_transponder_active(self) -> bool:
        if not self._comms_enabled:
            return False
        if not getattr(self.world_model, "transponder_allowed", True):
            return False
        return self.transponder_mode in (TransponderModeEnum.ON, TransponderModeEnum.SPOOF)

    def _resolve_transponder_id(self) -> str | None:
        if self.transponder_mode == TransponderModeEnum.ON:
            return self.transponder_id
        if self.transponder_mode == TransponderModeEnum.SPOOF:
            if not self._spoof_transponder_id:
                self._spoof_transponder_id = f"SPOOF-{uuid4().hex[:6].upper()}"
            return self._spoof_transponder_id
        return None
