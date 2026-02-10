import logging
import asyncio
import contextlib
import json
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from uuid import uuid4

from faststream import FastStream, Logger
from faststream.nats import JStream, NatsBroker
from pydantic import ValidationError

# Импортируем наши Pydantic модели
# Важно, чтобы PYTHONPATH был настроен правильно, чтобы найти shared
# В Docker-окружении это будет работать, так как корень проекта - /workspace
from qiki.shared.models.radar import RadarFrameModel, RadarTrackModel
from qiki.shared.models.qiki_chat import BilingualText, QikiChatRequestV1, QikiChatResponseV1, QikiMode
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.nats_subjects import COMMANDS_CONTROL, EVENTS_AUDIT, EVENTS_STREAM_NAME
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
from qiki.services.faststream_bridge.radar_guard_cadence import RadarGuardCadence
from qiki.services.faststream_bridge.radar_guard_publisher import RadarGuardEventPublisher
from qiki.services.faststream_bridge.track_publisher import RadarTrackPublisher
from qiki.services.faststream_bridge.lag_monitor import (
    ConsumerTarget,
    JetStreamLagMonitor,
)
from qiki.services.q_core_agent.core.guard_table import GuardEvaluationResult, load_guard_table
from qiki.services.qiki_chat.handler import build_invalid_request_response_model, handle_chat_request
from qiki.services.faststream_bridge.mode_store import get_mode, set_mode
from qiki.shared.nats_subjects import RADAR_GUARD_ALERTS, SYSTEM_MODE_EVENT

try:
    import nats  # type: ignore
except Exception:  # pragma: no cover
    nats = None  # type: ignore

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


@dataclass(frozen=True)
class PublishResult:
    ok: bool
    reason: str
    event_id: str | None
    is_fallback: bool = False


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


_DOCKING_ACTION_PREFIXES = ("sim.dock.", "power.dock.")


def _is_docking_action(name: str) -> bool:
    low = str(name or "").lower()
    return any(low.startswith(prefix) for prefix in _DOCKING_ACTION_PREFIXES)


def _docking_actions_allowed(mode: QikiMode) -> bool:
    return mode == QikiMode.FACTORY


_track_publisher = RadarTrackPublisher(NATS_URL, subject=RADAR_TRACKS_SUBJECT)
_guard_events_enabled = os.getenv("RADAR_GUARD_EVENTS_ENABLED", "0").strip().lower() not in ("0", "false", "")
_guard_table = load_guard_table() if _guard_events_enabled else None
_guard_publisher = RadarGuardEventPublisher(NATS_URL, subject=RADAR_GUARD_ALERTS)
_guard_default_cooldown_s = max(0.1, float(os.getenv("RADAR_GUARD_PUBLISH_INTERVAL_S", "2.0").strip() or "2.0"))
_guard_cadence = (
    RadarGuardCadence(_guard_table, default_cooldown_s=_guard_default_cooldown_s) if _guard_table is not None else None
)
_lag_monitor = JetStreamLagMonitor(
    nats_url=NATS_URL,
    stream=RADAR_STREAM,
    consumers=[
        ConsumerTarget(durable=RADAR_FRAMES_DURABLE, label="radar_frames_pull"),
        ConsumerTarget(durable=RADAR_TRACKS_DURABLE, label="radar_tracks_pull"),
    ],
    interval_sec=LAG_MONITOR_INTERVAL,
)


def _allow_bridge_fallback() -> bool:
    return os.getenv("QIKI_ALLOW_BRIDGE_FALLBACK", "false").strip().lower() in ("1", "true", "yes", "on")


def _resolve_frame_from_bridge_input(msg: object) -> tuple[RadarFrameModel | None, PublishResult | None]:
    if isinstance(msg, RadarFrameModel):
        return msg, None

    # Explicit lower-layer contract input (InterfaceResult-like).
    if hasattr(msg, "ok"):
        ok = bool(getattr(msg, "ok"))
        reason = str(getattr(msg, "reason", "NO_DATA"))
        is_fallback = bool(getattr(msg, "is_fallback", False))
        value = getattr(msg, "value", None)

        if not ok:
            if is_fallback and _allow_bridge_fallback():
                frame = RadarFrameModel(sensor_id=uuid4(), detections=[])
                return frame, None
            return None, PublishResult(ok=False, reason=f"DROP:{reason}", event_id=None, is_fallback=is_fallback)

        if value is None:
            return None, PublishResult(ok=False, reason="DROP:OK_WITHOUT_VALUE", event_id=None, is_fallback=is_fallback)

        try:
            frame = RadarFrameModel.model_validate(value)
        except ValidationError as exc:
            return None, PublishResult(
                ok=False,
                reason=f"INVALID_INPUT_VALUE:{exc.__class__.__name__}",
                event_id=None,
                is_fallback=is_fallback,
            )
        return frame, None

    try:
        frame = RadarFrameModel.model_validate(msg)
    except ValidationError as exc:
        return None, PublishResult(ok=False, reason=f"INVALID_PAYLOAD:{exc.__class__.__name__}", event_id=None)
    return frame, None


