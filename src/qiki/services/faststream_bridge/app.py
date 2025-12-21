import logging
import os
from faststream import FastStream, Logger
from faststream.nats import NatsBroker

# Импортируем наши Pydantic модели
# Важно, чтобы PYTHONPATH был настроен правильно, чтобы найти shared
# В Docker-окружении это будет работать, так как корень проекта - /workspace
from qiki.shared.models.core import CommandMessage, ResponseMessage, MessageMetadata
from qiki.shared.models.radar import RadarFrameModel
from qiki.shared.nats_subjects import (
    COMMANDS_CONTROL,
    RADAR_FRAMES,
    RADAR_FRAMES_DURABLE as RADAR_FRAMES_DURABLE_DEFAULT,
    RADAR_STREAM_NAME,
    RADAR_TRACKS,
    RADAR_TRACKS_DURABLE as RADAR_TRACKS_DURABLE_DEFAULT,
    RESPONSES_CONTROL,
)
from qiki.services.faststream_bridge.radar_handlers import frame_to_track
from qiki.services.faststream_bridge.track_publisher import RadarTrackPublisher
from qiki.services.faststream_bridge.lag_monitor import (
    ConsumerTarget,
    JetStreamLagMonitor,
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация NATS брокера
NATS_URL = os.getenv("NATS_URL", "nats://qiki-nats-phase1:4222")
RADAR_FRAMES_SUBJECT = os.getenv("RADAR_FRAMES_SUBJECT", RADAR_FRAMES)
RADAR_TRACKS_SUBJECT = os.getenv("RADAR_TRACKS_SUBJECT", RADAR_TRACKS)
RADAR_FRAMES_DURABLE = os.getenv("RADAR_FRAMES_DURABLE", RADAR_FRAMES_DURABLE_DEFAULT)
RADAR_TRACKS_DURABLE = os.getenv("RADAR_TRACKS_DURABLE", RADAR_TRACKS_DURABLE_DEFAULT)
LAG_MONITOR_INTERVAL = float(os.getenv("RADAR_LAG_MONITOR_INTERVAL_SEC", "5"))
RADAR_STREAM = os.getenv("RADAR_STREAM", RADAR_STREAM_NAME)

broker = NatsBroker(NATS_URL)
app = FastStream(broker)

_track_publisher = RadarTrackPublisher(NATS_URL, subject=RADAR_TRACKS_SUBJECT)
_lag_monitor = JetStreamLagMonitor(
    nats_url=NATS_URL,
    stream=RADAR_STREAM,
    consumers=[
        ConsumerTarget(durable=RADAR_FRAMES_DURABLE, label="radar_frames_pull"),
        ConsumerTarget(durable=RADAR_TRACKS_DURABLE, label="radar_tracks_pull"),
    ],
    interval_sec=LAG_MONITOR_INTERVAL,
)


@broker.subscriber(COMMANDS_CONTROL)
@broker.publisher(RESPONSES_CONTROL)
async def handle_control_command(
    msg: CommandMessage, logger: Logger
) -> ResponseMessage:
    """
    Этот обработчик принимает команды управления, логирует их
    и возвращает простое подтверждение.
    """
    logger.info(f"Received command: {msg.command_name}")
    logger.info(f"Parameters: {msg.parameters}")

    # Простое бизнес-логика: отвечаем успехом
    response_payload = {
        "status": "Command received",
        "command": msg.command_name,
    }

    response = ResponseMessage(
        request_id=msg.metadata.message_id,
        metadata=MessageMetadata(
            source="faststream_bridge", correlation_id=msg.metadata.message_id
        ),
        payload=response_payload,
        success=True,
    )

    logger.info(f"Sending response: {response}")
    return response


@app.on_startup
async def on_startup():
    logger.info("FastStream bridge service has started.")
    await _lag_monitor.start()


@app.on_shutdown
async def on_shutdown():
    logger.info("FastStream bridge service is shutting down.")
    await _lag_monitor.stop()


# ------------------------ Radar frames handling ------------------------
@broker.subscriber(
    RADAR_FRAMES_SUBJECT,
    durable=RADAR_FRAMES_DURABLE,
    stream=RADAR_STREAM,
    pull_sub=True,
)
async def handle_radar_frame(msg: RadarFrameModel, logger: Logger) -> None:
    """
    Минимальный потребитель кадров радара.
    На данном этапе — только логирование метрик кадра.
    """
    try:
        count = len(msg.detections)
        logger.info(
            "Radar frame received: frame_id=%s sensor_id=%s detections=%d",
            msg.frame_id,
            msg.sensor_id,
            count,
        )
        # Минимальная агрегация: кадр -> трек
        track = frame_to_track(msg)
        _track_publisher.publish_track(track)
        logger.debug(
            "Track published with CloudEvents headers: track_id=%s", track.track_id
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to handle radar frame: %s", exc)
        fallback = frame_to_track(
            RadarFrameModel(sensor_id=msg.sensor_id, detections=[])
        )
        _track_publisher.publish_track(fallback)
