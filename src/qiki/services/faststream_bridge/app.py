import logging
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass

from faststream import FastStream, Logger
from faststream.nats import JStream, NatsBroker
from pydantic import ValidationError

# Импортируем наши Pydantic модели
# Важно, чтобы PYTHONPATH был настроен правильно, чтобы найти shared
# В Docker-окружении это будет работать, так как корень проекта - /workspace
from qiki.shared.models.radar import RadarFrameModel
from qiki.shared.models.qiki_chat import QikiChatRequestV1, QikiChatResponseV1, QikiMode
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.nats_subjects import COMMANDS_CONTROL, EVENTS_AUDIT
from qiki.shared.nats_subjects import (
    QIKI_INTENTS,
    QIKI_RESPONSES,
    RADAR_FRAMES,
    RADAR_FRAMES_DURABLE as RADAR_FRAMES_DURABLE_DEFAULT,
    RADAR_STREAM_NAME,
    RADAR_TRACKS,
    RADAR_TRACKS_DURABLE as RADAR_TRACKS_DURABLE_DEFAULT,
)
from qiki.services.faststream_bridge.radar_handlers import frame_to_track
from qiki.services.faststream_bridge.track_publisher import RadarTrackPublisher
from qiki.services.faststream_bridge.lag_monitor import (
    ConsumerTarget,
    JetStreamLagMonitor,
)
from qiki.services.qiki_chat.handler import build_invalid_request_response_model, handle_chat_request
from qiki.services.faststream_bridge.mode_store import get_mode, set_mode
from qiki.shared.nats_subjects import SYSTEM_MODE_EVENT

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


@dataclass
class _StoredProposal:
    proposal_id: str
    actions: list[dict]
    ts_epoch: float


_proposal_store: dict[str, _StoredProposal] = {}


# Proposal store limits (avoid magic numbers; env-overridable).
_PROPOSAL_STORE_TTL_DEFAULT_SEC = 600.0
_PROPOSAL_STORE_TTL_MIN_SEC = 1.0
_PROPOSAL_STORE_MAX_DEFAULT = 500
_PROPOSAL_STORE_MAX_MIN = 10


def _proposal_store_ttl_s() -> float:
    try:
        raw = float(os.getenv("QIKI_PROPOSAL_STORE_TTL_SEC", str(_PROPOSAL_STORE_TTL_DEFAULT_SEC)))
    except Exception:
        return _PROPOSAL_STORE_TTL_DEFAULT_SEC
    return max(_PROPOSAL_STORE_TTL_MIN_SEC, raw)


def _proposal_store_max() -> int:
    try:
        raw = int(os.getenv("QIKI_PROPOSAL_STORE_MAX", str(_PROPOSAL_STORE_MAX_DEFAULT)))
    except Exception:
        return _PROPOSAL_STORE_MAX_DEFAULT
    return max(_PROPOSAL_STORE_MAX_MIN, raw)


def _proposal_store_gc(now_epoch: float) -> None:
    ttl = _proposal_store_ttl_s()
    for pid, item in list(_proposal_store.items()):
        if now_epoch - item.ts_epoch > ttl:
            _proposal_store.pop(pid, None)

    max_items = _proposal_store_max()
    if len(_proposal_store) <= max_items:
        return
    # Drop oldest first.
    for pid, _item in sorted(_proposal_store.items(), key=lambda kv: kv[1].ts_epoch)[
        : max(0, len(_proposal_store) - max_items)
    ]:
        _proposal_store.pop(pid, None)


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


def _parse_mode_change(text: str) -> QikiMode | None:
    raw = text.strip()
    low = raw.lower()
    if low.startswith("mode "):
        value = raw.split(" ", 1)[1].strip()
    elif low.startswith("режим "):
        value = raw.split(" ", 1)[1].strip()
    else:
        return None

    norm = value.strip().lower()
    if norm in {"factory", "завод"}:
        return QikiMode.FACTORY
    if norm in {"mission", "миссия"}:
        return QikiMode.MISSION
    return None