def _validate_publishable_track(track: RadarTrackModel) -> None:
    # Keep bridge-level guard explicit: event without ID/time is not a valid fact.
    if track.track_id is None:
        raise ValueError("track_id is required")
    if track.timestamp is None:
        raise ValueError("timestamp is required")


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


_QIKI_INTENTS_SUBJECT = os.getenv("QIKI_INTENTS_SUBJECT", QIKI_INTENTS)
_QIKI_RESPONSES_SUBJECT = os.getenv("QIKI_RESPONSES_SUBJECT", QIKI_RESPONSES)


async def _publish_system_mode(mode: QikiMode, *, logger_: Logger) -> None:
    payload = {
        "event_schema_version": 1,
        "source": "faststream_bridge",
        "subject": SYSTEM_MODE_EVENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ts_epoch": float(time.time()),
        "mode": mode.value,
    }
    # ORION boot hydration relies on a persisted last-known system mode in JetStream.
    # Do a direct JetStream publish for determinism.
    if nats is not None:
        nc = None
        try:
            nc = await nats.connect(servers=[NATS_URL], connect_timeout=5)
            js = nc.jetstream()
            await js.publish(SYSTEM_MODE_EVENT, json.dumps(payload).encode("utf-8"))
            return
        except Exception as exc:
            logger_.warning("Failed to publish system mode to JetStream: %s", exc)
        finally:
            if nc is not None:
                with contextlib.suppress(Exception):
                    await nc.close()

    # Fallback: core-NATS publish (best-effort).
    try:
        await broker.publish(payload, subject=SYSTEM_MODE_EVENT)
    except Exception as exc:
        logger_.warning("Failed to publish system mode event: %s", exc)


async def _publish_system_mode_persisted_boot(mode: QikiMode, *, logger_: Logger) -> bool:
    """Publish system_mode with a deterministic persisted proof at boot.

    Why:
    - faststream-bridge can start before `nats-js-init` creates the events stream.
    - a JetStream publish before the stream exists is not persisted (and ORION shows N/A).
    """

    if nats is None:
        return False

    payload = {
        "event_schema_version": 1,
        "source": "faststream_bridge",
        "subject": SYSTEM_MODE_EVENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ts_epoch": float(time.time()),
        "mode": mode.value,
    }

    nc = None
    try:
        nc = await nats.connect(servers=[NATS_URL], connect_timeout=5)
        js = nc.jetstream()

        deadline = time.time() + float(os.getenv("SYSTEM_MODE_BOOT_PERSIST_TIMEOUT_SEC", "20.0"))
        while time.time() < deadline:
            try:
                await js.stream_info(EVENTS_STREAM_NAME)
                break
            except Exception:
                await asyncio.sleep(0.5)
        else:
            logger_.warning("Events stream not ready; system_mode not persisted at boot")
            return False

        await js.publish(SYSTEM_MODE_EVENT, json.dumps(payload).encode("utf-8"))
        # Proof: ensure the last message exists in the configured stream.
        await js.get_last_msg(EVENTS_STREAM_NAME, SYSTEM_MODE_EVENT)
        return True
    except Exception as exc:
        logger_.warning("Failed to persist boot system_mode in JetStream: %s", exc)
        return False
    finally:
        if nc is not None:
            with contextlib.suppress(Exception):
                await nc.close()


@broker.subscriber(_QIKI_INTENTS_SUBJECT)
@broker.publisher(_QIKI_RESPONSES_SUBJECT)
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
        await _publish_system_mode(new_mode, logger_=logger)
    current_mode = get_mode()
    # Handle proposal decisions: execute stored actions on ACCEPT.
    if req.decision is not None:
        pid = str(req.decision.proposal_id)
        decision = req.decision.decision
        now_epoch = time.time()
        _proposal_store_gc(now_epoch)

        stored = _proposal_store.get(pid)
        if decision == "REJECT":
            _proposal_store.pop(pid, None)
            resp = handle_chat_request(req, current_mode=current_mode)
            return resp.model_dump(mode="json")

        # ACCEPT
        executed: list[str] = []
        blocked: list[str] = []
        blocked_reason: str | None = None
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
                    if _is_docking_action(name) and not _docking_actions_allowed(current_mode):
                        blocked.append(name)
                        blocked_reason = "mode_mission"
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
                        "blocked": blocked,
                        "blocked_reason": blocked_reason,
                        "mode": current_mode.value,
                    },
                    subject=EVENTS_AUDIT,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to publish audit event: %s", exc)

        resp = handle_chat_request(req, current_mode=current_mode)
        if blocked:
            resp.warnings.append(
                BilingualText(
                    en="Docking commands are blocked in MISSION mode.",
                    ru="Команды стыковки заблокированы в режиме МИССИЯ.",
                )
            )
        return resp.model_dump(mode="json")

    # Regular intents: generate proposals and store their actions for later decisions.
    resp: QikiChatResponseV1 = handle_chat_request(req, current_mode=current_mode)
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


@app.after_startup
async def after_startup() -> None:
    # Publish the initial system mode once at boot, but make it deterministic:
    # ensure it's actually persisted in JetStream (ORION boot hydration).
    mode = get_mode()
    if not await _publish_system_mode_persisted_boot(mode, logger_=logger):
        # Fallback: best-effort publish so at least live subscribers see something.
        await _publish_system_mode(mode, logger_=logger)


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
async def handle_radar_frame(msg: object, logger: Logger) -> PublishResult:
    """
    Минимальный потребитель кадров радара.
    На данном этапе — только логирование метрик кадра.
    """
    frame, rejected = _resolve_frame_from_bridge_input(msg)
    if rejected is not None:
        logger.warning("Radar frame dropped: reason=%s", rejected.reason)
        return rejected
    assert frame is not None

    fallback_allowed = _allow_bridge_fallback()
    input_is_fallback = bool(getattr(msg, "is_fallback", False))
    effective_fallback = input_is_fallback and fallback_allowed

    try:
        count = len(frame.detections)
        logger.info(
            "Radar frame received: frame_id=%s sensor_id=%s detections=%d",
            frame.frame_id,
            frame.sensor_id,
            count,
        )
        # Минимальная агрегация: кадр -> трек
        track = frame_to_track(frame)
        _validate_publishable_track(track)
        published = _track_publisher.publish_track(
            track,
            extra_headers={
                "x-qiki-truth-state": "NO_DATA" if effective_fallback else "OK",
                "x-qiki-fallback": "true" if effective_fallback else "false",
            },
        )
        if not published:
            logger.warning("Track publish failed: track_id=%s", track.track_id)
            return PublishResult(ok=False, reason="UNAVAILABLE", event_id=None, is_fallback=effective_fallback)

        logger.debug("Track published with CloudEvents headers: track_id=%s", track.track_id)

        # Radar guards -> events -> ORION incidents (opt-in; no-mocks).
        if _guard_cadence is not None:
            for evaluation in _guard_cadence.update(track):
                _guard_publisher.publish_guard_alert(
                    _build_radar_guard_event_payload(track=track, evaluation=evaluation)
                )
        return PublishResult(
            ok=True,
            reason="PUBLISHED" if not effective_fallback else "SIMULATED_EVENT",
            event_id=str(track.track_id),
            is_fallback=effective_fallback,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to handle radar frame: %s", exc)
        if fallback_allowed:
            fallback_track = frame_to_track(RadarFrameModel(sensor_id=frame.sensor_id, detections=[]))
            _validate_publishable_track(fallback_track)
            published = _track_publisher.publish_track(
                fallback_track,
                extra_headers={"x-qiki-truth-state": "NO_DATA", "x-qiki-fallback": "true"},
            )
            if published:
                logger.warning("Fallback event published: track_id=%s reason=SIMULATED_EVENT", fallback_track.track_id)
                return PublishResult(
                    ok=True,
                    reason="SIMULATED_EVENT",
                    event_id=str(fallback_track.track_id),
                    is_fallback=True,
                )
        return PublishResult(ok=False, reason=f"DROP:{exc.__class__.__name__}", event_id=None, is_fallback=False)


def _build_radar_guard_event_payload(*, track: RadarTrackModel, evaluation: GuardEvaluationResult) -> dict:
    event_dt = track.ts_event or track.timestamp
    payload = {
        "schema_version": 1,
        "category": "radar",
        "kind": "guard_alert",
        "source": "guard",
        "subject": evaluation.rule_id,
        # Use simulation-truth time carried by the track.
        "ts_epoch": float(event_dt.timestamp()),
        "rule_id": evaluation.rule_id,
        # Provide a stable per-track identifier for deterministic incident keys.
        "id": str(evaluation.track_id),
        "track_id": str(evaluation.track_id),
        "fsm_event": evaluation.fsm_event,
        "severity": evaluation.severity,
        "message": evaluation.message,
        "range_m": float(evaluation.range_m),
        "quality": float(evaluation.quality),
        "iff": int(evaluation.iff),
        "transponder_on": bool(evaluation.transponder_on),
        "transponder_mode": int(evaluation.transponder_mode),
    }
    if track.ts_ingest is not None:
        payload["ts_ingest_epoch"] = float(track.ts_ingest.timestamp())
    return payload