@broker.subscriber(QIKI_INTENTS)
@broker.publisher(QIKI_RESPONSES)
async def handle_qiki_intent(msg: dict, logger: Logger) -> dict:
    """Handle operator intent and return a strictly validated QikiChatResponseV1."""
    payload = msg if isinstance(msg, dict) else {}

    try:
        req = QikiChatRequestV1.model_validate(payload)
    except ValidationError:
        raw_req_id = payload.get("request_id") or payload.get("requestId")
        resp = build_invalid_request_response_model(
            str(raw_req_id) if raw_req_id is not None else None,
            current_mode=get_mode(),
        )
        return resp.model_dump(mode="json")

    logger.info("QIKI intent received: request_id=%s text=%r", req.request_id, req.input.text)
    if (new_mode := _parse_mode_change(req.input.text)) is not None:
        set_mode(new_mode)
        now = datetime.now(timezone.utc).isoformat()
        try:
            await broker.publish(
                {
                    "event_schema_version": 1,
                    "source": "faststream_bridge",
                    "subject": SYSTEM_MODE_EVENT,
                    "timestamp": now,
                    "mode": new_mode.value,
                },
                subject=SYSTEM_MODE_EVENT,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to publish system mode event: %s", exc)
    # Handle proposal decisions: execute stored actions on ACCEPT.
    if req.decision is not None:
        pid = str(req.decision.proposal_id)
        decision = req.decision.decision
        now_epoch = time.time()
        _proposal_store_gc(now_epoch)

        stored = _proposal_store.get(pid)
        if decision == "REJECT":
            _proposal_store.pop(pid, None)
            resp = handle_chat_request(req, current_mode=get_mode())
            return resp.model_dump(mode="json")

        # ACCEPT
        executed: list[str] = []
        if stored is not None:
            for action in stored.actions:
                try:
                    subject = str(action.get("subject") or "")
                    name = str(action.get("name") or "")
                    raw_params = action.get("parameters")
                    params = raw_params if isinstance(raw_params, dict) else {}
                    dry_run = bool(action.get("dry_run", True))
                    if dry_run:
                        continue
                    if subject != COMMANDS_CONTROL or not name:
                        continue

                    cmd = CommandMessage(
                        command_name=name,
                        parameters={str(k): v for k, v in params.items()},
                        metadata=MessageMetadata(
                            correlation_id=req.request_id,
                            message_type="control",
                            source="faststream_bridge",
                            destination="q_sim_service",
                        ),
                    )
                    await broker.publish(cmd.model_dump(mode="json"), subject=COMMANDS_CONTROL)
                    executed.append(name)
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed executing proposal action: %s", exc)

            try:
                await broker.publish(
                    {
                        "event_schema_version": 1,
                        "source": "faststream_bridge",
                        "subject": EVENTS_AUDIT,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "kind": "proposal_accept",
                        "proposal_id": pid,
                        "request_id": str(req.request_id),
                        "executed": executed,
                    },
                    subject=EVENTS_AUDIT,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to publish audit event: %s", exc)

        resp = handle_chat_request(req, current_mode=get_mode())
        return resp.model_dump(mode="json")

    # Regular intents: generate proposals and store their actions for later decisions.
    resp: QikiChatResponseV1 = handle_chat_request(req, current_mode=get_mode())
    now_epoch = time.time()
    _proposal_store_gc(now_epoch)
    for p in resp.proposals:
        actions = [a.model_dump(mode="json") for a in (p.proposed_actions or [])]
        _proposal_store[str(p.proposal_id)] = _StoredProposal(
            proposal_id=str(p.proposal_id),
            actions=actions,
            ts_epoch=now_epoch,
        )

    return resp.model_dump(mode="json")


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
    stream=JStream(name=RADAR_STREAM, declare=False),
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
        logger.debug("Track published with CloudEvents headers: track_id=%s", track.track_id)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to handle radar frame: %s", exc)
        fallback = frame_to_track(RadarFrameModel(sensor_id=msg.sensor_id, detections=[]))
        _track_publisher.publish_track(fallback)
