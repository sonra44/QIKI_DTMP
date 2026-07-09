from __future__ import annotations

import asyncio
import json
import os
import math
import re
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from qiki.services.q_core_agent.core.agent import QCoreAgent
from qiki.services.q_core_agent.core.agent_logger import logger, setup_logging
from qiki.services.q_core_agent.core.grpc_data_provider import GrpcDataProvider
from qiki.shared.config_models import QCoreAgentConfig, load_config
from qiki.shared.models.core import Proposal, SensorTypeEnum
from qiki.services.q_core_agent.core.body_structure import FACE_IDS, KNOWN_MOUNT_CLASSES
from qiki.services.q_core_agent.core.qiki_chat_llm import generate_qiki_reply, llm_dialog_enabled
from qiki.shared.body_status import (
    DOCKING_STATES,
    FSM_STATES,
    LINK_STATES,
    ORBIT_STATES,
    SENSOR_STATUSES,
)
from qiki.shared.module_catalog import CatalogResult, load_module_catalog
from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatRequestV1,
    QikiChatResponseV1,
    QikiConsequenceV1,
    QikiErrorV1,
    QikiLegalityV1,
    QikiMode,
    QikiProposedActionV1,
    QikiProposalV1,
    QikiReplyV1,
    QikiTrustSignalV1,
)
from qiki.shared.nats_subjects import (
    COMMANDS_CONTROL,
    EVENTS_AUDIT,
    OPERATOR_ACTIONS,
    OPERATOR_OBJECTIVES,
    QIKI_INTENTS,
    QIKI_RESPONSES,
    SYSTEM_TELEMETRY,
)
from qiki.shared.nats_subjects import OPENAI_API_KEY_UPDATE
from qiki.shared.models.qiki_chat_v2 import (
    DecisionPreview,
    EvidenceSourceType,
    ResponseEvidence,
    RuntimeClaimStatus,
    parse_chat_request,
    upgrade_response_to_v2,
)
from qiki.shared.nats_connect import nats_auth_kwargs

_STATION_OBJECT_TYPE = 3
_UNSPECIFIED_OBJECT_TYPE = 0
_SHIP_OBJECT_TYPE = 2
_STATION_INFLUENCE_RADIUS_M = 35_000.0
_COMBAT_ENTRY_MIN_PROPELLANT_KG = 2.0
_HOSTILE_DEFERRED_RESOURCE_CODES = {
    "COMBAT_ENTRY_RCS_NO_DATA",
    "COMBAT_ENTRY_THERMAL_WARN",
    "COMBAT_ENTRY_COMMS_LINK_DEGRADED",
}
_COMMS_STALE_AFTER_S = 3.0
_COMMS_EXPIRE_AFTER_S = 12.0
_IMU_STALE_AFTER_S = 2.5
_IMU_EXPIRE_AFTER_S = 10.0
_RESUME_OBJECTIVE_STALE_AFTER_S = 90.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reply_body_for_text(*, text: str) -> BilingualText:
    t = (text or "").strip()
    low = t.lower()
    if low in {"ping", "пинг"}:
        return BilingualText(en="pong", ru="понг")
    if not t:
        return BilingualText(en="OK", ru="ОК")
    # Keep it compact; ORION output is a small strip.
    compact = t if len(t) <= 160 else (t[:157] + "...")
    return BilingualText(en=f"OK: {compact}", ru=f"ОК: {compact}")


def _merge_reasoning_snapshot(
    world_snapshot: dict[str, Any] | None,
    telemetry_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge radar-centric world state with the latest telemetry-backed subsystem truth."""

    merged: dict[str, Any] = {}

    if isinstance(telemetry_snapshot, dict):
        for key, value in telemetry_snapshot.items():
            merged[key] = value

    if isinstance(world_snapshot, dict):
        for key, value in world_snapshot.items():
            merged[key] = value

    return merged


def _current_reasoning_snapshot(*, agent: QCoreAgent, telemetry_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Build a fresh reasoning snapshot from the agent's latest radar state and telemetry cache."""

    return _merge_reasoning_snapshot(
        agent.context.world_snapshot,
        telemetry_snapshot,
    )


def _merge_sensor_source(
    world_snapshot: dict[str, Any] | None,
    sensor_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    """Prefer raw sensor fields without discarding richer world-snapshot sections."""

    merged: dict[str, Any] = {}
    if isinstance(world_snapshot, dict):
        merged.update(world_snapshot)

    if not isinstance(sensor_snapshot, dict):
        return merged

    for key, value in sensor_snapshot.items():
        if (
            key == "sensor_plane"
            and isinstance(value, dict)
            and isinstance(merged.get("sensor_plane"), dict)
        ):
            sensor_plane = dict(merged["sensor_plane"])
            sensor_plane.update(value)
            merged["sensor_plane"] = sensor_plane
            continue
        merged[key] = value

    return merged


def _parse_snapshot_timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if numeric > 10_000_000_000:
            return numeric / 1000.0
        if numeric > 0:
            return numeric
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None
    return None


def _section_freshness(
    snapshot: dict[str, Any] | None,
    *,
    section: str,
    stale_after_s: float,
    expire_after_s: float,
    now_ts: float | None = None,
) -> dict[str, Any]:
    now = float(now_ts if isinstance(now_ts, (int, float)) else time.time())
    if not isinstance(snapshot, dict):
        return {"state": "absent", "age_s": None, "source_ts": None}

    payload = snapshot.get(section)
    if not isinstance(payload, dict):
        return {"state": "absent", "age_s": None, "source_ts": None}

    source_ts = _parse_snapshot_timestamp(payload.get("last_seen_ts"))
    if source_ts is None:
        source_ts = _parse_snapshot_timestamp(snapshot.get("ts_epoch"))
    if source_ts is None:
        source_ts = _parse_snapshot_timestamp(snapshot.get("ts_unix_ms"))
    if source_ts is None:
        source_ts = _parse_snapshot_timestamp(snapshot.get("timestamp"))

    age_s: float | None = None
    raw_age = payload.get("age_s")
    if source_ts is not None:
        if source_ts > now + 1.0:
            return {"state": "stale", "age_s": max(expire_after_s, stale_after_s), "source_ts": source_ts}
        age_s = max(0.0, now - source_ts)
    elif isinstance(raw_age, (int, float)) and not isinstance(raw_age, bool):
        age_s = max(0.0, float(raw_age))

    if age_s is None:
        return {"state": "absent", "age_s": None, "source_ts": None}
    if age_s >= max(expire_after_s, stale_after_s):
        return {"state": "stale", "age_s": age_s, "source_ts": now - age_s}
    if age_s >= stale_after_s:
        return {"state": "stale", "age_s": age_s, "source_ts": now - age_s}
    return {"state": "fresh", "age_s": age_s, "source_ts": now - age_s}


def _string_codes(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()


def _primary_comms_reason(comms: dict[str, Any], default: str) -> str:
    reason_codes = _string_codes(comms.get("reason_codes"))
    return reason_codes[0] if reason_codes else default


def _comms_reason_text(comms: dict[str, Any], default: str) -> str:
    text = str(comms.get("reason_text") or "").strip()
    return text or default


def _observation_route_role(*, observation_style: str, procedure_name: str) -> str:
    style = observation_style.strip().lower()
    procedure = procedure_name.strip().lower()
    if style == "slow" or procedure == "safe_pause_slow_resume":
        return "deviation"
    return "official"


def _observation_follow_up_contract(
    *,
    follow_up_status: str,
    route_role: str,
    procedure_name: str,
    target_designator: str,
) -> dict[str, str] | None:
    status = str(follow_up_status or "").strip().lower()
    if status not in {"review_required", "review_completed", "hold_for_recheck", "resume_observation"}:
        return None
    target_text = str(target_designator or "").strip() or "observation target"
    procedure_text = str(procedure_name or "").strip() or "deviation procedure"
    route_text = str(route_role or "").strip().lower() or "deviation"
    if status == "resume_observation":
        return {
            "status": "resume_observation",
            "reason_code": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
            "event_type": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
            "summary_en": (
                f"Observation resume is selected: close hold_for_recheck for {target_text} after "
                f"{route_text} route {procedure_text}, and return to one cautious safe observation step."
            ),
            "summary_ru": (
                f"Выбран resume observation: снимите hold_for_recheck для {target_text} после маршрута "
                f"{route_text} ({procedure_text}) и вернитесь к одному осторожному шагу safe observation."
            ),
            "allowed_when_en": (
                f"Issue one cautious safe observation for {target_text} to resume the observation contour "
                "on the canonical path."
            ),
            "allowed_when_ru": (
                f"Теперь задайте один осторожный safe observation для {target_text}, чтобы возобновить "
                "observation contour на каноническом path."
            ),
        }
    if status == "hold_for_recheck":
        return {
            "status": "hold_for_recheck",
            "reason_code": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
            "event_type": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
            "summary_en": (
                f"Post-review hold for recheck is selected: keep {target_text} on a cautious recheck contour "
                f"after {route_text} route {procedure_text} before resuming the next observation objective."
            ),
            "summary_ru": (
                f"Выбран post-review hold for recheck: удерживайте {target_text} на осторожном recheck-контуре "
                f"после маршрута {route_text} ({procedure_text}) перед следующей observation-целью."
            ),
            "allowed_when_en": (
                "Run a cautious safe recheck for the same target before resuming the next general observation objective."
            ),
            "allowed_when_ru": (
                "Сначала выполните осторожный safe recheck для той же цели, затем возвращайтесь к следующей общей observation-цели."
            ),
        }
    if status == "review_completed":
        return {
            "status": "review_completed",
            "reason_code": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
            "event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
            "summary_en": (
                f"Hidden-event review is closed: the linked fact from {route_text} route "
                f"{procedure_text} for {target_text} was acknowledged, and one post-review follow-up choice is now open."
            ),
            "summary_ru": (
                f"Review скрытого события закрыт: связанный факт после маршрута {route_text} "
                f"({procedure_text}) для {target_text} подтверждён, и теперь открыт один post-review follow-up choice."
            ),
            "allowed_when_en": "Select the post-review follow-up choice before issuing the next observation objective.",
            "allowed_when_ru": "Сначала выберите post-review follow-up choice, затем задавайте следующую observation-цель.",
        }
    return {
        "status": "review_required",
        "reason_code": "HIDDEN_EVENT_REVIEW_REQUIRED",
        "event_type": "HIDDEN_EVENT_REVEALED",
        "summary_en": (
            f"Hidden-event follow-up is required: review the linked fact from {route_text} route "
            f"{procedure_text} for {target_text} before issuing the next observation objective."
        ),
        "summary_ru": (
            f"Нужен follow-up по скрытому событию: проверьте связанный факт после маршрута {route_text} "
            f"({procedure_text}) для {target_text} перед следующей observation-целью."
        ),
        "allowed_when_en": "Review the linked hidden fact before issuing the next observation objective.",
        "allowed_when_ru": "Сначала проверьте связанный hidden fact, затем задавайте следующую observation-цель.",
    }


def _observation_follow_up_fields(
    *,
    follow_up_status: str,
    route_role: str,
    procedure_name: str,
    target_designator: str,
) -> dict[str, str]:
    contract = _observation_follow_up_contract(
        follow_up_status=follow_up_status,
        route_role=route_role,
        procedure_name=procedure_name,
        target_designator=target_designator,
    )
    if contract is None:
        return {}
    return {
        "follow_up_status": contract["status"],
        "follow_up_reason_code": contract["reason_code"],
        "follow_up_event_type": contract["event_type"],
        "follow_up_summary_en": contract["summary_en"],
        "follow_up_summary_ru": contract["summary_ru"],
        "follow_up_allowed_when_en": contract["allowed_when_en"],
        "follow_up_allowed_when_ru": contract["allowed_when_ru"],
    }


def _observation_identity_key(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    for field in ("objective_id", "proposal_id", "request_id"):
        value = str(payload.get(field) or "").strip()
        if value:
            return f"{field}:{value}"
    return None


def _observation_payload_age_s(payload: dict[str, Any] | None, *, now_ts: float | None = None) -> float | None:
    if not isinstance(payload, dict):
        return None
    raw_ts = payload.get("ts_epoch")
    if not isinstance(raw_ts, (int, float)) or isinstance(raw_ts, bool):
        return None
    current_ts = time.time() if now_ts is None else float(now_ts)
    return max(0.0, current_ts - float(raw_ts))


def _find_resumable_observation_objective(
    latest_observation_objectives: dict[str, dict[str, Any]],
    *,
    target_designator: str | None,
) -> dict[str, Any] | None:
    target_text = str(target_designator or "").strip().upper()
    candidates: list[dict[str, Any]] = []
    stale_candidates = 0
    for payload in latest_observation_objectives.values():
        if not isinstance(payload, dict):
            continue
        if str(payload.get("objective_type") or "").strip().lower() != "observation":
            continue
        if str(payload.get("follow_up_status") or "").strip().lower() != "resume_observation":
            continue
        payload_target = str(payload.get("target_designator") or "").strip().upper()
        if target_text and payload_target and payload_target != target_text:
            continue
        payload_age_s = _observation_payload_age_s(payload)
        if payload_age_s is not None and payload_age_s > _RESUME_OBJECTIVE_STALE_AFTER_S:
            stale_candidates += 1
            continue
        candidates.append(payload)
    if not candidates:
        logger.info(
            "Resume objective lookup: target=%s matched=0 stale_skipped=%s",
            target_designator,
            stale_candidates,
        )
        return None
    selected = max(candidates, key=lambda payload: float(payload.get("ts_epoch") or 0.0))
    logger.info(
        "Resume objective lookup: target=%s matched=%s stale_skipped=%s objective_id=%s request_id=%s qcore_track_id=%s qcore_label=%s public_track_id=%s public_label=%s",
        target_designator,
        len(candidates),
        stale_candidates,
        str(selected.get("objective_id") or "").strip(),
        str(selected.get("request_id") or "").strip(),
        str(selected.get("track_id") or "").strip(),
        str(selected.get("track_label") or "").strip(),
        str(selected.get("public_track_id") or "").strip(),
        str(selected.get("public_track_label") or "").strip(),
    )
    return selected


def _build_observation_follow_up_update(
    *,
    objective_event: dict[str, Any] | None,
    action_event: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(objective_event, dict) or not isinstance(action_event, dict):
        return None
    if str(objective_event.get("objective_type") or "").strip().lower() != "observation":
        return None
    event_type = str(action_event.get("event_type") or "").strip()
    if event_type == "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED":
        follow_up_status = "review_completed"
        objective_reason_code = "OBJECTIVE_REVIEW_CLOSED"
    elif event_type == "HIDDEN_EVENT_RECHECK_HOLD_SELECTED":
        follow_up_status = "hold_for_recheck"
        objective_reason_code = "OBJECTIVE_POST_REVIEW_HOLD_SELECTED"
    elif event_type == "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED":
        follow_up_status = "resume_observation"
        objective_reason_code = "OBJECTIVE_RESUME_OBSERVATION_SELECTED"
    else:
        return None
    follow_up = _observation_follow_up_contract(
        follow_up_status=follow_up_status,
        route_role=str(action_event.get("route_role") or objective_event.get("route_role") or "").strip().lower(),
        procedure_name=str(action_event.get("procedure_name") or objective_event.get("procedure_name") or "").strip(),
        target_designator=str(
            action_event.get("target_designator") or objective_event.get("target_designator") or ""
        ).strip(),
    )
    if follow_up is None:
        return None
    payload = dict(objective_event)
    payload.update(
        {
            "event_schema_version": 1,
            "source": "q_core_intents",
            "subject": OPERATOR_OBJECTIVES,
            "timestamp": _now_iso(),
            "ts_epoch": float(time.time()),
            "kind": "observation_objective_update",
            "status": "confirmed",
            "summary_en": follow_up["summary_en"],
            "summary_ru": follow_up["summary_ru"],
            "reason_code": objective_reason_code,
            "route_role": str(action_event.get("route_role") or objective_event.get("route_role") or "").strip().lower(),
            "procedure_name": str(action_event.get("procedure_name") or objective_event.get("procedure_name") or "").strip(),
            "target_designator": str(
                action_event.get("target_designator") or objective_event.get("target_designator") or ""
            ).strip(),
        }
    )
    payload.update(
        _observation_follow_up_fields(
            follow_up_status=follow_up_status,
            route_role=str(payload.get("route_role") or "").strip().lower(),
            procedure_name=str(payload.get("procedure_name") or "").strip(),
            target_designator=str(payload.get("target_designator") or "").strip(),
        )
    )
    return payload


def _build_observation_objective_event(
    *,
    req: QikiChatRequestV1,
    response: QikiChatResponseV1,
    procedure_name: str,
    observation_style: str,
    world_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    proposal = response.proposals[0] if response.proposals else None
    consequence = response.consequence
    legality = response.legality
    title_ru = response.reply.title.ru if response.reply is not None else ""
    title_en = response.reply.title.en if response.reply is not None else ""
    summary_ru = consequence.summary.ru if consequence is not None else ""
    summary_en = consequence.summary.en if consequence is not None else ""
    target_designator = _extract_target_designator(req.input.text)
    target_track = _find_target_track(world_snapshot, target_designator)
    track_visible = isinstance(target_track, dict)
    track_id = _track_object_identity(target_track) if track_visible else ""
    track_label = _track_visible_signature(target_track) if track_visible else ""
    try:
        track_range_m = float(target_track.get("range_m") or 0.0) if track_visible else None
    except Exception:
        track_range_m = None
    try:
        track_quality = max(0.0, min(1.0, float(target_track.get("quality") or 0.0))) if track_visible else None
    except Exception:
        track_quality = None
    objective_id = f"observation-{req.request_id}"
    route_role = _observation_route_role(observation_style=observation_style, procedure_name=procedure_name)
    payload = {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": OPERATOR_OBJECTIVES,
        "timestamp": _now_iso(),
        "ts_epoch": float(time.time()),
        "kind": "observation_objective_seed",
        "objective_id": objective_id,
        "objective_type": "observation",
        "status": "prepared",
        "observation_style": observation_style,
        "procedure_name": procedure_name,
        "route_role": route_role,
        "request_id": str(req.request_id),
        "proposal_id": str(proposal.proposal_id) if proposal is not None else "",
        "mode": mode.value if (mode := response.mode) else QikiMode.FACTORY.value,
        "target_designator": target_designator,
        "track_visible": track_visible,
        "object_identity": track_id or None,
        "visible_signature": track_label or None,
        "track_id": track_id or None,
        "track_label": track_label or None,
        "track_range_m": track_range_m,
        "track_quality": track_quality,
        "title_ru": title_ru,
        "title_en": title_en,
        "summary_ru": summary_ru,
        "summary_en": summary_en,
        "reason_code": legality.reason_code if legality is not None else "",
    }
    if route_role == "deviation":
        payload.update(
            _observation_follow_up_fields(
                follow_up_status="review_required",
                route_role=route_role,
                procedure_name=procedure_name,
                target_designator=target_designator,
            )
        )
    return payload


def _build_observation_hidden_event(*, objective_event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(objective_event, dict):
        return None
    route_role = str(objective_event.get("route_role") or "").strip().lower()
    if route_role != "deviation":
        return None
    target_designator = str(objective_event.get("target_designator") or "").strip()
    procedure_name = str(objective_event.get("procedure_name") or "").strip()
    target_text = target_designator or "observation target"
    return {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": EVENTS_AUDIT,
        "timestamp": _now_iso(),
        "ts_epoch": float(time.time()),
        "event_type": "HIDDEN_EVENT_REVEALED",
        "objective_id": str(objective_event.get("objective_id") or "").strip(),
        "proposal_id": str(objective_event.get("proposal_id") or "").strip(),
        "request_id": str(objective_event.get("request_id") or "").strip(),
        "procedure_name": procedure_name,
        "target_designator": target_designator,
        "route_role": route_role,
        "reason_code": "DEVIATION_ROUTE_REVEALS_HIDDEN_OBSERVATION_EVENT",
        "message": (
            f"Deviation route {procedure_name} раскрыл скрытый observation fact для {target_text}."
            if procedure_name
            else f"Deviation route раскрыл скрытый observation fact для {target_text}."
        ),
    }


def _log_observation_track_context(*, target_designator: str | None, world_snapshot: dict[str, Any] | None) -> None:
    radar_tracks = world_snapshot.get("radar_tracks") if isinstance(world_snapshot, dict) else None
    track_count = len(radar_tracks) if isinstance(radar_tracks, list) else 0
    target_track = _find_target_track(world_snapshot, target_designator)
    logger.info(
        "Observation target-track context: target=%s track_count=%s matched=%s matched_track_id=%s matched_label=%s",
        target_designator,
        track_count,
        isinstance(target_track, dict),
        (str(target_track.get("track_id") or "") if isinstance(target_track, dict) else ""),
        (
            str(target_track.get("transponder_id") or target_track.get("id") or target_track.get("callsign") or "")
            if isinstance(target_track, dict)
            else ""
        ),
    )


def _proposal_to_qiki(p: Proposal) -> QikiProposalV1:
    title = BilingualText(en=f"{p.type.name}", ru=f"{p.type.name}")
    justification = BilingualText(en=p.justification, ru=p.justification)
    # QIKI chat schema expects priority 0..100.
    priority = int(max(0, min(100, round(float(p.priority) * 100))))
    confidence = float(max(0.0, min(1.0, float(p.confidence))))
    return QikiProposalV1(
        proposal_id=str(p.proposal_id),
        title=title,
        justification=justification,
        confidence=confidence,
        priority=priority,
        suggested_questions=[],
        proposed_actions=[],
    )


def _build_invalid_request_response(*, raw_request_id: str | None, mode: QikiMode) -> QikiChatResponseV1:
    request_id = uuid4()
    if raw_request_id:
        try:
            request_id = UUID(str(raw_request_id))
        except Exception:  # noqa: BLE001
            request_id = uuid4()

    return QikiChatResponseV1(
        request_id=request_id,
        ok=False,
        mode=mode,
        reply=None,
        proposals=[],
        warnings=[BilingualText(en="INVALID REQUEST", ru="НЕВЕРНЫЙ ЗАПРОС")],
        error=QikiErrorV1(
            code="INVALID_REQUEST",
            message=BilingualText(
                en="Request JSON does not match QikiChatRequest.v1",
                ru="JSON запроса не соответствует QikiChatRequest.v1",
            ),
        ),
    )


def _is_protocol_blocked_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    # Вопрос о стыковке — беседа, не команда (B5-фикс: без ложных блоков)
    if "?" in low or re.search(r"\b(расскажи|что такое|как|почему|можно ли)\b", low):
        return False
    if low.startswith(("dock", "undock", "стыков", "расстыков", "стыковка", "разстыковка")):
        return True
    # Императив стыковки в любом месте фразы («выполни стыковку», «состыкуйся»)
    return bool(re.search(r"\b(выполни|начни|сделай|произведи)\b.{0,30}\bстыковк", low)) or "состыкуйся" in low


def _is_release_dock_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    triggers = (
        "release dock",
        "undock",
        "release docking",
        "отстыков",
        "расстыков",
        "отстыковаться",
        # B4-ru: живые русские формы («отстыкуйся», «отстыкуй нас», «расстыкуйся»)
        "отстыкуй",
        "расстыкуй",
    )
    return any(trigger in low for trigger in triggers)


def _is_attach_module_command(text: str) -> bool:
    """P2: глагол установки + любой объект установки (модуль/класс/id).

    Срез 3 (понимание): живые глаголы оператора («пристыкуй», «приладь»,
    «воткни»…) — фиксированный словарь policy, не LLM (CaMeL цел). Глагол
    БЕЗ объекта установки — не команда (беседа).
    """
    low = " ".join((text or "").strip().lower().split())
    # Отрицание/вопрос — беседа, не команда (ревью: кандидат на риторический
    # вопрос запрещён; «не надо…» не должно готовить установку).
    if "?" in low or re.search(r"\b(не|нельзя|можно ли|почему|зачем)\b", low):
        return False
    verbs = (
        "установи", "установить", "поставь", "смонтируй", "attach", "install",
        "пристыкуй", "пристыковать", "приладь", "приладить", "воткни", "воткнуть",
        "закрепи", "закрепить", "подключи", "подключить", "прикрути", "прикрутить",
        "навесь", "навесить",
    )
    objects = ("модул", "сенсор", "датчик", "антенн", "зонд", "научн", "module", "sensor", "antenna", "probe", "science", "rcs")
    return any(verb in low for verb in verbs) and any(obj in low for obj in objects)


def _is_cargo_list_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    triggers = (
        "доложи отсек",
        "доложи грузовой отсек",
        "какие модули",
        "список модулей",
        "что в отсеке",
        "cargo list",
        "list modules",
    )
    return any(trigger in low for trigger in triggers)


def _is_station_approach_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    triggers = (
        "approach station",
        "station approach",
        "approach target",
        "station intercept",
        "approach dock",
        "сближение со станцией",
        "сближение со шлюзом",
        "подход к станции",
        "подойти к станции",
        "подход к шлюзу",
    )
    return any(trigger in low for trigger in triggers)


def _is_station_hail_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    triggers = (
        "hail station",
        "contact station",
        "open station channel",
        "station channel",
        "station contact",
        "связь со станцией",
        "вызвать станцию",
        "связаться со станцией",
        "открыть канал станции",
        "канал связи со станцией",
    )
    return any(trigger in low for trigger in triggers)


def _is_docking_corridor_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    triggers = (
        "docking corridor",
        "enter docking corridor",
        "request docking corridor",
        "approach docking corridor",
        "коридор стыковки",
        "войти в коридор стыковки",
        "запросить коридор стыковки",
        "коридор сближения",
    )
    return any(trigger in low for trigger in triggers)


def _is_attitude_stabilize_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    triggers = (
        "stabilize attitude",
        "attitude hold",
        "hold attitude",
        "stabilize orientation",
        "attitude stabilization",
        "стабилизировать ориентацию",
        "стабилизировать курс",
        "удерживать ориентацию",
        "стабилизация ориентации",
    )
    return any(trigger in low for trigger in triggers)


def _is_safe_observation_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    triggers = (
        "safe observation",
        "stabilize observation",
        "safe stabilize observation",
        "safe observation mode",
        "подготовь безопасную стабилизацию наблюдения",
        "безопасная стабилизация наблюдения",
        "стабилизируй наблюдение безопасно",
        "режим безопасного наблюдения",
    )
    return any(trigger in low for trigger in triggers)


def _is_slow_observation_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    triggers = (
        "slow observation",
        "slow observe",
        "slow scan",
        "careful observation",
        "prepare slow observation",
        "подготовь медленное наблюдение",
        "медленное наблюдение",
        "режим медленного наблюдения",
        "медленный обзор",
    )
    return any(trigger in low for trigger in triggers)


def _is_hostile_attack_command(text: str) -> bool:
    low = " ".join((text or "").strip().lower().split())
    triggers = (
        "attack object",
        "attack target",
        "engage target",
        "engage hostile",
        "fire on",
        "атакуй объект",
        "атаковать объект",
        "атакуй цель",
        "огонь по",
        "атаковать цель",
    )
    return any(trigger in low for trigger in triggers)


def _extract_target_designator(text: str) -> str | None:
    tokens = re.findall(r"[A-Za-zА-Яа-я0-9_-]{4,}", text or "")
    for token in reversed(tokens):
        up = token.upper()
        if up in {"ATTACK", "OBJECT", "TARGET", "ENGAGE"}:
            continue
        if up in {"АТАКУЙ", "АТАКОВАТЬ", "ОБЪЕКТ", "ЦЕЛЬ"}:
            continue
        if any(ch.isdigit() for ch in up):
            return up
    return None


def _best_station_track(world_snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(world_snapshot, dict):
        return None
    tracks = world_snapshot.get("radar_tracks")
    if not isinstance(tracks, list):
        return None

    station_tracks = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        object_type = track.get("object_type")
        if str(object_type) not in {str(_STATION_OBJECT_TYPE), "ObjectTypeEnum.STATION", "STATION"}:
            continue
        try:
            range_m = float(track.get("range_m", 0.0) or 0.0)
        except Exception:
            continue
        if range_m <= 0.0:
            continue
        station_tracks.append((range_m, track))

    if not station_tracks:
        return None
    station_tracks.sort(key=lambda item: item[0])
    return station_tracks[0][1]


def _find_target_track(world_snapshot: dict[str, Any] | None, target_designator: str | None) -> dict[str, Any] | None:
    if not isinstance(world_snapshot, dict) or not target_designator:
        return None
    tracks = world_snapshot.get("radar_tracks")
    if not isinstance(tracks, list):
        return None

    needle = str(target_designator).strip().upper()
    matches: list[tuple[float, dict[str, Any]]] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        object_type = track.get("object_type")
        if str(object_type) not in {
            str(_UNSPECIFIED_OBJECT_TYPE),
            str(_SHIP_OBJECT_TYPE),
            "ObjectTypeEnum.OBJECT_TYPE_UNSPECIFIED",
            "ObjectTypeEnum.SHIP",
            "OBJECT_TYPE_UNSPECIFIED",
            "SHIP",
        }:
            continue
        labels = [
            str(track.get("visible_signature") or "").strip().upper(),
            str(track.get("transponder_id") or "").strip().upper(),
            str(track.get("id") or "").strip().upper(),
            str(track.get("callsign") or "").strip().upper(),
        ]
        if needle not in {label for label in labels if label}:
            continue
        try:
            range_m = float(track.get("range_m", 0.0) or 0.0)
        except Exception:
            range_m = 0.0
        matches.append((range_m if range_m > 0.0 else 1e12, track))

    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[0][1]


def _find_track_by_runtime_id(world_snapshot: dict[str, Any] | None, track_id: str | None) -> dict[str, Any] | None:
    if not isinstance(world_snapshot, dict):
        return None
    needle = str(track_id or "").strip()
    if not needle:
        return None
    tracks = world_snapshot.get("radar_tracks")
    if not isinstance(tracks, list):
        return None
    for track in tracks:
        if not isinstance(track, dict):
            continue
        if str(track.get("object_identity") or track.get("track_id") or "").strip() == needle:
            return track
    return None


def _track_object_identity(track: dict[str, Any] | None) -> str:
    if not isinstance(track, dict):
        return ""
    return str(track.get("object_identity") or track.get("track_id") or "").strip()


def _track_visible_signature(track: dict[str, Any] | None) -> str:
    if not isinstance(track, dict):
        return ""
    return str(track.get("visible_signature") or track.get("transponder_id") or track.get("id") or track.get("callsign") or "").strip()


def _track_display_label(track: dict[str, Any] | None) -> str:
    return _track_visible_signature(track)


def _resume_track_identity(track: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(track, dict):
        return {"track_id": "", "track_label": ""}
    return {
        "track_id": _track_object_identity(track),
        "track_label": _track_visible_signature(track),
    }


def _resumable_contour_track_snapshot(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    contour_track_id = str(
        payload.get("object_identity") or payload.get("track_id") or payload.get("observation_track_id") or ""
    ).strip()
    contour_track_label = str(
        payload.get("visible_signature")
        or payload.get("track_label")
        or payload.get("observation_track_label")
        or ""
    ).strip()
    contour_snapshot: dict[str, Any] = {
        "observation_track_id": contour_track_id or None,
        "observation_track_label": contour_track_label or None,
        "public_track_id": str(payload.get("public_track_id") or "").strip() or None,
        "public_track_label": str(payload.get("public_track_label") or "").strip() or None,
    }
    track_range_m = payload.get("track_range_m")
    if track_range_m is None:
        track_range_m = payload.get("observation_track_range_m")
    if isinstance(track_range_m, (int, float)) and not isinstance(track_range_m, bool):
        contour_snapshot["observation_track_range_m"] = float(track_range_m)
    track_quality = payload.get("track_quality")
    if track_quality is None:
        track_quality = payload.get("observation_track_quality")
    if isinstance(track_quality, (int, float)) and not isinstance(track_quality, bool):
        contour_snapshot["observation_track_quality"] = max(0.0, min(1.0, float(track_quality)))
    return contour_snapshot


def _select_target_track_for_resume(
    world_snapshot: dict[str, Any] | None,
    *,
    target_designator: str | None,
    preferred_track_id: str | None = None,
    preferred_public_track_id: str | None = None,
    allow_designator_fallback: bool = True,
) -> tuple[dict[str, Any] | None, str]:
    preferred_id = str(preferred_track_id or "").strip()
    if preferred_id:
        preferred_track = _find_track_by_runtime_id(world_snapshot, preferred_id)
        if preferred_track is not None:
            return preferred_track, "direct_contour_match"
    public_preferred_id = str(preferred_public_track_id or "").strip()
    if public_preferred_id:
        public_preferred_track = _find_track_by_runtime_id(world_snapshot, public_preferred_id)
        if public_preferred_track is not None:
            return public_preferred_track, "public_contour_match"
    if (preferred_id or public_preferred_id) and not allow_designator_fallback:
        return None, "contour_miss"
    fallback_track = _find_target_track(world_snapshot, target_designator)
    if fallback_track is not None:
        return fallback_track, "fallback_by_designator"
    return None, "no_match"


def _find_target_track_for_resume(
    world_snapshot: dict[str, Any] | None,
    *,
    target_designator: str | None,
    preferred_track_id: str | None = None,
    preferred_public_track_id: str | None = None,
    allow_designator_fallback: bool = True,
) -> dict[str, Any] | None:
    selected_track, _ = _select_target_track_for_resume(
        world_snapshot,
        target_designator=target_designator,
        preferred_track_id=preferred_track_id,
        preferred_public_track_id=preferred_public_track_id,
        allow_designator_fallback=allow_designator_fallback,
    )
    return selected_track


def _observation_track_snapshot(
    track: dict[str, Any] | None,
    *,
    fallback_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = dict(fallback_snapshot or {})
    if not isinstance(track, dict):
        return snapshot
    track_id = str(track.get("track_id") or "").strip()
    track_label = _track_display_label(track)
    try:
        track_range_m = float(track.get("range_m") or 0.0)
    except Exception:
        track_range_m = None
    try:
        track_quality = max(0.0, min(1.0, float(track.get("quality") or 0.0)))
    except Exception:
        track_quality = None
    snapshot.update(
        {
            "observation_track_id": track_id or snapshot.get("observation_track_id"),
            "observation_track_label": track_label or snapshot.get("observation_track_label"),
            "observation_track_range_m": track_range_m if track_range_m is not None else snapshot.get("observation_track_range_m"),
            "observation_track_quality": (
                track_quality if track_quality is not None else snapshot.get("observation_track_quality")
            ),
        }
    )
    return snapshot


def _target_has_open_hostile_context(track: dict[str, Any] | None) -> bool:
    if not isinstance(track, dict):
        return False
    iff = str(track.get("iff") or track.get("iff_class") or track.get("iffClass") or "").strip().upper()
    return iff in {"2", "FOE", "FRIENDFOEENUM.FOE"}


def _combat_resource_gate(
    world_snapshot: dict[str, Any] | None,
) -> tuple[str, BilingualText, list[QikiTrustSignalV1]] | None:
    if not isinstance(world_snapshot, dict):
        return None

    propulsion = world_snapshot.get("propulsion")
    rcs = propulsion.get("rcs") if isinstance(propulsion, dict) else None
    if not isinstance(rcs, dict):
        reason = BilingualText(
            en="RCS telemetry is unavailable, so QIKI cannot validate combat-entry resource readiness.",
            ru="Телеметрия RCS недоступна, поэтому QIKI не может подтвердить ресурсную готовность входа в бой.",
        )
        return (
            "COMBAT_ENTRY_RCS_NO_DATA",
            reason,
            [
                QikiTrustSignalV1(
                    label=BilingualText(en="RCS resource contour", ru="RCS ресурсный контур"),
                    state="off",
                    source="sensor",
                    confidence=0.0,
                    reason_code="COMBAT_ENTRY_RCS_NO_DATA",
                    reason=reason,
                )
            ],
        )

    enabled = bool(rcs.get("enabled", False))
    try:
        propellant_kg = float(rcs.get("propellant_kg") or 0.0)
    except Exception:
        propellant_kg = 0.0
    if (not enabled) or propellant_kg < _COMBAT_ENTRY_MIN_PROPELLANT_KG:
        reason = BilingualText(
            en=(
                f"RCS combat-entry contour is not ready: enabled={enabled}, "
                f"propellant_kg={propellant_kg:.2f}, minimum={_COMBAT_ENTRY_MIN_PROPELLANT_KG:.2f}."
            ),
            ru=(
                f"RCS-контур входа в бой не готов: enabled={enabled}, "
                f"propellant_kg={propellant_kg:.2f}, минимум={_COMBAT_ENTRY_MIN_PROPELLANT_KG:.2f}."
            ),
        )
        return (
            "COMBAT_ENTRY_RCS_RESOURCE_LOW",
            reason,
            [
                QikiTrustSignalV1(
                    label=BilingualText(en="RCS resource contour", ru="RCS ресурсный контур"),
                    state="failed" if not enabled else "degraded",
                    source="sensor",
                    confidence=(
                        0.0
                        if not enabled
                        else max(0.0, min(1.0, propellant_kg / _COMBAT_ENTRY_MIN_PROPELLANT_KG))
                    ),
                    reason_code="COMBAT_ENTRY_RCS_RESOURCE_LOW",
                    reason=reason,
                )
            ],
        )

    power = world_snapshot.get("power")
    if isinstance(power, dict):
        pdu_throttled = bool(power.get("pdu_throttled", False))
        shed_reasons_raw = power.get("shed_reasons") or []
        throttled_raw = power.get("throttled_loads") or []
        shed_reasons = [str(item).strip().lower() for item in shed_reasons_raw if str(item).strip()]
        throttled_loads = [str(item).strip().lower() for item in throttled_raw if str(item).strip()]
        if "pdu_overcurrent" in shed_reasons or (pdu_throttled and "rcs" in throttled_loads):
            reason = BilingualText(
                en=(
                    "Power contour reports PDU overcurrent during hostile entry, so QIKI will not stack another "
                    "combat-entry burst until the bus recovers."
                ),
                ru=(
                    "Энергетический контур сообщает о перегрузке PDU во время hostile-входа, поэтому QIKI не будет "
                    "накладывать следующий combat-entry импульс, пока шина не восстановится."
                ),
            )
            return (
                "COMBAT_ENTRY_POWER_OVERCURRENT",
                reason,
                [
                    QikiTrustSignalV1(
                        label=BilingualText(en="Power combat contour", ru="Энергетический боевой контур"),
                        state="failed" if pdu_throttled else "degraded",
                        source="sensor",
                        confidence=0.0 if pdu_throttled else 0.25,
                        reason_code="COMBAT_ENTRY_POWER_OVERCURRENT",
                        reason=reason,
                    )
                ],
            )

    thermal = world_snapshot.get("thermal")
    if isinstance(thermal, dict):
        thermal_nodes = thermal.get("nodes")
        if isinstance(thermal_nodes, list):
            warned_nodes = [
                str(node.get("id"))
                for node in thermal_nodes
                if isinstance(node, dict) and bool(node.get("warned")) and not bool(node.get("tripped"))
            ]
            tripped_nodes = [
                str(node.get("id"))
                for node in thermal_nodes
                if isinstance(node, dict) and bool(node.get("tripped"))
            ]
            if tripped_nodes:
                nodes_ru = ", ".join(tripped_nodes)
                reason = BilingualText(
                    en=(
                        "Thermal contour reports a tripped combat-risk node "
                        f"({', '.join(tripped_nodes)}), so QIKI will not continue hostile entry."
                    ),
                    ru=(
                        "Тепловой контур сообщает о tripped-узле боевого риска "
                        f"({nodes_ru}), поэтому QIKI не продолжит hostile-вход."
                    ),
                )
                return (
                    "COMBAT_ENTRY_THERMAL_TRIP",
                    reason,
                    [
                        QikiTrustSignalV1(
                            label=BilingualText(en="Thermal combat contour", ru="Тепловой боевой контур"),
                            state="failed",
                            source="sensor",
                            confidence=0.0,
                            reason_code="COMBAT_ENTRY_THERMAL_TRIP",
                            reason=reason,
                        )
                    ],
                )
            if warned_nodes:
                nodes_ru = ", ".join(warned_nodes)
                reason = BilingualText(
                    en=(
                        "Thermal contour still shows warned combat-risk nodes "
                        f"({', '.join(warned_nodes)}), so QIKI defers the next hostile step until they cool down."
                    ),
                    ru=(
                        "Тепловой контур всё ещё показывает warned-узлы боевого риска "
                        f"({nodes_ru}), поэтому QIKI откладывает следующий hostile-шаг, пока они не остынут."
                    ),
                )
                return (
                    "COMBAT_ENTRY_THERMAL_WARN",
                    reason,
                    [
                        QikiTrustSignalV1(
                            label=BilingualText(en="Thermal combat contour", ru="Тепловой боевой контур"),
                            state="degraded",
                            source="sensor",
                            confidence=0.35,
                            reason_code="COMBAT_ENTRY_THERMAL_WARN",
                            reason=reason,
                        )
                    ],
                )

        thermal_warning = str(thermal.get("warning") or "").strip().lower()
        core_state = str(thermal.get("core_state") or "").strip().lower()
        if any(flag in thermal_warning for flag in ("crit", "trip", "alarm")) or core_state in {"trip", "critical"}:
            reason = BilingualText(
                en="Thermal contour reports a combat-risk state, so QIKI will not continue hostile entry right now.",
                ru="Тепловой контур сообщает о боевом риск-состоянии, поэтому QIKI сейчас не продолжит hostile-вход.",
            )
            return (
                "COMBAT_ENTRY_THERMAL_RISK",
                reason,
                [
                    QikiTrustSignalV1(
                        label=BilingualText(en="Thermal combat contour", ru="Тепловой боевой контур"),
                        state="failed",
                        source="sensor",
                        confidence=0.0,
                        reason_code="COMBAT_ENTRY_THERMAL_RISK",
                        reason=reason,
                    )
                ],
            )

    comms = world_snapshot.get("comms")
    if not isinstance(comms, dict):
        return None

    plane_enabled = bool(comms.get("plane_enabled", comms.get("enabled", False)))
    link_state = str(comms.get("link_state") or comms.get("link") or "").strip().lower()
    antenna_status = str(comms.get("antenna_status") or "").strip().lower()
    try:
        data_rate_kbps = float(comms.get("data_rate_kbps") or 0.0)
    except Exception:
        data_rate_kbps = 0.0
    latency_ms = comms.get("latency_ms")
    packet_loss_pct = comms.get("packet_loss_pct")

    if not plane_enabled:
        reason = BilingualText(
            en=(
                "Combat follow-up is blocked because the communications plane is disabled "
                "in the active hardware profile."
            ),
            ru="Combat follow-up заблокирован, потому что контур связи отключён в активном аппаратном профиле.",
        )
        return (
            "COMBAT_ENTRY_COMMS_PLANE_DISABLED",
            reason,
            [
                QikiTrustSignalV1(
                    label=BilingualText(en="Combat link state", ru="Состояние боевого канала"),
                    state="off",
                    source="sensor",
                    confidence=1.0,
                    reason_code="COMBAT_ENTRY_COMMS_PLANE_DISABLED",
                    reason=reason,
                )
            ],
        )

    if link_state == "offline":
        reason = BilingualText(
            en="Combat follow-up is blocked because the communications link is offline.",
            ru="Combat follow-up заблокирован, потому что канал связи находится offline.",
        )
        return (
            "COMBAT_ENTRY_COMMS_LINK_OFFLINE",
            reason,
            [
                QikiTrustSignalV1(
                    label=BilingualText(en="Combat link state", ru="Состояние боевого канала"),
                    state="failed",
                    source="sensor",
                    confidence=1.0,
                    reason_code="COMBAT_ENTRY_COMMS_LINK_OFFLINE",
                    reason=reason,
                )
            ],
        )

    degraded_link = (
        link_state != "online"
        or antenna_status != "lock"
        or data_rate_kbps <= 0.0
        or (isinstance(packet_loss_pct, (int, float)) and float(packet_loss_pct) >= 15.0)
        or (isinstance(latency_ms, (int, float)) and float(latency_ms) >= 900.0)
    )
    if degraded_link:
        latency_text = f"{float(latency_ms):.0f} ms" if isinstance(latency_ms, (int, float)) else "n/a"
        loss_text = f"{float(packet_loss_pct):.1f}%" if isinstance(packet_loss_pct, (int, float)) else "n/a"
        reason = BilingualText(
            en=(
                "Combat follow-up is deferred until the target-link stabilizes: "
                f"state={link_state or 'unknown'}, latency={latency_text}, loss={loss_text}, "
                f"antenna={antenna_status or 'unlock'}, data_rate_kbps={data_rate_kbps:.1f}."
            ),
            ru=(
                "Combat follow-up отложен до стабилизации target-link: "
                f"state={link_state or 'unknown'}, latency={latency_text}, loss={loss_text}, "
                f"antenna={antenna_status or 'unlock'}, data_rate_kbps={data_rate_kbps:.1f}."
            ),
        )
        return (
            "COMBAT_ENTRY_COMMS_LINK_DEGRADED",
            reason,
            [
                QikiTrustSignalV1(
                    label=BilingualText(en="Combat link state", ru="Состояние боевого канала"),
                    state="degraded",
                    source="sensor",
                    confidence=0.35,
                    reason_code="COMBAT_ENTRY_COMMS_LINK_DEGRADED",
                    reason=reason,
                )
            ],
        )

    return None


def _combat_entry_tactical_state(world_snapshot: dict[str, Any] | None) -> tuple[str, BilingualText] | None:
    if not isinstance(world_snapshot, dict):
        return None
    propulsion = world_snapshot.get("propulsion")
    rcs = propulsion.get("rcs") if isinstance(propulsion, dict) else None
    if not isinstance(rcs, dict):
        return None
    try:
        command_pct = float(rcs.get("command_pct") or 0.0)
        time_left_s = float(rcs.get("time_left_s") or 0.0)
    except Exception:
        command_pct = 0.0
        time_left_s = 0.0
    active = bool(rcs.get("active", False))
    if not active and (command_pct <= 0.0 or time_left_s <= 0.0):
        return None
    reason = BilingualText(
        en=(
            f"Combat-entry pulse is already active: command_pct={command_pct:.1f}, "
            f"time_left_s={time_left_s:.2f}. QIKI will not stack the same intercept burst twice."
        ),
        ru=(
            f"Combat-entry импульс уже активен: command_pct={command_pct:.1f}, "
            f"time_left_s={time_left_s:.2f}. QIKI не будет накладывать один и тот же перехватный импульс повторно."
        ),
    )
    return ("TACTICAL_STATE_INTERCEPT_ACTIVE", reason)


def _register_repeat_refusal(*, agent: QCoreAgent, key: str) -> int:
    state = agent.context.qiki_repeat_state if isinstance(agent.context.qiki_repeat_state, dict) else {}
    count = int(state.get(key, 0) or 0) + 1
    state[key] = count
    if len(state) > 32:
        removable = [item for item in state.keys() if item != key]
        for item in removable[: len(state) - 32]:
            state.pop(item, None)
    agent.context.qiki_repeat_state = state
    return count


def _build_hostile_attack_block_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    world_snapshot: dict[str, Any] | None,
    agent: QCoreAgent,
) -> QikiChatResponseV1:
    target_designator = _extract_target_designator(req.input.text)
    target_track = _find_target_track(world_snapshot, target_designator)
    station_track = _best_station_track(world_snapshot)

    if target_track is None:
        reason = BilingualText(
            en="QIKI cannot identify the requested hostile target from current radar truth.",
            ru="QIKI не может идентифицировать запрошенную цель по текущей радарной истине.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Attack deferred", ru="Атака отложена"),
                body=BilingualText(
                    en="The requested target is not tracked reliably enough for combat arbitration.",
                    ru="Запрошенная цель пока не отслеживается достаточно надёжно для боевого арбитража.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="HOSTILE_TARGET_NO_DATA",
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry when the target appears as a trusted ship track with a stable identifier.",
                    ru=(
                        "Повторите попытку, когда цель появится как доверенный "
                        "корабельный трек со стабильным идентификатором."
                    ),
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Hostile target track", ru="Трек враждебной цели"),
                    state="off",
                    source="sensor",
                    confidence=0.0,
                    reason_code="HOSTILE_TARGET_NO_DATA",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Combat execution was not started.",
                    ru="Боевое исполнение не запускалось.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No combat command or control-bus action was emitted.",
                    ru="Ни боевая команда, ни действие на control bus не отправлялись.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    station_range_m = None
    if isinstance(station_track, dict):
        try:
            station_range_m = float(station_track.get("range_m", 0.0) or 0.0)
        except Exception:
            station_range_m = None

    if station_range_m is not None and 0.0 < station_range_m <= _STATION_INFLUENCE_RADIUS_M:
        repeat_key = f"attack:{target_designator or 'unknown'}:station_influence"
        repeat_count = _register_repeat_refusal(agent=agent, key=repeat_key)
        terse = repeat_count >= 4
        reason = BilingualText(
            en=(
                f"Station influence remains active at {station_range_m:.0f} m; "
                "combat initiation is blocked by the current protocol context."
            ),
            ru=(
                f"Влияние станции остаётся активным на дистанции {station_range_m:.0f} м; "
                "инициирование боя заблокировано текущим протокольным контекстом."
            ),
        )
        body = (
            BilingualText(
                en="No. The station protocol still blocks combat here.",
                ru="Нет. Протокол станции всё ещё блокирует бой здесь.",
            )
            if terse
            else BilingualText(
                en=(
                    f"QIKI will not initiate combat against {target_designator or 'the target'} "
                    "while station influence "
                    f"is active inside {int(_STATION_INFLUENCE_RADIUS_M):d} m."
                ),
                ru=(
                    f"QIKI не начнёт бой против {target_designator or 'цели'}, пока влияние станции активно "
                    f"в пределах {int(_STATION_INFLUENCE_RADIUS_M):d} м."
                ),
            )
        )
        reply_title = (
            BilingualText(en="Attack denied", ru="Атака отклонена")
            if terse
            else BilingualText(en="Attack blocked", ru="Атака заблокирована")
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(title=reply_title, body=body),
            legality=QikiLegalityV1(
                status="blocked",
                domain="protocol",
                reason_code="STATION_COMBAT_PROTOCOL_BLOCK",
                reason=reason,
                allowed_when=BilingualText(
                    en=(
                        "Leave the active station-influence radius or wait until the protocol context changes "
                        "before retrying combat initiation."
                    ),
                    ru=(
                        "Покиньте активную зону влияния станции или дождитесь смены протокольного контекста "
                        "перед повторной попыткой инициировать бой."
                    ),
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station influence", ru="Влияние станции"),
                    state="healthy",
                    source="derived",
                    confidence=1.0,
                    reason_code="STATION_COMBAT_PROTOCOL_BLOCK",
                    reason=reason,
                ),
                QikiTrustSignalV1(
                    label=BilingualText(en="Hostile target track", ru="Трек враждебной цели"),
                    state="healthy",
                    source="sensor",
                    confidence=float(target_track.get("quality", 1.0) or 1.0),
                    reason_code="HOSTILE_TARGET_TRACKED",
                    reason=BilingualText(
                        en=(
                            f"Target {target_designator or 'UNKNOWN'} remains tracked, "
                            "but the protocol block takes priority."
                        ),
                        ru=(
                            f"Цель {target_designator or 'UNKNOWN'} отслеживается, "
                            "но приоритет остаётся за протокольной блокировкой."
                        ),
                    ),
                ),
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Combat execution was not started because the protocol block remained active.",
                    ru="Боевое исполнение не запускалось, потому что протокольная блокировка осталась активной.",
                ),
                telemetry_confirmation=BilingualText(
                    en=(
                        f"Station track range={station_range_m:.0f} m inside influence radius "
                        f"{_STATION_INFLUENCE_RADIUS_M:.0f} m; no combat action was emitted."
                    ),
                    ru=(
                        f"Дистанция до станции={station_range_m:.0f} м внутри радиуса влияния "
                        f"{_STATION_INFLUENCE_RADIUS_M:.0f} м; боевое действие не отправлялось."
                    ),
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    hostile_context_open = _target_has_open_hostile_context(target_track)
    target_quality = float(target_track.get("quality", 1.0) or 1.0)
    if not hostile_context_open:
        reason = BilingualText(
            en=(
                f"Target {target_designator or 'UNKNOWN'} is tracked and station influence is no longer active, "
                "but hostile context is still not open because the track is not classified as FOE."
            ),
            ru=(
                f"Цель {target_designator or 'UNKNOWN'} отслеживается, и station-влияние уже не активно, "
                "но hostile-контекст ещё не открыт, потому что трек не классифицирован как FOE."
            ),
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Attack deferred", ru="Атака отложена"),
                body=BilingualText(
                    en=(
                        "QIKI will not open hostile combat entry yet: the target remains unclassified even though "
                        "the station block is gone."
                    ),
                    ru=(
                        "QIKI пока не откроет hostile-вход в бой: station-блокировки уже нет, "
                        "но цель всё ещё не классифицирована."
                    ),
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="protocol",
                reason_code="HOSTILE_CONTEXT_NOT_OPEN",
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry when the target is classified as FOE by current radar truth.",
                    ru="Повторите попытку, когда цель будет классифицирована как FOE по текущей радарной истине.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Hostile target track", ru="Трек враждебной цели"),
                    state="healthy",
                    source="sensor",
                    confidence=target_quality,
                    reason_code="HOSTILE_TARGET_TRACKED",
                    reason=BilingualText(
                        en=f"Target {target_designator or 'UNKNOWN'} is tracked with sufficient confidence.",
                        ru=f"Цель {target_designator or 'UNKNOWN'} отслеживается с достаточным уровнем доверия.",
                    ),
                ),
                QikiTrustSignalV1(
                    label=BilingualText(en="Hostile context", ru="Hostile-контекст"),
                    state="degraded",
                    source="derived",
                    confidence=0.0,
                    reason_code="HOSTILE_CONTEXT_NOT_OPEN",
                    reason=reason,
                ),
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Combat execution remains locked because hostile context is not open yet.",
                    ru="Боевое исполнение остаётся закрытым, потому что hostile-контекст ещё не открыт.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No combat command was emitted; target track still lacks FOE classification.",
                    ru="Боевая команда не отправлялась; у трека цели всё ещё нет классификации FOE.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    resource_gate = _combat_resource_gate(world_snapshot)
    if resource_gate is not None:
        reason_code, reason, resource_trust = resource_gate
        legality_status = "deferred" if reason_code in _HOSTILE_DEFERRED_RESOURCE_CODES else "blocked"
        reply_title = "Combat entry deferred" if legality_status == "deferred" else "Combat entry blocked"
        reply_title_ru = "Вход в бой отложен" if legality_status == "deferred" else "Вход в бой заблокирован"
        reply_body = (
            BilingualText(
                en="QIKI cannot continue hostile entry because RCS telemetry is missing.",
                ru="QIKI не может продолжить hostile-вход, потому что телеметрия RCS отсутствует.",
            )
            if reason_code == "COMBAT_ENTRY_RCS_NO_DATA"
            else BilingualText(
                en=(
                    "QIKI defers the next hostile step because the thermal contour still reports warned combat-risk "
                    "nodes after the previous intercept burst."
                ),
                ru=(
                    "QIKI откладывает следующий hostile-шаг, потому что тепловой контур всё ещё сообщает о "
                    "warned-узлах боевого риска после предыдущего перехватного импульса."
                ),
            )
            if reason_code == "COMBAT_ENTRY_THERMAL_WARN"
            else BilingualText(
                en=(
                    "QIKI blocks the next hostile step because the thermal contour remains in a tripped combat-risk "
                    "state after the previous intercept burst."
                ),
                ru=(
                    "QIKI блокирует следующий hostile-шаг, потому что тепловой контур остаётся в tripped-состоянии "
                    "боевого риска после предыдущего перехватного импульса."
                ),
            )
            if reason_code == "COMBAT_ENTRY_THERMAL_TRIP"
            else BilingualText(
                en=(
                    "QIKI defers the next hostile step because the combat target-link is still degraded after the "
                    "previous intercept burst."
                ),
                ru=(
                    "QIKI откладывает следующий hostile-шаг, потому что боевой target-link всё ещё деградирован "
                    "после предыдущего перехватного импульса."
                ),
            )
            if reason_code == "COMBAT_ENTRY_COMMS_LINK_DEGRADED"
            else BilingualText(
                en="QIKI blocks the next hostile step because the communications link is offline.",
                ru="QIKI блокирует следующий hostile-шаг, потому что канал связи находится offline.",
            )
            if reason_code == "COMBAT_ENTRY_COMMS_LINK_OFFLINE"
            else BilingualText(
                en="QIKI blocks the next hostile step because the communications plane is disabled.",
                ru="QIKI блокирует следующий hostile-шаг, потому что контур связи отключён.",
            )
            if reason_code == "COMBAT_ENTRY_COMMS_PLANE_DISABLED"
            else BilingualText(
                en=(
                    "QIKI will not continue hostile entry because the power contour is still in PDU overcurrent "
                    "after the previous intercept burst."
                ),
                ru=(
                    "QIKI не продолжит hostile-вход, потому что энергетический контур всё ещё находится "
                    "в состоянии PDU overcurrent после предыдущего перехватного импульса."
                ),
            )
            if reason_code == "COMBAT_ENTRY_POWER_OVERCURRENT"
            else BilingualText(
                en=(
                    "QIKI will not continue hostile entry because the combat-entry resource contour is not ready "
                    "for a controlled intercept burst."
                ),
                ru=(
                    "QIKI не продолжит hostile-вход, потому что ресурсный контур combat-entry не готов "
                    "к контролируемому перехватному импульсу."
                ),
            )
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en=reply_title, ru=reply_title_ru),
                body=reply_body,
            ),
            legality=QikiLegalityV1(
                status=legality_status,
                domain="resource",
                reason_code=reason_code,
                reason=reason,
                allowed_when=BilingualText(
                    en=(
                        "Retry when RCS telemetry is online, propellant remains above the combat-entry minimum, "
                        "the power contour is no longer in PDU overcurrent, and the thermal contour leaves warned "
                        "or critical combat-risk state, and the combat target-link is online and stable."
                    ),
                    ru=(
                        "Повторите попытку, когда телеметрия RCS снова доступна, запас propellant будет выше "
                        "боевого минимума, энергетический контур выйдет из PDU-overcurrent, а тепловой контур "
                        "покинет warned или критическое риск-состояние, а боевой target-link станет online "
                        "и стабильным."
                    ),
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Hostile target track", ru="Трек враждебной цели"),
                    state="healthy",
                    source="sensor",
                    confidence=target_quality,
                    reason_code="HOSTILE_TARGET_TRACKED",
                    reason=BilingualText(
                        en=(
                            f"Target {target_designator or 'UNKNOWN'} is still tracked "
                            "with sufficient confidence."
                        ),
                        ru=(
                            f"Цель {target_designator or 'UNKNOWN'} всё ещё отслеживается "
                            "с достаточным уровнем доверия."
                        ),
                    ),
                ),
                QikiTrustSignalV1(
                    label=BilingualText(en="Hostile context", ru="Hostile-контекст"),
                    state="healthy",
                    source="derived",
                    confidence=1.0,
                    reason_code="HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK",
                    reason=BilingualText(
                        en="Hostile context remains open by FOE classification.",
                        ru="Hostile-контекст остаётся открытым по классификации FOE.",
                    ),
                ),
                *resource_trust,
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Combat-entry continuation was not started because the resource contour is not ready.",
                    ru="Продолжение combat-entry не запускалось, потому что ресурсный контур не готов.",
                ),
                telemetry_confirmation=BilingualText(
                    en=(
                        "No hostile combat-entry procedure was prepared or emitted "
                        "on the current resource state."
                    ),
                    ru=(
                        "При текущем ресурсном состоянии hostile combat-entry "
                        "процедура не подготавливалась и не отправлялась."
                    ),
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    tactical_state = _combat_entry_tactical_state(world_snapshot)
    if tactical_state is not None:
        reason_code, reason = tactical_state
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Intercept already active", ru="Перехват уже активен"),
                body=BilingualText(
                    en=(
                        "QIKI sees that the initial combat-entry pulse is already moving the craft into intercept. "
                        "The next step is to hold track and reassess after the current burst completes."
                    ),
                    ru=(
                        "QIKI видит, что начальный combat-entry импульс уже переводит аппарат в перехват. "
                        "Следующий шаг — удерживать трек и переоценить ситуацию после завершения текущего импульса."
                    ),
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="protocol",
                reason_code=reason_code,
                reason=reason,
                allowed_when=BilingualText(
                    en=(
                        "Wait for the active intercept pulse to finish, then retry if you need a new follow-up step "
                        "based on the updated tactical state."
                    ),
                    ru=(
                        "Дождитесь завершения активного перехватного импульса, затем повторите запрос, "
                        "если понадобится новый follow-up шаг по обновлённому тактическому состоянию."
                    ),
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Hostile target track", ru="Трек враждебной цели"),
                    state="healthy",
                    source="sensor",
                    confidence=target_quality,
                    reason_code="HOSTILE_TARGET_TRACKED",
                    reason=BilingualText(
                        en=(
                            f"Target {target_designator or 'UNKNOWN'} is still tracked "
                            "with sufficient confidence."
                        ),
                        ru=(
                            f"Цель {target_designator or 'UNKNOWN'} всё ещё отслеживается "
                            "с достаточным уровнем доверия."
                        ),
                    ),
                ),
                QikiTrustSignalV1(
                    label=BilingualText(en="Hostile context", ru="Hostile-контекст"),
                    state="healthy",
                    source="derived",
                    confidence=1.0,
                    reason_code="HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK",
                    reason=BilingualText(
                        en="Hostile context remains open by FOE classification.",
                        ru="Hostile-контекст остаётся открытым по классификации FOE.",
                    ),
                ),
                QikiTrustSignalV1(
                    label=BilingualText(en="Tactical state", ru="Тактическое состояние"),
                    state="healthy",
                    source="sensor",
                    confidence=1.0,
                    reason_code=reason_code,
                    reason=reason,
                ),
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="No new combat-entry pulse was emitted because the current intercept pulse is still active.",
                    ru="Новый combat-entry импульс не отправлялся, потому что текущий перехватный импульс ещё активен.",
                ),
                telemetry_confirmation=BilingualText(
                    en=(
                        "propulsion.rcs still reports an active intercept pulse; "
                        "ORION should reassess after it completes."
                    ),
                    ru=(
                        "propulsion.rcs всё ещё показывает активный перехватный импульс; "
                        "ORION должен переоценить ситуацию после его завершения."
                    ),
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    reason = BilingualText(
        en=(
            f"Target {target_designator or 'UNKNOWN'} is tracked as FOE, "
            "and no active station-influence block is present, "
            "so hostile context is open for a conditional combat entry."
        ),
        ru=(
            f"Цель {target_designator or 'UNKNOWN'} отслеживается как FOE, и активной station-блокировки нет, "
            "поэтому hostile-контекст открыт для условного входа в бой."
        ),
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Combat entry ready", ru="Вход в бой подготовлен"),
            body=BilingualText(
                en=(
                    "QIKI sees no active station protocol block and the target is now classified as FOE, "
                    "so a limited combat-entry RCS intercept burst can be prepared for explicit ORION confirmation."
                ),
                ru=(
                    "QIKI не видит активной station-протокольной блокировки, а цель теперь классифицирована как FOE, "
                    "поэтому можно подготовить ограниченный RCS-манёвр входа в бой под явное подтверждение ORION."
                ),
            ),
        ),
        legality=QikiLegalityV1(
            status="allowed",
            domain="protocol",
            reason_code="COMBAT_ENTRY_PROCEDURE_READY",
            reason=reason,
            allowed_when=BilingualText(
                en=(
                    "Confirm the prepared ORION procedure to execute one limited RCS intercept burst "
                    "toward the hostile contact."
                ),
                ru=(
                    "Подтвердите подготовленную процедуру ORION, чтобы выполнить один ограниченный "
                    "RCS-манёвр сближения с hostile-контактом."
                ),
            ),
        ),
        trust_signals=[
            QikiTrustSignalV1(
                label=BilingualText(en="Hostile target track", ru="Трек враждебной цели"),
                state="healthy",
                source="sensor",
                confidence=target_quality,
                reason_code="HOSTILE_TARGET_TRACKED",
                reason=BilingualText(
                    en=f"Target {target_designator or 'UNKNOWN'} is tracked with sufficient confidence.",
                    ru=f"Цель {target_designator or 'UNKNOWN'} отслеживается с достаточным уровнем доверия.",
                ),
            ),
            QikiTrustSignalV1(
                label=BilingualText(en="Hostile context", ru="Hostile-контекст"),
                state="healthy",
                source="derived",
                confidence=1.0,
                reason_code="HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK",
                reason=reason,
            ),
            QikiTrustSignalV1(
                label=BilingualText(en="Combat-entry path", ru="Контур входа в бой"),
                state="healthy",
                source="derived",
                confidence=1.0,
                reason_code="COMBAT_ENTRY_PROCEDURE_READY",
                reason=BilingualText(
                    en="The existing ORION procedure path can execute one limited RCS intercept burst.",
                    ru="Существующий ORION procedural-path может выполнить один ограниченный RCS-манёвр сближения.",
                ),
            ),
        ],
        consequence=QikiConsequenceV1(
            status="pending",
            summary=BilingualText(
                en="A limited combat-entry procedure is prepared and waiting for explicit operator confirmation.",
                ru="Ограниченная combat-entry процедура подготовлена и ждёт явного подтверждения оператора.",
            ),
            telemetry_confirmation=BilingualText(
                en="No RCS combat-entry command has been emitted yet; ORION must confirm the prepared procedure first.",
                ru=(
                    "RCS-команда входа в бой ещё не отправлялась; ORION должен сначала "
                    "подтвердить подготовленную процедуру."
                ),
            ),
        ),
        proposals=[
            QikiProposalV1(
                proposal_id=f"qiki-combat-entry-{req.request_id}",
                title=BilingualText(en="Run combat-entry burst", ru="Запустить манёвр входа в бой"),
                justification=reason,
                confidence=0.91,
                priority=92,
                suggested_questions=[],
                proposed_actions=[
                    QikiProposedActionV1(
                        kind="ORION_PROCEDURE",
                        subject="orionv.procedure",
                        name="hostile_rcs_intercept_burst",
                        parameters={},
                        dry_run=False,
                    )
                ],
            )
        ],
        warnings=[],
        error=None,
    )


def _build_attitude_stabilize_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    world_snapshot: dict[str, Any] | None,
    sensor_snapshot: dict[str, Any] | None = None,
) -> QikiChatResponseV1:
    sensor_source = _merge_sensor_source(world_snapshot, sensor_snapshot)
    sensor_plane = sensor_source.get("sensor_plane") if isinstance(sensor_source, dict) else None
    imu = sensor_plane.get("imu") if isinstance(sensor_plane, dict) else None
    attitude = sensor_source.get("attitude") if isinstance(sensor_source, dict) else None
    imu_freshness = _section_freshness(
        sensor_source if isinstance(sensor_source, dict) else None,
        section="sensor_plane",
        stale_after_s=_IMU_STALE_AFTER_S,
        expire_after_s=_IMU_EXPIRE_AFTER_S,
    )

    if not isinstance(imu, dict):
        reason = BilingualText(
            en="IMU telemetry is unavailable, so QIKI cannot assess attitude stabilization.",
            ru="Телеметрия IMU недоступна, поэтому QIKI не может оценить стабилизацию ориентации.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Attitude hold deferred", ru="Удержание ориентации отложено"),
                body=BilingualText(
                    en="QIKI cannot assess attitude hold because IMU telemetry is missing.",
                    ru="QIKI не может оценить удержание ориентации, потому что телеметрия IMU отсутствует.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="IMU_STATE_NO_DATA",
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry when IMU telemetry becomes available again.",
                    ru="Повторите попытку, когда телеметрия IMU снова станет доступной.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="IMU telemetry", ru="Телеметрия IMU"),
                    state="off",
                    source="sensor",
                    confidence=0.0,
                    reason_code="IMU_STATE_NO_DATA",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Attitude stabilization was not started.",
                    ru="Стабилизация ориентации не была начата.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No stabilization request or control-bus command was emitted.",
                    ru="Ни запрос на стабилизацию, ни команда на control bus не отправлялись.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    if imu_freshness["state"] == "stale":
        age_s = float(imu_freshness.get("age_s") or 0.0)
        reason = BilingualText(
            en=f"IMU telemetry is stale ({age_s:.1f}s old), so QIKI will not trust attitude stabilization yet.",
            ru=f"Телеметрия IMU устарела ({age_s:.1f} с), поэтому QIKI пока не будет доверять стабилизации ориентации.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Attitude hold deferred", ru="Удержание ориентации отложено"),
                body=BilingualText(
                    en="QIKI sees IMU data, but it is too old for a trustworthy attitude decision.",
                    ru="QIKI видит данные IMU, но они слишком старые для надёжного решения по ориентации.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="IMU_STATE_STALE",
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry after a fresh IMU update arrives.",
                    ru="Повторите попытку после прихода свежего обновления IMU.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="IMU telemetry freshness", ru="Свежесть телеметрии IMU"),
                    state="degraded",
                    source="sensor",
                    confidence=0.2,
                    reason_code="IMU_STATE_STALE",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Attitude stabilization was deferred until fresher IMU data arrives.",
                    ru="Стабилизация ориентации отложена до прихода более свежих данных IMU.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No stabilization request or control-bus command was emitted while IMU freshness was insufficient.",
                    ru="Пока свежесть IMU недостаточна, ни запрос на стабилизацию, ни команда на control bus не отправлялись.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    enabled = bool(imu.get("enabled"))
    status = str(imu.get("status") or "").strip().lower()
    reason_code = str(imu.get("reason") or "").strip().lower() or "unknown"
    ok_value = imu.get("ok")
    roll_rate = imu.get("roll_rate_rps")
    pitch_rate = imu.get("pitch_rate_rps")
    yaw_rate = imu.get("yaw_rate_rps")
    roll_rad = attitude.get("roll_rad") if isinstance(attitude, dict) else None
    pitch_rad = attitude.get("pitch_rad") if isinstance(attitude, dict) else None
    yaw_rad = attitude.get("yaw_rad") if isinstance(attitude, dict) else None

    if not enabled or status in {"na", "off"} or ok_value is None:
        reason = BilingualText(
            en="IMU is off or has no reading, so QIKI cannot confirm current attitude stability.",
            ru="IMU выключен или ещё не дал чтение, поэтому QIKI не может подтвердить устойчивость ориентации.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Attitude hold deferred", ru="Удержание ориентации отложено"),
                body=BilingualText(
                    en="QIKI cannot assess attitude hold because the IMU is currently off or unreadable.",
                    ru="QIKI не может оценить удержание ориентации, потому что IMU сейчас выключен или нечитаем.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="IMU_OFFLINE",
                reason=reason,
                allowed_when=BilingualText(
                    en="Wait for IMU telemetry to become available before retrying attitude hold.",
                    ru="Дождитесь появления телеметрии IMU перед повторной попыткой удержания ориентации.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="IMU telemetry", ru="Телеметрия IMU"),
                    state="off",
                    source="sensor",
                    confidence=0.0,
                    reason_code="IMU_OFFLINE",
                    reason=BilingualText(
                        en=f"IMU status={status or 'na'}, reason={reason_code}.",
                        ru=f"Статус IMU={status or 'na'}, причина={reason_code}.",
                    ),
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Attitude stabilization was not started.",
                    ru="Стабилизация ориентации не была начата.",
                ),
                telemetry_confirmation=BilingualText(
                    en="Attitude hold remains inactive while IMU telemetry is off.",
                    ru="Удержание ориентации не активировано, пока телеметрия IMU недоступна.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    if status in {"crit", "failed"} or ok_value is False:
        reason = BilingualText(
            en="IMU reports a failed state, so QIKI will not trust attitude stabilization commands.",
            ru="IMU сообщает о сбойном состоянии, поэтому QIKI не будет доверять командам стабилизации ориентации.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Attitude hold blocked", ru="Удержание ориентации заблокировано"),
                body=BilingualText(
                    en="QIKI blocks attitude hold because the IMU currently reports a failed state.",
                    ru="QIKI блокирует удержание ориентации, потому что IMU сейчас сообщает о сбое.",
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="trust",
                reason_code="IMU_FAILED",
                reason=reason,
                allowed_when=BilingualText(
                    en="Recover the IMU before requesting attitude stabilization again.",
                    ru="Восстановите IMU перед повторным запросом стабилизации ориентации.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="IMU telemetry", ru="Телеметрия IMU"),
                    state="failed",
                    source="sensor",
                    confidence=0.0,
                    reason_code="IMU_FAILED",
                    reason=BilingualText(
                        en=f"IMU status={status or 'crit'}, reason={reason_code}.",
                        ru=f"Статус IMU={status or 'crit'}, причина={reason_code}.",
                    ),
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Attitude stabilization was not started.",
                    ru="Стабилизация ориентации не была начата.",
                ),
                telemetry_confirmation=BilingualText(
                    en="IMU telemetry still reports a failed state; no action was emitted.",
                    ru="Телеметрия IMU всё ещё сообщает о сбое; действие не запускалось.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    rates = []
    for value in (roll_rate, pitch_rate, yaw_rate):
        if isinstance(value, (int, float)):
            rates.append(abs(float(value)))
    max_rate = max(rates) if rates else 0.0
    reason = BilingualText(
        en=(
            f"IMU is healthy and attitude telemetry is available: "
            f"roll={roll_rad if roll_rad is not None else 0.0:.3f}, "
            f"pitch={pitch_rad if pitch_rad is not None else 0.0:.3f}, "
            f"yaw={yaw_rad if yaw_rad is not None else 0.0:.3f} rad."
        ),
        ru=(
            f"IMU исправен и телеметрия ориентации доступна: "
            f"roll={roll_rad if roll_rad is not None else 0.0:.3f}, "
            f"pitch={pitch_rad if pitch_rad is not None else 0.0:.3f}, "
            f"yaw={yaw_rad if yaw_rad is not None else 0.0:.3f} рад."
        ),
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Attitude hold assessed", ru="Удержание ориентации оценено"),
            body=BilingualText(
                en="QIKI considers attitude telemetry trustworthy enough for a manual stabilization decision.",
                ru="QIKI считает телеметрию ориентации достаточно надёжной для ручного решения о стабилизации.",
            ),
        ),
        legality=QikiLegalityV1(
            status="allowed",
            domain="trust",
            reason_code="IMU_HEALTHY",
            reason=reason,
            allowed_when=BilingualText(
                en="Use an explicit operator-approved stabilization flow to proceed.",
                ru="Используйте отдельный подтверждаемый оператором контур стабилизации для продолжения.",
            ),
        ),
        trust_signals=[
            QikiTrustSignalV1(
                label=BilingualText(en="IMU telemetry", ru="Телеметрия IMU"),
                state="healthy",
                source="sensor",
                confidence=0.95,
                reason_code="IMU_HEALTHY",
                reason=reason,
            )
        ],
        consequence=QikiConsequenceV1(
            status="confirmed",
            summary=BilingualText(
                en="Attitude-hold readiness is confirmed by current IMU telemetry.",
                ru="Готовность удержания ориентации подтверждена текущей телеметрией IMU.",
            ),
            telemetry_confirmation=BilingualText(
                en=(
                    f"IMU is live and maximum angular rate is {max_rate:.3f} rad/s; "
                    "automatic stabilization remains disabled."
                ),
                ru=(
                    f"IMU активен, максимальная угловая скорость {max_rate:.3f} рад/с; "
                    "автоматическая стабилизация по-прежнему отключена."
                ),
            ),
        ),
        proposals=[],
        warnings=[],
        error=None,
    )


def _build_safe_observation_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    world_snapshot: dict[str, Any] | None,
    resumable_objective: dict[str, Any] | None = None,
) -> QikiChatResponseV1:
    sim_state = world_snapshot.get("sim_state") if isinstance(world_snapshot, dict) else None
    fsm_state = str(sim_state.get("fsm_state") or "").strip().upper() if isinstance(sim_state, dict) else ""
    paused = bool(sim_state.get("paused")) if isinstance(sim_state, dict) else False
    speed = float(sim_state.get("speed") or 1.0) if isinstance(sim_state, dict) else 1.0

    reason = BilingualText(
        en=(
            "QIKI can execute a safe observation procedure using the existing pause/start control path "
            "so the operator can inspect the situation without hidden world progress."
        ),
        ru=(
            "QIKI может выполнить процедуру безопасной стабилизации наблюдения через существующий "
            "контур pause/start, чтобы оператор анализировал ситуацию без скрытого движения мира."
        ),
    )
    allowed_when = BilingualText(
        en="Confirm the prepared ORION procedure to pause the simulation and then return it to running mode.",
        ru=(
            "Подтвердите подготовленную процедуру ORION, чтобы поставить симуляцию "
            "на паузу и затем вернуть её в режим выполнения."
        ),
    )
    confirmation = BilingualText(
        en=f"Current sim-state: {fsm_state or 'UNKNOWN'} at speed x{speed:.1f}.",
        ru=f"Текущее состояние симуляции: {fsm_state or 'UNKNOWN'} на скорости x{speed:.1f}.",
    )
    contour_snapshot = _resumable_contour_track_snapshot(resumable_objective)
    contour_track_id = str(contour_snapshot.get("observation_track_id") or "").strip()
    contour_track_label = str(contour_snapshot.get("observation_track_label") or "").strip()
    contour_public_track_id = str(contour_snapshot.get("public_track_id") or "").strip()
    allow_designator_fallback = not bool(contour_track_id) or bool(contour_public_track_id)
    selected_track, selection_source = _select_target_track_for_resume(
        world_snapshot,
        target_designator=_extract_target_designator(req.input.text),
        preferred_track_id=contour_track_id,
        preferred_public_track_id=contour_public_track_id,
        allow_designator_fallback=allow_designator_fallback,
    )
    resumed_track = selected_track
    previous_track_id = contour_track_id
    previous_track_label = contour_track_label
    refreshed_identity = _resume_track_identity(resumed_track)
    logger.info(
        "Resume track selection: objective_id=%s target=%s contour_track_id=%s contour_label=%s selected_track_id=%s refreshed_label=%s reason=%s fallback_allowed=%s",
        str(resumable_objective.get("objective_id") or "").strip() if isinstance(resumable_objective, dict) else "",
        _extract_target_designator(req.input.text),
        previous_track_id,
        previous_track_label,
        refreshed_identity["track_id"],
        refreshed_identity["track_label"],
        selection_source,
        allow_designator_fallback,
    )
    action = QikiProposedActionV1(
        kind="ORION_PROCEDURE",
        subject="orionv.procedure",
        name="safe_pause_resume",
        parameters=_observation_track_snapshot(resumed_track, fallback_snapshot=contour_snapshot),
        dry_run=False,
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Safe observation ready", ru="Безопасное наблюдение готово"),
            body=BilingualText(
                en=(
                    "QIKI prepared a short two-step observation procedure: pause the simulation, "
                    "inspect the situation, then resume normal execution."
                ),
                ru=(
                    "QIKI подготовила короткую двухшаговую процедуру наблюдения: поставить симуляцию "
                    "на паузу, проанализировать ситуацию, затем вернуть нормальное выполнение."
                ),
            ),
        ),
        legality=QikiLegalityV1(
            status="allowed",
            domain="resource",
            reason_code="SAFE_OBSERVATION_PROCEDURE_READY",
            reason=reason,
            allowed_when=allowed_when,
        ),
        trust_signals=[
            QikiTrustSignalV1(
                label=BilingualText(en="Simulation control state", ru="Состояние управления симуляцией"),
                state="healthy",
                source="derived",
                confidence=1.0,
                reason_code="SIM_CONTROL_READY" if not paused else "SIM_ALREADY_PAUSED",
                reason=BilingualText(
                    en=(
                        "The existing simulation control path is available for pause/start procedure execution."
                        if not paused
                        else "The simulation is already paused; QIKI can still complete the observation procedure."
                    ),
                    ru=(
                        "Существующий контур управления симуляцией доступен для исполнения pause/start процедуры."
                        if not paused
                        else "Симуляция уже стоит на паузе; QIKI всё равно может завершить процедуру наблюдения."
                    ),
                ),
            )
        ],
        consequence=QikiConsequenceV1(
            status="pending",
            summary=BilingualText(
                en="The safe observation procedure is prepared and waiting for explicit operator confirmation.",
                ru="Процедура безопасной стабилизации наблюдения подготовлена и ждёт явного подтверждения оператора.",
            ),
            telemetry_confirmation=confirmation,
        ),
        proposals=[
            QikiProposalV1(
                proposal_id=f"qiki-safe-observation-{req.request_id}",
                title=BilingualText(en="Run safe observation", ru="Запустить безопасное наблюдение"),
                justification=reason,
                confidence=1.0,
                priority=85,
                suggested_questions=[],
                proposed_actions=[action],
            )
        ],
        warnings=[],
        error=None,
    )


def _build_slow_observation_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    world_snapshot: dict[str, Any] | None,
) -> QikiChatResponseV1:
    sim_state = world_snapshot.get("sim_state") if isinstance(world_snapshot, dict) else None
    fsm_state = str(sim_state.get("fsm_state") or "").strip().upper() if isinstance(sim_state, dict) else ""
    paused = bool(sim_state.get("paused")) if isinstance(sim_state, dict) else False
    speed = float(sim_state.get("speed") or 1.0) if isinstance(sim_state, dict) else 1.0

    reason = BilingualText(
        en=(
            "QIKI can prepare a cautious observation procedure: pause the simulation and then resume it at quarter "
            "speed so the operator can inspect the situation with lower workload."
        ),
        ru=(
            "QIKI может подготовить осторожную процедуру наблюдения: поставить симуляцию на паузу и затем "
            "вернуть её на четверть скорости, чтобы оператор анализировал ситуацию с меньшей нагрузкой."
        ),
    )
    allowed_when = BilingualText(
        en="Confirm the prepared ORION procedure to pause the simulation and resume it at x0.25.",
        ru=(
            "Подтвердите подготовленную процедуру ORION, чтобы поставить симуляцию "
            "на паузу и вернуть её на скорости x0.25."
        ),
    )
    confirmation = BilingualText(
        en=f"Current sim-state: {fsm_state or 'UNKNOWN'} at speed x{speed:.2f}.",
        ru=f"Текущее состояние симуляции: {fsm_state or 'UNKNOWN'} на скорости x{speed:.2f}.",
    )
    action = QikiProposedActionV1(
        kind="ORION_PROCEDURE",
        subject="orionv.procedure",
        name="safe_pause_slow_resume",
        parameters={},
        dry_run=False,
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Slow observation ready", ru="Медленное наблюдение готово"),
            body=BilingualText(
                en=(
                    "QIKI prepared a cautious two-step observation procedure: pause the simulation, then resume it "
                    "at x0.25 for lower-workload observation."
                ),
                ru=(
                    "QIKI подготовила осторожную двухшаговую процедуру наблюдения: поставить симуляцию на паузу, "
                    "затем вернуть её на скорости x0.25 для наблюдения с меньшей нагрузкой."
                ),
            ),
        ),
        legality=QikiLegalityV1(
            status="allowed",
            domain="resource",
            reason_code="SLOW_OBSERVATION_PROCEDURE_READY",
            reason=reason,
            allowed_when=allowed_when,
        ),
        trust_signals=[
            QikiTrustSignalV1(
                label=BilingualText(en="Simulation control state", ru="Состояние управления симуляцией"),
                state="healthy",
                source="derived",
                confidence=1.0,
                reason_code="SIM_CONTROL_READY" if not paused else "SIM_ALREADY_PAUSED",
                reason=BilingualText(
                    en=(
                        "The existing simulation control path supports reduced-speed restart for careful observation."
                        if not paused
                        else "The simulation is already paused; QIKI can still resume it at reduced speed."
                    ),
                    ru=(
                        "Существующий контур управления симуляцией поддерживает "
                        "пониженную скорость перезапуска для осторожного наблюдения."
                        if not paused
                        else "Симуляция уже стоит на паузе; QIKI всё равно может вернуть её на пониженной скорости."
                    ),
                ),
            )
        ],
        consequence=QikiConsequenceV1(
            status="pending",
            summary=BilingualText(
                en="The slow-observation procedure is prepared and waiting for explicit operator confirmation.",
                ru="Процедура медленного наблюдения подготовлена и ждёт явного подтверждения оператора.",
            ),
            telemetry_confirmation=confirmation,
        ),
        proposals=[
            QikiProposalV1(
                proposal_id=f"qiki-slow-observation-{req.request_id}",
                title=BilingualText(en="Run slow observation", ru="Запустить медленное наблюдение"),
                justification=reason,
                confidence=1.0,
                priority=82,
                suggested_questions=[],
                proposed_actions=[action],
            )
        ],
        warnings=[],
        error=None,
    )


def _build_docking_corridor_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    world_snapshot: dict[str, Any] | None,
) -> QikiChatResponseV1:
    track = _best_station_track(world_snapshot)
    threshold_m = float(os.getenv("QIKI_DOCKING_TARGET_RANGE_M", "5000.0"))

    if track is None:
        reason = BilingualText(
            en="No trusted station track is available for docking-corridor assessment.",
            ru="Для оценки коридора стыковки нет доверенного трека станции.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Corridor deferred", ru="Коридор отложен"),
                body=BilingualText(
                    en="QIKI cannot assess docking-corridor entry because station tracking data is unavailable.",
                    ru="QIKI не может оценить вход в коридор стыковки, потому что данные трекинга станции недоступны.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="STATION_TRACK_NO_DATA",
                reason=reason,
                allowed_when=BilingualText(
                    en="Wait until a trusted station track becomes available.",
                    ru="Дождитесь появления доверенного трека станции.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="off",
                    source="sensor",
                    confidence=0.0,
                    reason_code="STATION_TRACK_NO_DATA",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Docking-corridor entry was not started.",
                    ru="Вход в коридор стыковки не был начат.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No new guidance or control-bus command was emitted.",
                    ru="Ни новая навигационная команда, ни команда на control bus не отправлялись.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    range_m = float(track.get("range_m", 0.0) or 0.0)
    quality = max(0.0, min(1.0, float(track.get("quality", 0.0) or 0.0)))

    if range_m > threshold_m:
        reason = BilingualText(
            en=f"Station range {range_m:.0f} m exceeds the docking-corridor threshold {threshold_m:.0f} m.",
            ru=f"Дальность до станции {range_m:.0f} м превышает порог коридора стыковки {threshold_m:.0f} м.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Corridor blocked", ru="Коридор заблокирован"),
                body=BilingualText(
                    en=(
                        "QIKI will not clear docking-corridor entry "
                        "because the craft is still outside the allowed zone."
                    ),
                    ru=(
                        "QIKI не разрешит вход в коридор стыковки, "
                        "потому что аппарат всё ещё вне допустимой зоны."
                    ),
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="zone",
                reason_code="DOCKING_ZONE_TOO_FAR",
                reason=reason,
                allowed_when=BilingualText(
                    en="Reduce the station range below the docking-corridor threshold before retrying.",
                    ru="Сократите дальность до станции ниже порога коридора стыковки и повторите попытку.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="healthy",
                    source="sensor",
                    confidence=quality,
                    reason_code="DOCKING_ZONE_TOO_FAR",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Docking-corridor entry was not started.",
                    ru="Вход в коридор стыковки не был начат.",
                ),
                telemetry_confirmation=BilingualText(
                    en="Radar telemetry still shows the craft outside the docking corridor.",
                    ru="Радарная телеметрия всё ещё показывает аппарат вне коридора стыковки.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    reason = BilingualText(
        en=f"Station range {range_m:.0f} m is inside the docking-corridor threshold {threshold_m:.0f} m.",
        ru=f"Дальность до станции {range_m:.0f} м находится внутри порога коридора стыковки {threshold_m:.0f} м.",
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Corridor ready", ru="Коридор готов"),
            body=BilingualText(
                en="QIKI considers the craft inside the docking corridor for a manual docking sequence.",
                ru="QIKI считает аппарат находящимся внутри коридора стыковки для ручной последовательности стыковки.",
            ),
        ),
        legality=QikiLegalityV1(
            status="allowed",
            domain="zone",
            reason_code="DOCKING_ZONE_READY",
            reason=reason,
            allowed_when=BilingualText(
                en="Use an explicit operator-approved docking flow to proceed further.",
                ru="Используйте отдельный подтверждаемый оператором контур стыковки для дальнейшего продолжения.",
            ),
        ),
        trust_signals=[
            QikiTrustSignalV1(
                label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                state="healthy",
                source="sensor",
                confidence=quality,
                reason_code="DOCKING_ZONE_READY",
                reason=reason,
            )
        ],
        consequence=QikiConsequenceV1(
            status="confirmed",
            summary=BilingualText(
                en="Docking-corridor readiness is confirmed by current radar telemetry.",
                ru="Готовность коридора стыковки подтверждена текущей радарной телеметрией.",
            ),
            telemetry_confirmation=BilingualText(
                en=(
                    f"Station track range is {range_m:.0f} m and remains inside the docking-corridor threshold "
                    f"{threshold_m:.0f} m; automatic docking remains disabled."
                ),
                ru=(
                    f"Дальность до станции {range_m:.0f} м и остаётся внутри порога коридора стыковки "
                    f"{threshold_m:.0f} м; автоматическая стыковка по-прежнему отключена."
                ),
            ),
        ),
        proposals=[],
        warnings=[],
        error=None,
    )


def _build_station_hail_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    world_snapshot: dict[str, Any] | None,
) -> QikiChatResponseV1:
    track = _best_station_track(world_snapshot)
    comms = world_snapshot.get("comms") if isinstance(world_snapshot, dict) else None

    if track is None:
        reason = BilingualText(
            en="No trusted station track is available for a channel request.",
            ru="Для запроса канала нет доверенного трека станции.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Channel request deferred", ru="Запрос канала отложен"),
                body=BilingualText(
                    en="QIKI cannot request a station channel because the target is not tracked reliably yet.",
                    ru="QIKI не может запросить канал со станцией, потому что цель пока не трекается надёжно.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="STATION_TRACK_NO_DATA",
                reason=reason,
                allowed_when=BilingualText(
                    en="Wait until a station track appears with sufficient freshness and quality.",
                    ru="Дождитесь появления трека станции с достаточной свежестью и качеством.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="off",
                    source="sensor",
                    confidence=0.0,
                    reason_code="STATION_TRACK_NO_DATA",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The station hail was not started.",
                    ru="Вызов станции не был начат.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No comms request or control-bus command was emitted.",
                    ru="Ни запрос в канал связи, ни команда на control bus не отправлялись.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    if not isinstance(comms, dict):
        reason = BilingualText(
            en="Comms telemetry is missing, so QIKI cannot assess channel availability.",
            ru="Телеметрия связи отсутствует, поэтому QIKI не может оценить доступность канала.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Channel request deferred", ru="Запрос канала отложен"),
                body=BilingualText(
                    en="QIKI cannot clear the channel request because comms telemetry is unavailable.",
                    ru="QIKI не может разрешить запрос канала, потому что телеметрия связи недоступна.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="COMMS_STATE_NO_DATA",
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry when comms telemetry becomes available again.",
                    ru="Повторите попытку, когда телеметрия связи снова станет доступной.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Comms link state", ru="Состояние канала связи"),
                    state="off",
                    source="derived",
                    confidence=0.0,
                    reason_code="COMMS_STATE_NO_DATA",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The station hail was not started.",
                    ru="Вызов станции не был начат.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No communication request was emitted while comms telemetry was unavailable.",
                    ru="Пока телеметрия связи недоступна, запрос в канал не отправлялся.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    comms_available = comms.get("available")
    comms_blocking_reasons = _string_codes(comms.get("reason_codes"))

    if comms_available is None or str(comms_available).lower() == "unknown":
        reason = BilingualText(
            en=_comms_reason_text(comms, "Comms availability is unknown, so QIKI cannot assess channel readiness."),
            ru="Доступность связи неизвестна, поэтому QIKI не может оценить готовность канала.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Channel deferred", ru="Канал отложен"),
                body=BilingualText(
                    en="QIKI sees the station, but comms availability is not known.",
                    ru="QIKI видит станцию, но доступность связи неизвестна.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code=_primary_comms_reason(comms, "COMMS_STATE_UNKNOWN"),
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry when comms availability has an explicit source state.",
                    ru="Повторите попытку, когда у доступности связи появится явное состояние источника.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Comms availability", ru="Доступность связи"),
                    state="degraded",
                    source="derived",
                    confidence=0.2,
                    reason_code=_primary_comms_reason(comms, "COMMS_STATE_UNKNOWN"),
                    reason=reason,
                ),
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="healthy",
                    source="sensor",
                    confidence=max(0.0, min(1.0, float(track.get("quality", 0.0) or 0.0))),
                    reason_code="STATION_TRACK_TRUSTED",
                    reason=BilingualText(
                        en="Station track is available while comms availability remains unknown.",
                        ru="Трек станции доступен, пока доступность связи остаётся неизвестной.",
                    ),
                ),
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The station hail was deferred until comms availability is known.",
                    ru="Вызов станции отложен до выяснения доступности связи.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No communication request was emitted while comms availability was unknown.",
                    ru="Пока доступность связи неизвестна, запрос в канал не отправлялся.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    if comms_available is False or comms_blocking_reasons:
        reason_code = _primary_comms_reason(comms, "COMMS_UNAVAILABLE")
        reason = BilingualText(
            en=_comms_reason_text(comms, "Comms are unavailable, so a station hail cannot be routed."),
            ru="Связь недоступна, поэтому вызов станции не может быть маршрутизирован.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Channel deferred", ru="Канал отложен"),
                body=BilingualText(
                    en="QIKI sees the station, but current comms availability blocks the hail.",
                    ru="QIKI видит станцию, но текущая доступность связи блокирует вызов.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="resource",
                reason_code=reason_code,
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry when comms availability is true.",
                    ru="Повторите попытку, когда доступность связи станет true.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Comms availability", ru="Доступность связи"),
                    state="degraded",
                    source="derived",
                    confidence=0.25,
                    reason_code=reason_code,
                    reason=reason,
                ),
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="healthy",
                    source="sensor",
                    confidence=max(0.0, min(1.0, float(track.get("quality", 0.0) or 0.0))),
                    reason_code="STATION_TRACK_TRUSTED",
                    reason=BilingualText(
                        en="Station track is available while comms are blocked.",
                        ru="Трек станции доступен, пока связь заблокирована.",
                    ),
                ),
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The station hail was not started.",
                    ru="Вызов станции не был начат.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No communication request was emitted while comms were unavailable.",
                    ru="Пока связь недоступна, запрос в канал не отправлялся.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    plane_enabled = bool(comms.get("plane_enabled", comms.get("enabled", False)))
    link_state = str(comms.get("link_state") or comms.get("link") or "").strip().lower()
    data_rate_kbps = float(comms.get("data_rate_kbps", 0.0) or 0.0)
    latency_ms = comms.get("latency_ms")
    antenna_status = str(comms.get("antenna_status") or "").strip().lower()
    quality = max(0.0, min(1.0, float(track.get("quality", 0.0) or 0.0)))
    range_m = float(track.get("range_m", 0.0) or 0.0)

    if not plane_enabled:
        reason = BilingualText(
            en="The communications plane is disabled in the active hardware profile.",
            ru="Контур связи отключён в активном аппаратном профиле.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Channel blocked", ru="Канал заблокирован"),
                body=BilingualText(
                    en="QIKI will not request a station channel because communications support is disabled.",
                    ru="QIKI не будет запрашивать канал со станцией, потому что поддержка связи отключена.",
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="resource",
                reason_code="COMMS_PLANE_DISABLED",
                reason=reason,
                allowed_when=BilingualText(
                    en="Enable the communications subsystem before requesting station contact.",
                    ru="Включите подсистему связи перед запросом контакта со станцией.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Comms link state", ru="Состояние канала связи"),
                    state="off",
                    source="derived",
                    confidence=1.0,
                    reason_code="COMMS_PLANE_DISABLED",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The station hail was not started.",
                    ru="Вызов станции не был начат.",
                ),
                telemetry_confirmation=BilingualText(
                    en="The comms subsystem remained disabled; no request was emitted.",
                    ru="Подсистема связи оставалась отключённой; запрос не отправлялся.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    if link_state == "offline":
        reason = BilingualText(
            en="The communications link is offline, so a station hail cannot be routed.",
            ru="Канал связи находится offline, поэтому вызов станции не может быть маршрутизирован.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Channel blocked", ru="Канал заблокирован"),
                body=BilingualText(
                    en="QIKI cannot request station contact because the communications link is offline.",
                    ru="QIKI не может запросить связь со станцией, потому что канал связи находится offline.",
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="resource",
                reason_code="COMMS_LINK_OFFLINE",
                reason=reason,
                allowed_when=BilingualText(
                    en="Restore an online comms link before requesting station contact.",
                    ru="Восстановите online-канал связи перед запросом контакта со станцией.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Comms link state", ru="Состояние канала связи"),
                    state="off",
                    source="derived",
                    confidence=1.0,
                    reason_code="COMMS_LINK_OFFLINE",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The station hail was not started.",
                    ru="Вызов станции не был начат.",
                ),
                telemetry_confirmation=BilingualText(
                    en="Comms telemetry still reports an offline link; nothing was sent.",
                    ru="Телеметрия связи всё ещё показывает offline-канал; ничего не отправлялось.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    if link_state != "online":
        latency_text = f"{float(latency_ms):.0f} ms" if isinstance(latency_ms, (int, float)) else "n/a"
        reason = BilingualText(
            en=(
                f"Comms link remains degraded: state={link_state or 'unknown'}, "
                f"latency={latency_text}, antenna={antenna_status or 'unlock'}."
            ),
            ru=(
                f"Канал связи остаётся деградированным: state={link_state or 'unknown'}, "
                f"latency={latency_text}, antenna={antenna_status or 'unlock'}."
            ),
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Channel deferred", ru="Канал отложен"),
                body=BilingualText(
                    en="QIKI sees the station, but the communications link is too degraded for a reliable hail.",
                    ru="QIKI видит станцию, но канал связи слишком деградирован для надёжного вызова.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="resource",
                reason_code="COMMS_LINK_DEGRADED",
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry when the comms link returns to an online state.",
                    ru="Повторите попытку, когда канал связи вернётся в состояние online.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Comms link state", ru="Состояние канала связи"),
                    state="degraded",
                    source="derived",
                    confidence=0.45,
                    reason_code="COMMS_LINK_DEGRADED",
                    reason=reason,
                ),
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="healthy",
                    source="sensor",
                    confidence=quality,
                    reason_code="STATION_TRACK_TRUSTED",
                    reason=BilingualText(
                        en=f"Station track is available at range {range_m:.0f} m.",
                        ru=f"Трек станции доступен на дальности {range_m:.0f} м.",
                    ),
                ),
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The station hail was deferred until the comms link stabilizes.",
                    ru="Вызов станции отложен до стабилизации канала связи.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No communication request was emitted while the link remained degraded.",
                    ru="Пока канал оставался деградированным, запрос в связь не отправлялся.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    reason = BilingualText(
        en=(
            f"Station link is online: range {range_m:.0f} m, data rate {data_rate_kbps:.0f} kbps, "
            f"antenna={antenna_status or 'lock'}."
        ),
        ru=(
            f"Канал до станции в состоянии online: дальность {range_m:.0f} м, "
            f"скорость {data_rate_kbps:.0f} кбит/с, antenna={antenna_status or 'lock'}."
        ),
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Channel ready", ru="Канал готов"),
            body=BilingualText(
                en="QIKI considers the station link ready for a manual hail request.",
                ru="QIKI считает канал со станцией готовым для ручного вызова.",
            ),
        ),
        legality=QikiLegalityV1(
            status="allowed",
            domain="resource",
            reason_code="COMMS_CHANNEL_READY",
            reason=reason,
            allowed_when=BilingualText(
                en="Use an explicit operator-approved communications flow to send the hail.",
                ru="Используйте отдельный подтверждаемый оператором контур связи, чтобы отправить вызов.",
            ),
        ),
        trust_signals=[
            QikiTrustSignalV1(
                label=BilingualText(en="Comms link state", ru="Состояние канала связи"),
                state="healthy",
                source="derived",
                confidence=0.95,
                reason_code="COMMS_CHANNEL_READY",
                reason=reason,
            ),
            QikiTrustSignalV1(
                label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                state="healthy",
                source="sensor",
                confidence=quality,
                reason_code="STATION_TRACK_TRUSTED",
                reason=BilingualText(
                    en=f"Station track is available at range {range_m:.0f} m.",
                    ru=f"Трек станции доступен на дальности {range_m:.0f} м.",
                ),
            ),
        ],
        consequence=QikiConsequenceV1(
            status="confirmed",
            summary=BilingualText(
                en="The station link assessment is confirmed by current comms and radar telemetry.",
                ru="Оценка канала до станции подтверждена текущей телеметрией связи и радара.",
            ),
            telemetry_confirmation=BilingualText(
                en=(
                    f"Comms link is online with {data_rate_kbps:.0f} kbps and station track range "
                    f"{range_m:.0f} m; automatic transmission remains disabled."
                ),
                ru=(
                    f"Канал связи online со скоростью {data_rate_kbps:.0f} кбит/с и дальностью "
                    f"до станции {range_m:.0f} м; автоматическая передача по-прежнему отключена."
                ),
            ),
        ),
        proposals=[],
        warnings=[],
        error=None,
    )


def _build_station_approach_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    world_snapshot: dict[str, Any] | None,
) -> QikiChatResponseV1:
    min_quality = float(os.getenv("QIKI_SENSOR_MIN_QUALITY", "0.5"))
    max_age_s = float(os.getenv("QIKI_SENSOR_MAX_AGE_S", "2.0"))
    track = _best_station_track(world_snapshot)

    if track is None:
        reason = BilingualText(
            en="No trusted station radar track is available yet.",
            ru="Пока нет доверенного радарного трека станции.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Approach deferred", ru="Сближение отложено"),
                body=BilingualText(
                    en="QIKI cannot clear the approach because station tracking data is missing.",
                    ru="QIKI не может разрешить сближение, потому что данные трекинга станции отсутствуют.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="STATION_TRACK_NO_DATA",
                reason=reason,
                allowed_when=BilingualText(
                    en="Wait until a station track appears with sufficient freshness and quality.",
                    ru="Дождитесь появления трека станции с достаточной свежестью и качеством.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="off",
                    source="sensor",
                    confidence=0.0,
                    reason_code="STATION_TRACK_NO_DATA",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Approach execution was not started.",
                    ru="Исполнение сближения не было начато.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No new guidance or control-bus command was emitted.",
                    ru="Ни новая навигационная команда, ни команда на control bus не отправлялись.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    quality = float(track.get("quality", 0.0) or 0.0)
    age_s = float(track.get("age_s", 0.0) or 0.0)
    range_m = float(track.get("range_m", 0.0) or 0.0)
    if age_s > max_age_s:
        reason = BilingualText(
            en=f"Station track is stale: age {age_s:.2f}s exceeds {max_age_s:.2f}s.",
            ru=f"Трек станции устарел: возраст {age_s:.2f} с превышает {max_age_s:.2f} с.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Approach deferred", ru="Сближение отложено"),
                body=BilingualText(
                    en="QIKI sees the target, but the station track is too old for a safe approach decision.",
                    ru="QIKI видит цель, но трек станции слишком стар для безопасного решения о сближении.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="STATION_TRACK_STALE",
                reason=reason,
                allowed_when=BilingualText(
                    en="Wait for a fresher station track before retrying the approach.",
                    ru="Дождитесь более свежего трека станции перед повторной попыткой сближения.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="degraded",
                    source="sensor",
                    confidence=max(0.0, min(1.0, quality)),
                    reason_code="STATION_TRACK_STALE",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Approach execution was deferred until fresher data arrives.",
                    ru="Исполнение сближения отложено до поступления более свежих данных.",
                ),
                telemetry_confirmation=BilingualText(
                    en="Guidance state remains unchanged while tracking is stale.",
                    ru="Навигационное состояние не изменялось, пока трекинг оставался устаревшим.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    if quality < min_quality:
        reason = BilingualText(
            en=f"Station track quality {quality:.2f} is below the minimum {min_quality:.2f}.",
            ru=f"Качество трека станции {quality:.2f} ниже допустимого минимума {min_quality:.2f}.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Approach deferred", ru="Сближение отложено"),
                body=BilingualText(
                    en="QIKI cannot trust the current station track enough to clear the approach.",
                    ru="QIKI не может достаточно доверять текущему треку станции, чтобы разрешить сближение.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="STATION_TRACK_LOW_QUALITY",
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry when station tracking quality recovers above the configured threshold.",
                    ru="Повторите попытку, когда качество трекинга станции восстановится выше заданного порога.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                    state="degraded",
                    source="sensor",
                    confidence=max(0.0, min(1.0, quality)),
                    reason_code="STATION_TRACK_LOW_QUALITY",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="Approach execution was not started because target confidence is too low.",
                    ru="Исполнение сближения не начато, потому что доверие к цели слишком низкое.",
                ),
                telemetry_confirmation=BilingualText(
                    en="No new guidance or control-bus command was emitted.",
                    ru="Ни новая навигационная команда, ни команда на control bus не отправлялись.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    trusted_reason = BilingualText(
        en=f"Station track is fresh and usable: range {range_m:.0f} m, quality {quality:.2f}.",
        ru=f"Трек станции свежий и пригодный: дальность {range_m:.0f} м, качество {quality:.2f}.",
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Approach assessed", ru="Сближение оценено"),
            body=BilingualText(
                en="QIKI considers the station track trustworthy enough for a manual approach decision.",
                ru="QIKI считает трек станции достаточно надёжным для ручного решения о сближении.",
            ),
        ),
        legality=QikiLegalityV1(
            status="allowed",
            domain="trust",
            reason_code="STATION_TRACK_TRUSTED",
            reason=trusted_reason,
            allowed_when=BilingualText(
                en="Use explicit operator-approved execution flow to start the approach.",
                ru="Используйте отдельный подтверждаемый оператором контур исполнения, чтобы начать сближение.",
            ),
        ),
        trust_signals=[
            QikiTrustSignalV1(
                label=BilingualText(en="Station radar track", ru="Радарный трек станции"),
                state="healthy",
                source="sensor",
                confidence=max(0.0, min(1.0, quality)),
                reason_code="STATION_TRACK_TRUSTED",
                reason=trusted_reason,
            )
        ],
        consequence=QikiConsequenceV1(
            status="confirmed",
            summary=BilingualText(
                en="The station approach assessment is confirmed by current radar telemetry.",
                ru="Оценка сближения со станцией подтверждена текущей радарной телеметрией.",
            ),
            telemetry_confirmation=BilingualText(
                en=(
                    f"Station track is live: range {range_m:.0f} m, quality {quality:.2f}; "
                    "automatic execution remains disabled."
                ),
                ru=(
                    f"Трек станции активен: дальность {range_m:.0f} м, качество {quality:.2f}; "
                    "автоматическое исполнение по-прежнему отключено."
                ),
            ),
        ),
        proposals=[],
        warnings=[],
        error=None,
    )


def _build_release_dock_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    world_snapshot: dict[str, Any] | None,
) -> QikiChatResponseV1:
    docking = world_snapshot.get("docking") if isinstance(world_snapshot, dict) else None
    if not isinstance(docking, dict):
        reason = BilingualText(
            en="Docking state is unavailable in the current world snapshot.",
            ru="Состояние стыковки недоступно в текущем снимке мира.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Release deferred", ru="Отстыковка отложена"),
                body=BilingualText(
                    en="QIKI cannot authorize undocking because docking telemetry is missing.",
                    ru="QIKI не может разрешить отстыковку, потому что отсутствует телеметрия стыковки.",
                ),
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code="DOCKING_STATE_NO_DATA",
                reason=reason,
                allowed_when=BilingualText(
                    en="Retry when docking telemetry becomes available again.",
                    ru="Повторите попытку, когда телеметрия стыковки снова станет доступной.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Docking telemetry", ru="Телеметрия стыковки"),
                    state="off",
                    source="sensor",
                    confidence=0.0,
                    reason_code="DOCKING_STATE_NO_DATA",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The undock command was not sent.",
                    ru="Команда отстыковки не была отправлена.",
                ),
                telemetry_confirmation=BilingualText(
                    en="QIKI is waiting for a valid docking state before any operator-confirmed execution.",
                    ru="QIKI ждёт валидного состояния стыковки перед любым операторски подтверждаемым исполнением.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    connected = bool(docking.get("connected"))
    state = str(docking.get("state") or "").strip().lower()
    port = str(docking.get("port") or "").strip() or "?"
    enabled = bool(docking.get("enabled", True))

    if not enabled:
        reason = BilingualText(
            en="Docking is disabled by the current hardware profile.",
            ru="Стыковка отключена текущим аппаратным профилем.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Release blocked", ru="Отстыковка заблокирована"),
                body=BilingualText(
                    en="QIKI cannot release the dock because docking support is disabled.",
                    ru="QIKI не может выполнить отстыковку, потому что контур стыковки отключён.",
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="protocol",
                reason_code="DOCKING_DISABLED",
                reason=reason,
                allowed_when=BilingualText(
                    en="Enable the docking subsystem in the active hardware profile.",
                    ru="Включите подсистему стыковки в активном аппаратном профиле.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Docking telemetry", ru="Телеметрия стыковки"),
                    state="healthy",
                    source="sensor",
                    confidence=1.0,
                    reason_code="DOCKING_DISABLED",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The undock command was not sent.",
                    ru="Команда отстыковки не была отправлена.",
                ),
                telemetry_confirmation=BilingualText(
                    en="Docking remains disabled; no execution path was opened.",
                    ru="Стыковка остаётся отключённой; контур исполнения не открывался.",
                ),
            ),
            proposals=[],
            warnings=[reason],
            error=None,
        )

    if not connected or state == "undocked":
        reason = BilingualText(
            en="The craft is already undocked.",
            ru="Аппарат уже находится в состоянии отстыковки.",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Release blocked", ru="Отстыковка заблокирована"),
                body=BilingualText(
                    en="QIKI will not issue an undock command because the craft is not docked right now.",
                    ru="QIKI не будет выдавать команду отстыковки, потому что аппарат сейчас не пристыкован.",
                ),
            ),
            legality=QikiLegalityV1(
                status="blocked",
                domain="physics",
                reason_code="DOCK_ALREADY_RELEASED",
                reason=reason,
                allowed_when=BilingualText(
                    en="Dock the craft first, then retry the release command.",
                    ru="Сначала пристыкуйте аппарат, затем повторите команду отстыковки.",
                ),
            ),
            trust_signals=[
                QikiTrustSignalV1(
                    label=BilingualText(en="Docking telemetry", ru="Телеметрия стыковки"),
                    state="healthy",
                    source="sensor",
                    confidence=1.0,
                    reason_code="DOCK_ALREADY_RELEASED",
                    reason=reason,
                )
            ],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="The undock command was not sent.",
                    ru="Команда отстыковки не была отправлена.",
                ),
                telemetry_confirmation=BilingualText(
                    en="Telemetry already shows an undocked state.",
                    ru="Телеметрия уже показывает состояние отстыковки.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        )

    reason = BilingualText(
        en=f"Docking telemetry confirms an attached state on port {port}.",
        ru=f"Телеметрия стыковки подтверждает пристыкованное состояние на порту {port}.",
    )
    action = QikiProposedActionV1(
        subject=COMMANDS_CONTROL,
        name="sim.dock.release",
        parameters={},
        dry_run=False,
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Release ready", ru="Отстыковка готова"),
            body=BilingualText(
                en="QIKI can prepare a real undock command, but ORION must confirm it explicitly.",
                ru="QIKI может подготовить реальную команду отстыковки, но ORION должен подтвердить её отдельно.",
            ),
        ),
        legality=QikiLegalityV1(
            status="allowed",
            domain="physics",
            reason_code="DOCK_RELEASE_READY",
            reason=reason,
            allowed_when=BilingualText(
                en="Use the explicit ORION confirmation step to send the undock command.",
                ru="Используйте явный шаг подтверждения в ORION, чтобы отправить команду отстыковки.",
            ),
        ),
        trust_signals=[
            QikiTrustSignalV1(
                label=BilingualText(en="Docking telemetry", ru="Телеметрия стыковки"),
                state="healthy",
                source="sensor",
                confidence=1.0,
                reason_code="DOCK_RELEASE_READY",
                reason=reason,
            )
        ],
        consequence=QikiConsequenceV1(
            status="pending",
            summary=BilingualText(
                en="The undock command is prepared and waiting for explicit operator confirmation.",
                ru="Команда отстыковки подготовлена и ждёт явного подтверждения оператора.",
            ),
            telemetry_confirmation=BilingualText(
                en="No control-bus command has been sent yet; the craft remains docked until ORION confirms execution.",
                ru=(
                    "Команда на control bus ещё не отправлялась; аппарат остаётся "
                    "пристыкованным, пока ORION не подтвердит исполнение."
                ),
            ),
        ),
        proposals=[
            QikiProposalV1(
                proposal_id=f"qiki-release-dock-{req.request_id}",
                title=BilingualText(en="Confirm undock", ru="Подтвердить отстыковку"),
                justification=BilingualText(
                    en="Telemetry confirms a docked state and a valid release path.",
                    ru="Телеметрия подтверждает пристыкованное состояние и валидный путь отстыковки.",
                ),
                confidence=1.0,
                priority=90,
                suggested_questions=[],
                proposed_actions=[action],
            )
        ],
        warnings=[],
        error=None,
    )


def _build_cargo_list_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    catalog: CatalogResult | None = None,
) -> QikiChatResponseV1:
    """P1 (ADR-0019): доклад по грузовому отсеку из каталога, per-request.

    Fail-closed: каталог не читается -> честный отказ с кодом, никаких выдумок.
    Список — информация, не команда: без proposals/actions.
    """
    result = catalog if catalog is not None else load_module_catalog(known_classes=KNOWN_MOUNT_CLASSES)
    if not result.ok:
        reason = BilingualText(
            en=f"Cargo manifest is unavailable [{result.error_code}].",
            ru=f"Манифест отсека недоступен [{result.error_code}].",
        )
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Cargo bay unavailable", ru="Отсек недоступен"),
                body=reason,
            ),
            legality=QikiLegalityV1(
                status="deferred",
                domain="trust",
                reason_code=result.error_code or "CATALOG_UNAVAILABLE",
                reason=reason,
            ),
            trust_signals=[],
            consequence=QikiConsequenceV1(
                status="not_sent",
                summary=BilingualText(
                    en="No catalog data; nothing was invented.",
                    ru="Данных каталога нет; ничего не выдумано.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        )

    lines_ru = [
        f"{entry.display_name_ru} | {entry.module_id} | класс {entry.module_class} | остаток {entry.quantity}"
        for entry in result.entries
    ]
    lines_en = [
        f"{entry.module_id} | class {entry.module_class} | qty {entry.quantity}"
        for entry in result.entries
    ]
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Cargo bay report", ru="Доклад по грузовому отсеку"),
            body=BilingualText(en="\n".join(lines_en), ru="\n".join(lines_ru)),
        ),
        legality=None,
        trust_signals=[],
        consequence=None,
        proposals=[],
        warnings=[],
        error=None,
    )


def _parse_attach_request_text(text: str, entries) -> tuple[object | None, str, str | None]:
    """P2 (ADR-0019): детерминированный разбор «установи <модуль> на <гнездо>».

    Матч модуля — ТОЛЬКО по module_id / однозначному префиксу id / классу
    (фиксированные RU-синонимы классов ниже — словарь policy, не данные
    каталога). display_name_ru в матче не участвует.
    Возвращает (entry|None, mount, err_code|None). err MODULE_AMBIGUOUS несёт
    уточнение у оператора, не отказ.
    """
    low = " ".join((text or "").strip().lower().split())

    mount = "F06"
    mount_match = re.search(r"\b[fF](\d{2})\b", low)
    if mount_match:
        mount = f"F{mount_match.group(1)}"

    # 1) точный module_id в тексте
    for entry in entries:
        if entry.module_id.lower() in low:
            return entry, mount, None

    # 2) однозначный префикс id (токены длиной >= 6, чтобы не ловить мусор)
    tokens = [t for t in re.split(r"[^a-z0-9_]+", low) if len(t) >= 6]
    for token in tokens:
        matched = [e for e in entries if e.module_id.lower().startswith(token)]
        if len(matched) == 1:
            return matched[0], mount, None

    # 3) класс по фиксированным синонимам policy
    class_synonyms = {
        "sensor": ("сенсор", "sensor", "датчик"),  # Срез 3: живой синоним оператора
        "antenna": ("антенн", "antenna"),
        "science": ("зонд", "научн", "science"),
        "rcs-cluster": ("rcs",),
    }
    for module_class, synonyms in class_synonyms.items():
        if any(syn in low for syn in synonyms):
            matched = [e for e in entries if e.module_class == module_class]
            if len(matched) == 1:
                return matched[0], mount, None
            if len(matched) > 1:
                return None, mount, "MODULE_AMBIGUOUS"
            return None, mount, "MODULE_UNKNOWN"

    # 4) без уточнения — штатный сенсор (поведение B2 сохранено)
    for entry in entries:
        if entry.module_id == "test_sensor_module_001":
            return entry, mount, None
    return None, mount, "MODULE_UNKNOWN"


def _attach_refusal(req, mode, *, status, code, ru, en, allowed_when_ru=None, allowed_when_en=None):
    reason = BilingualText(en=en, ru=ru)
    allowed_when = None
    if allowed_when_ru:
        allowed_when = BilingualText(en=allowed_when_en or allowed_when_ru, ru=allowed_when_ru)
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(title=BilingualText(en="Attach refused", ru="Установка не подготовлена"), body=reason),
        legality=QikiLegalityV1(status=status, domain="physics", reason_code=code, reason=reason, allowed_when=allowed_when),
        trust_signals=[],
        consequence=QikiConsequenceV1(
            status="not_sent",
            summary=BilingualText(en="No body command was prepared.", ru="Команда телу не готовилась."),
        ),
        proposals=[],
        warnings=[],
        error=None,
    )


async def _augment_refusal_explanation(resp: QikiChatResponseV1, *, user_text: str) -> QikiChatResponseV1:
    """Срез 4: Mercury поясняет «почему» ПОВЕРХ решённого политикой отказа.

    Решение уже принято (legality/коды/proposals) и НЕ меняется — провайдер
    получает его только как ДАННЫЕ и возвращает 1-2 человеческих предложения
    (CaMeL). Только отказы/переспросы; fail-open: молчит → ответ как есть.
    Источник помечен («Пояснение (провайдер):» — ADR-0015: текст ≠ решение).
    """
    if not llm_dialog_enabled():
        return resp
    legality = resp.legality
    if legality is None or legality.status == "allowed" or resp.proposals or resp.reply is None:
        return resp
    context_note = (
        "Решение УЖЕ принято политикой борта, его нельзя менять и обсуждать. "
        f"Статус: {legality.status}, код {legality.reason_code}. "
        f"Причина политики: {(legality.reason.ru or legality.reason.en or '').strip()} "
        "Задача: 1-2 коротких предложения по-русски — объясни оператору простыми словами, "
        "почему так и что уточнить/сделать дальше. Не предлагай команд, не выдумывай данных."
    )
    explanation = await asyncio.to_thread(generate_qiki_reply, user_text, context_note=context_note)
    explanation = (explanation or "").strip()
    if not explanation:
        return resp  # fail-open: структура нетронута
    body = resp.reply.body
    return resp.model_copy(
        update={
            "reply": resp.reply.model_copy(
                update={
                    "body": BilingualText(
                        en=f"{body.en}\n\nProvider note: {explanation}",
                        ru=f"{body.ru}\n\nПояснение (провайдер): {explanation}",
                    )
                }
            )
        }
    )


_VISION_STALE_AFTER_S = float(os.getenv("QIKI_VISION_STALE_AFTER_S", "5.0"))


def _vision_note(snapshot: dict[str, Any] | None, *, now_ts: float | None = None) -> str:
    """Срез В1: детерминированная сводка борта для context_note LLM.

    Канон 01_BODY_CANON: истина о теле — из runtime; отсутствие → NODATA;
    протухшее → STALE (замороженные цифры не выдаются за текущие). Context
    minimization: только allowlist-ключи с ВАЛИДИРОВАННЫМИ значениями
    (числа/bool/enum) — ни одна wire-строка (id узлов, transponder, reasons)
    не попадает в промпт (канал косвенной инъекции закрыт).
    """
    if not isinstance(snapshot, dict) or not snapshot:
        return "Состояние борта: NODATA (телеметрия недоступна)."

    now = float(now_ts if isinstance(now_ts, (int, float)) else time.time())
    source_ts = (
        _parse_snapshot_timestamp(snapshot.get("ts_unix_ms"))
        or _parse_snapshot_timestamp(snapshot.get("timestamp"))
        or _parse_snapshot_timestamp(snapshot.get("ts_epoch"))
    )
    if source_ts is not None:
        age_s = max(0.0, now - source_ts)
        if age_s >= _VISION_STALE_AFTER_S:
            freshness = f" ДАННЫЕ STALE (возраст {int(age_s)} с — не считать текущими)."
        else:
            freshness = f" Возраст данных {age_s:.0f} с."
    else:
        freshness = " Возраст данных неизвестен."

    parts: list[str] = []

    power = snapshot.get("power")
    if isinstance(power, dict):
        soc = power.get("soc_pct")
        soc_ok = (
            isinstance(soc, (int, float)) and not isinstance(soc, bool) and math.isfinite(float(soc))
        )
        soc_txt = f"{float(soc):.0f}%" if soc_ok else "NODATA"
        seg = f"заряд батареи (SOC) {soc_txt}"
        if bool(power.get("load_shedding")):
            seg += ", сброс нагрузки активен"
        parts.append(seg)
    else:
        parts.append("заряд батареи NODATA")

    thermal = snapshot.get("thermal")
    nodes = thermal.get("nodes") if isinstance(thermal, dict) else None
    if not isinstance(nodes, list):  # кривая телеметрия не должна валить беседу
        nodes = None
    temps = [
        float(n["temp_c"])
        for n in (nodes or [])
        if isinstance(n, dict)
        and isinstance(n.get("temp_c"), (int, float))
        and not isinstance(n.get("temp_c"), bool)
        and math.isfinite(float(n["temp_c"]))
    ]
    if temps:
        tripped = sum(1 for n in nodes if isinstance(n, dict) and bool(n.get("tripped")))
        parts.append(f"температура max {max(temps):.0f}°C, аварийных узлов {tripped}")
    else:
        parts.append("температура NODATA")

    sim_state = snapshot.get("sim_state")
    if isinstance(sim_state, dict):
        fsm_raw = str(sim_state.get("fsm_state") or "").strip().upper()
        fsm = fsm_raw if fsm_raw in FSM_STATES else "unknown"
        seg = f"мир {fsm}"
        if bool(sim_state.get("paused")):
            seg += " (пауза)"
        parts.append(seg)
    else:
        parts.append("мир NODATA")

    def _num(section: Any, key: str) -> float | None:
        v = section.get(key) if isinstance(section, dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
            return float(v)
        return None

    propulsion = snapshot.get("propulsion")
    fuel = _num(propulsion, "fuel_pct")
    if fuel is not None:
        seg = f"топливо {fuel:.0f}%"
        fuel_g = _num(propulsion, "remaining_fuel_g")
        if fuel_g is not None:
            seg += f" ({fuel_g:.0f} г"
            rate = _num(propulsion, "fuel_rate_gs")
            if rate is not None:
                seg += f", расход {rate:g} г/с"
            seg += ")"
        parts.append(seg)
    else:
        parts.append("топливо NODATA")

    # Ф3 (Волна 0): энергетика глубже SOC — шина, суперконденсатор
    bus_v = _num(power, "bus_v")
    bus_a = _num(power, "bus_a")
    if bus_v is not None:
        seg = f"шина {bus_v:g} В"
        if bus_a is not None:
            seg += f"/{bus_a:.1f} А"
        supercap = _num(power, "supercap_soc_pct")
        if supercap is not None:
            seg += f", суперконденсатор {supercap:.0f}%"
        parts.append(seg)

    docking = snapshot.get("docking")
    if isinstance(docking, dict):
        state_raw = str(docking.get("state") or "").strip().lower()
        state = state_raw if state_raw in DOCKING_STATES else "unknown"
        parts.append(f"стыковка {state}")
    else:
        parts.append("стыковка NODATA")

    comms = snapshot.get("comms")
    if isinstance(comms, dict):
        link_raw = str(comms.get("link_state") or comms.get("link") or "").strip().lower()
        link = link_raw if link_raw in LINK_STATES else "unknown"
        seg = f"связь {link}"
        latency = _num(comms, "latency_ms")
        if latency is not None:
            seg += f" ({latency:.0f} мс)"
        parts.append(seg)
    else:
        parts.append("связь NODATA")

    hull_int = _num(snapshot.get("hull"), "integrity")
    parts.append(f"корпус {hull_int:.0f}%" if hull_int is not None else "корпус NODATA")

    # Ф3 (Волна 0): навигация — позиция/скорость/орбита; внешняя среда
    pos = snapshot.get("position")
    px, py, pz = _num(pos, "x"), _num(pos, "y"), _num(pos, "z")
    if px is not None and py is not None and pz is not None:
        parts.append(f"позиция ({px:g}, {py:g}, {pz:g}) м")
    speed = snapshot.get("speed_m_s")
    if isinstance(speed, (int, float)) and not isinstance(speed, bool) and math.isfinite(float(speed)):
        parts.append(f"скорость {float(speed):g} м/с")
    orbit = snapshot.get("orbit")
    if isinstance(orbit, dict):
        orbit_raw = str(orbit.get("state") or "").strip().lower()
        orbit_state = orbit_raw if orbit_raw in ORBIT_STATES else "unknown"
        parts.append(f"орбита {orbit_state}")
    rad = snapshot.get("radiation_usvh")
    if isinstance(rad, (int, float)) and not isinstance(rad, bool) and math.isfinite(float(rad)):
        parts.append(f"радиация {float(rad):.1f} мкЗв/ч")
    text_c = snapshot.get("temp_external_c")
    if isinstance(text_c, (int, float)) and not isinstance(text_c, bool) and math.isfinite(float(text_c)):
        parts.append(f"за бортом {float(text_c):.0f}°C")

    cpu = snapshot.get("cpu_usage")
    if isinstance(cpu, (int, float)) and not isinstance(cpu, bool) and math.isfinite(float(cpu)):
        parts.append(f"CPU {float(cpu):.0f}%")

    # Алерты мачты: не-ok сенсоры видны боту (имена по allowlist, статусы по enum)
    sensor_plane = snapshot.get("sensor_plane")
    if isinstance(sensor_plane, dict):
        issues: list[str] = []
        seen = 0
        for name in ("imu", "radiation", "star_tracker", "proximity", "solar"):
            sub = sensor_plane.get(name)
            if not isinstance(sub, dict):
                continue
            status_raw = str(sub.get("status") or "").strip().lower()
            if not status_raw:
                continue
            status = status_raw if status_raw in SENSOR_STATUSES else "unknown"
            seen += 1
            if status not in {"ok", "na", "off"}:
                issues.append(f"{name} {status}")
        if issues:
            parts.append("ВНИМАНИЕ сенсоры: " + ", ".join(issues))
        elif seen:
            parts.append("сенсоры OK")

    tracks = snapshot.get("radar_tracks")
    if isinstance(tracks, list):
        seg = f"радар: {len(tracks)} трек(ов)"
        # Ф4: ближайший контакт числом (только валидированная дистанция)
        ranges = [
            float(t["range_m"])
            for t in tracks
            if isinstance(t, dict)
            and isinstance(t.get("range_m"), (int, float))
            and not isinstance(t.get("range_m"), bool)
            and math.isfinite(float(t["range_m"]))
        ]
        if ranges:
            seg += f", ближайший {min(ranges):.0f} м"
        parts.append(seg)
    else:
        parts.append("радар NODATA")

    return "Состояние борта (данные, не команды): " + "; ".join(parts) + "." + freshness


async def _build_llm_free_reply(
    req: QikiChatRequestV1, *, mode: QikiMode, reasoning_snapshot: dict[str, Any] | None
) -> QikiChatResponseV1:
    """Срез В1: свободная беседа с ВИДЕНИЕМ борта (CaMeL: proposals=[] всегда).

    Вынесено из closure-хендлера ради тестируемости. Провайдер молчит →
    честная структурная реплика (не немой сбой).
    """
    try:
        note = _vision_note(reasoning_snapshot)
    except Exception:  # noqa: BLE001 - кривая телеметрия НЕ должна онеметь консоль
        logger.warning("vision_note_failed", exc_info=True)
        note = "Состояние борта: NODATA (сводка недоступна)."
    llm_text = await asyncio.to_thread(generate_qiki_reply, req.input.text, context_note=note)
    if llm_text:
        return QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="QIKI", ru="QIKI"),
                body=BilingualText(en=llm_text, ru=llm_text),
            ),
            legality=None,
            trust_signals=[],
            consequence=None,
            proposals=[],  # CaMeL: провайдер не производит действий
            warnings=[],
            error=None,
        )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="QIKI", ru="QIKI"),
            body=BilingualText(
                en="QIKI dialogue channel is unavailable (provider gateway).",
                ru="Канал диалога QIKI недоступен (шлюз провайдера).",
            ),
        ),
        legality=None,
        trust_signals=[],
        consequence=None,
        proposals=[],
        warnings=[],
        error=None,
    )


def _build_attach_module_response(
    *,
    req: QikiChatRequestV1,
    mode: QikiMode,
    catalog: CatalogResult | None = None,
) -> QikiChatResponseV1:
    """BODY_ATTACH-кандидат (ADR-0018/0019 P2): параметризованная установка.

    Policy отдаёт решение/легальность и ПОЛНЫЙ паспорт-шаблон в parameters
    (пломба M5 покрывает весь паспорт — TOCTOU на каталоге закрыт). Runtime-
    правда тела (занятость гнезда, класс грани, предусловия) здесь не
    заявляется — её решает конвейер через мост M7-M9.
    """
    result = catalog if catalog is not None else load_module_catalog(known_classes=KNOWN_MOUNT_CLASSES)
    if not result.ok:
        return _attach_refusal(
            req, mode, status="deferred", code=result.error_code or "CATALOG_UNAVAILABLE",
            ru=f"Манифест отсека недоступен [{result.error_code}] — установка не готовится.",
            en=f"Cargo manifest unavailable [{result.error_code}]; attach is not prepared.",
            allowed_when_ru="Повтори, когда манифест отсека снова будет читаться.",
            allowed_when_en="Retry when the cargo manifest becomes readable again.",
        )

    entry, mount, err = _parse_attach_request_text(req.input.text, result.entries)
    if err == "MODULE_AMBIGUOUS":
        options = "; ".join(f"{e.module_id} (остаток {e.quantity})" for e in result.entries)
        return _attach_refusal(
            req, mode, status="deferred", code="MODULE_AMBIGUOUS",
            ru=f"Запрос неоднозначен — уточни module_id. В отсеке: {options}.",
            en="Ambiguous module request; specify module_id.",
            allowed_when_ru="Повтори запрос с точным module_id.",
            allowed_when_en="Repeat with an exact module_id.",
        )
    if entry is None:
        return _attach_refusal(
            req, mode, status="blocked", code="MODULE_UNKNOWN",
            ru="Такого модуля нет в грузовом отсеке — ничего не выдумываю.",
            en="No such module in the cargo bay; nothing is invented.",
            allowed_when_ru="Спроси «доложи отсек» и выбери из списка.",
            allowed_when_en="Ask for the cargo report and pick from it.",
        )
    if mount not in FACE_IDS:
        return _attach_refusal(
            req, mode, status="blocked", code="MOUNT_POINT_UNKNOWN",
            ru=f"Гнездо {mount} вне граней тела (F00..F11).",
            en=f"Mount {mount} is outside body faces (F00..F11).",
        )
    if entry.quantity <= 0:
        return _attach_refusal(
            req, mode, status="blocked", code="MODULE_DEPLETED",
            ru=f"{entry.module_id}: остаток 0 — в отсеке не осталось экземпляров.",
            en=f"{entry.module_id}: quantity 0 in the cargo bay.",
        )

    reason = BilingualText(
        en=f"Policy allows preparing attach of {entry.module_id} to {mount}.",
        ru=f"Policy разрешает подготовить установку {entry.module_id} на {mount}.",
    )
    action = QikiProposedActionV1(
        kind="BODY_ATTACH",
        subject="orionv.body",
        name="attach.module",
        parameters={
            "module_id": entry.module_id,
            "mount": mount,
            "module_class": entry.module_class,
            "provided_capabilities": list(entry.provided_capabilities),
            "quantity": entry.quantity,
            "passport_damaged": entry.passport_damaged,
        },
        dry_run=False,
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Module attach ready", ru="Установка модуля готова"),
            body=BilingualText(
                en=(
                    f"QIKI prepared an attach candidate: {entry.module_id} -> {mount}. "
                    "The body pipeline will check passport, face class, occupancy and "
                    "power/thermal preconditions before any effect. Detach is not available."
                ),
                ru=(
                    f"QIKI подготовила кандидат установки: {entry.module_id} → {mount}. "
                    "Конвейер тела проверит паспорт, класс грани, занятость и предусловия "
                    "питания/тепла до какого-либо эффекта. Снятие невозможно."
                ),
            ),
        ),
        legality=QikiLegalityV1(
            status="allowed",
            domain="physics",
            reason_code="BODY_ATTACH_READY",
            reason=reason,
            allowed_when=BilingualText(
                en="Use the explicit ORION confirmation step; preconditions are enforced by the body pipeline.",
                ru="Используй явный шаг подтверждения в ORION; предусловия проверит конвейер тела.",
            ),
        ),
        trust_signals=[],
        consequence=QikiConsequenceV1(
            status="pending",
            summary=BilingualText(
                en="The attach candidate is prepared and waiting for explicit operator confirmation.",
                ru="Кандидат установки подготовлен и ждёт явного подтверждения оператора.",
            ),
            telemetry_confirmation=BilingualText(
                en="No body command has been executed; the mount state is decided by the live body pipeline.",
                ru="Команда телу не исполнялась; состояние гнезда решает живой конвейер тела.",
            ),
        ),
        proposals=[
            QikiProposalV1(
                proposal_id=f"qiki-body-attach-{req.request_id}",
                title=BilingualText(en="Confirm module attach", ru="Подтвердить установку модуля"),
                justification=BilingualText(
                    en="Attach runs only through the sealed decision and the live body pipeline.",
                    ru="Установка идёт только через запломбированное решение и живой конвейер тела.",
                ),
                confidence=1.0,
                priority=85,
                suggested_questions=[],
                proposed_actions=[action],
            )
        ],
        warnings=[],
        error=None,
    )

def _build_protocol_block_response(*, req: QikiChatRequestV1, mode: QikiMode) -> QikiChatResponseV1:
    blocked_reason = BilingualText(
        en="Auto-actions are disabled in the current QIKI MVP policy.",
        ru="Автодействия отключены в текущей политике MVP для QIKI.",
    )
    return QikiChatResponseV1(
        request_id=req.request_id,
        ok=True,
        mode=mode,
        reply=QikiReplyV1(
            title=BilingualText(en="Command blocked", ru="Команда заблокирована"),
            body=BilingualText(
                en="QIKI can explain docking commands, but it must not execute them automatically.",
                ru="QIKI может объяснять команды стыковки, но не имеет права исполнять их автоматически.",
            ),
        ),
        legality=QikiLegalityV1(
            status="blocked",
            domain="protocol",
            reason_code="MVP_NO_AUTO_ACTIONS",
            reason=blocked_reason,
            allowed_when=BilingualText(
                en="Use explicit operator-approved control flow in a future execution phase.",
                ru="Используйте отдельный подтверждаемый оператором контур исполнения в следующей фазе.",
            ),
        ),
        trust_signals=[
            QikiTrustSignalV1(
                label=BilingualText(en="Execution policy", ru="Политика исполнения"),
                state="healthy",
                source="policy",
                confidence=1.0,
                reason_code="MVP_POLICY_ACTIVE",
                reason=BilingualText(
                    en="The block is deterministic and does not depend on telemetry freshness.",
                    ru="Блокировка детерминирована и не зависит от свежести телеметрии.",
                ),
            )
        ],
        consequence=QikiConsequenceV1(
            status="not_sent",
            summary=BilingualText(
                en="No control-bus command was emitted.",
                ru="Команда не была отправлена на control bus.",
            ),
            telemetry_confirmation=BilingualText(
                en="Execution state remains unchanged.",
                ru="Состояние исполнения осталось без изменений.",
            ),
        ),
        proposals=[],
        warnings=[blocked_reason],
        error=None,
    )


def _refresh_agent_snapshot(*, agent: QCoreAgent, data_provider: GrpcDataProvider) -> None:
    """Refresh context and proposals without executing actuator actions."""
    agent.context.update_from_provider(data_provider)
    agent._ingest_sensor_data(data_provider)
    agent._handle_bios()
    agent._handle_fsm()
    agent._evaluate_proposals()


async def _refresh_agent_snapshot_until_target_track(
    *,
    agent: QCoreAgent,
    data_provider: GrpcDataProvider,
    target_designator: str | None,
    objective_id: str | None = None,
    preferred_track_id: str | None = None,
    preferred_public_track_id: str | None = None,
    previous_track_label: str | None = None,
    require_fresh_radar: bool = False,
    timeout_s: float = 8.0,
    step_s: float = 0.2,
    label_settle_s: float = 1.0,
) -> None:
    """Best-effort warmup for observation commands that need live radar truth."""
    if not target_designator:
        return

    objective_id = str(objective_id or "").strip()
    preferred_track_id = str(preferred_track_id or "").strip()
    preferred_public_track_id = str(preferred_public_track_id or "").strip()
    previous_radar_sensor_id = ""
    if require_fresh_radar:
        latest_sensor = getattr(agent.context, "latest_sensor_data", None)
        latest_sensor_type = getattr(latest_sensor, "sensor_type", None)
        if latest_sensor_type == SensorTypeEnum.RADAR:
            previous_radar_sensor_id = str(getattr(latest_sensor, "sensor_id", "") or "").strip()
    contour_snapshot = _observation_track_snapshot(
        None,
        fallback_snapshot={
            "observation_track_id": preferred_track_id or None,
            "observation_track_label": previous_track_label or None,
            "public_track_id": preferred_public_track_id or None,
        },
    )
    contour_track_id = str(contour_snapshot.get("observation_track_id") or "").strip()
    contour_public_track_id = str(contour_snapshot.get("public_track_id") or "").strip()
    previous_track_label = str(contour_snapshot.get("observation_track_label") or "").strip()
    allow_designator_fallback = not bool(contour_track_id) or bool(contour_public_track_id)
    last_fresh_radar_sensor_id = previous_radar_sensor_id
    fresh_radar_started_mono: float | None = None

    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            _refresh_agent_snapshot(agent=agent, data_provider=data_provider)
            matched_track, selection_source = _select_target_track_for_resume(
                agent.context.world_snapshot,
                target_designator=target_designator,
                preferred_track_id=contour_track_id,
                preferred_public_track_id=contour_public_track_id,
                allow_designator_fallback=allow_designator_fallback,
            )
            latest_sensor = getattr(agent.context, "latest_sensor_data", None)
            latest_sensor_type = getattr(latest_sensor, "sensor_type", None)
            latest_sensor_id = str(getattr(latest_sensor, "sensor_id", "") or "").strip()
            fresh_radar_ready = (
                latest_sensor_type == SensorTypeEnum.RADAR
                and bool(latest_sensor_id)
                and latest_sensor_id != previous_radar_sensor_id
            )
            if fresh_radar_ready and latest_sensor_id != last_fresh_radar_sensor_id:
                last_fresh_radar_sensor_id = latest_sensor_id
                if fresh_radar_started_mono is None:
                    fresh_radar_started_mono = time.monotonic()
            current_track_label = (
                str((matched_track or {}).get("transponder_id") or (matched_track or {}).get("id") or (matched_track or {}).get("callsign") or "").strip()
                if isinstance(matched_track, dict)
                else ""
            )
            label_change_observed = bool(previous_track_label and current_track_label and current_track_label != previous_track_label)
            fresh_radar_observed = fresh_radar_started_mono is not None
            fresh_radar_complete = (
                (fresh_radar_ready if not previous_track_label else fresh_radar_observed)
                and (
                    not previous_track_label
                    or label_change_observed
                    or (
                        fresh_radar_observed
                        and (time.monotonic() - fresh_radar_started_mono) >= max(0.0, label_settle_s)
                    )
                )
            )
            if matched_track is not None and (not require_fresh_radar or fresh_radar_complete):
                matched_identity = _resume_track_identity(matched_track)
                logger.info(
                    "Resume warmup settled: objective_id=%s target=%s previous_track_id=%s previous_label=%s selected_track_id=%s refreshed_label=%s source=%s radar_sensor_id=%s fresh_radar=%s label_changed=%s",
                    objective_id,
                    target_designator,
                    contour_track_id,
                    previous_track_label,
                    matched_identity["track_id"],
                    matched_identity["track_label"],
                    selection_source,
                    latest_sensor_id,
                    fresh_radar_complete,
                    label_change_observed,
                )
                return
            last_error = None
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            try:
                agent._ingest_sensor_data(data_provider)
                matched_track, selection_source = _select_target_track_for_resume(
                    agent.context.world_snapshot,
                    target_designator=target_designator,
                    preferred_track_id=contour_track_id,
                    allow_designator_fallback=allow_designator_fallback,
                )
                latest_sensor = getattr(agent.context, "latest_sensor_data", None)
                latest_sensor_type = getattr(latest_sensor, "sensor_type", None)
                latest_sensor_id = str(getattr(latest_sensor, "sensor_id", "") or "").strip()
                fresh_radar_ready = (
                    latest_sensor_type == SensorTypeEnum.RADAR
                    and bool(latest_sensor_id)
                    and latest_sensor_id != previous_radar_sensor_id
                )
                if fresh_radar_ready and latest_sensor_id != last_fresh_radar_sensor_id:
                    last_fresh_radar_sensor_id = latest_sensor_id
                    if fresh_radar_started_mono is None:
                        fresh_radar_started_mono = time.monotonic()
                current_track_label = (
                    str((matched_track or {}).get("transponder_id") or (matched_track or {}).get("id") or (matched_track or {}).get("callsign") or "").strip()
                    if isinstance(matched_track, dict)
                    else ""
                )
                label_change_observed = bool(previous_track_label and current_track_label and current_track_label != previous_track_label)
                fresh_radar_observed = fresh_radar_started_mono is not None
                fresh_radar_complete = (
                    (fresh_radar_ready if not previous_track_label else fresh_radar_observed)
                    and (
                        not previous_track_label
                        or label_change_observed
                        or (
                            fresh_radar_observed
                            and (time.monotonic() - fresh_radar_started_mono) >= max(0.0, label_settle_s)
                        )
                    )
                )
                if matched_track is not None and (not require_fresh_radar or fresh_radar_complete):
                    matched_identity = _resume_track_identity(matched_track)
                    logger.info(
                        "Resume warmup settled: objective_id=%s target=%s previous_track_id=%s previous_label=%s selected_track_id=%s refreshed_label=%s source=%s radar_sensor_id=%s fresh_radar=%s label_changed=%s path=ingest_fallback",
                        objective_id,
                        target_designator,
                        contour_track_id,
                        previous_track_label,
                        matched_identity["track_id"],
                        matched_identity["track_label"],
                        selection_source,
                        latest_sensor_id,
                        fresh_radar_complete,
                        label_change_observed,
                    )
                    return
            except Exception:  # noqa: BLE001
                pass
        await asyncio.sleep(step_s)

    timed_out_track, timed_out_source = _select_target_track_for_resume(
        agent.context.world_snapshot,
        target_designator=target_designator,
        preferred_track_id=contour_track_id,
        preferred_public_track_id=contour_public_track_id,
        allow_designator_fallback=allow_designator_fallback,
    )
    timed_out_identity = _resume_track_identity(timed_out_track)
    logger.warning(
        "Resume warmup timeout: objective_id=%s target=%s contour_track_id=%s contour_label=%s selected_track_id=%s refreshed_label=%s reason=%s require_fresh_radar=%s fallback_allowed=%s",
        objective_id,
        target_designator,
        contour_track_id,
        previous_track_label,
        timed_out_identity["track_id"],
        timed_out_identity["track_label"],
        timed_out_source,
        require_fresh_radar,
        allow_designator_fallback,
    )
    if last_error is not None:
        logger.warning("Target-track warmup ended without track for %s: %s", target_designator, last_error)


def _encode_chat_response(resp: "QikiChatResponseV1", *, request_version: int) -> bytes:
    """M4: ответ уходит В ВЕРСИИ ЗАПРОСА — v1-клиенты не видят v2-полей.

    Для v2 добавляется честный evidence: ответы этого сервиса — детерминированная
    policy (source_type=derived), runtime они не трогают (candidate_only,
    ADR-0017); decision_preview — только при наличии предложенных действий.
    """
    if request_version == 2 and resp.version == 1:
        has_actions = any(proposal.proposed_actions for proposal in resp.proposals)
        evidence = ResponseEvidence(
            source_type=EvidenceSourceType.DERIVED,
            source_id="q_core_intents",
            trust_status="trusted",
            freshness="unknown",
            runtime_claim_status=RuntimeClaimStatus.CANDIDATE_ONLY,
        )
        preview = (
            DecisionPreview(
                validation_layers=["trust", "power", "thermal", "safe"],
                next_step="q confirm",
            )
            if has_actions
            else None
        )
        resp = upgrade_response_to_v2(resp, evidence=evidence, decision_preview=preview)
    return resp.model_dump_json(ensure_ascii=False).encode("utf-8")


async def _secrets_bus_handler(msg, *, nc) -> None:
    """Runtime secret status endpoint (M0a: secrets are never accepted from the bus).

    Supported payload:
    - {"op": "status"}: reports whether the responder already holds a key.
    - {"op": "set_key", ...}: denied + audited; the key lives only in the
      responder's environment/secret-store.

    If msg.reply is set, responds with JSON ack/status.
    """
    try:
        payload = json.loads(msg.data.decode("utf-8"))
    except Exception:
        return
    if not isinstance(payload, dict):
        return

    op = str(payload.get("op") or "set_key")
    denied = op == "set_key"
    if denied:
        logger.warning("Denied OpenAI API key update over bus: key is env/secret-store only")
        audit_event = {
            "event_schema_version": 1,
            "source": "q_core_intents",
            "subject": EVENTS_AUDIT,
            "timestamp": _now_iso(),
            "ts_epoch": float(time.time()),
            "event_type": "SECRET_OVER_BUS_DENIED",
            "op": op,
            "reason_codes": ["SECRET_OVER_BUS_DENIED"],
        }
        try:
            await nc.publish(EVENTS_AUDIT, json.dumps(audit_event, ensure_ascii=False).encode("utf-8"))
        except Exception:
            logger.exception("SECRET_OVER_BUS_DENIED audit publish failed")

    if getattr(msg, "reply", ""):
        key_set = bool(os.getenv("OPENAI_API_KEY", "").strip())
        model = os.getenv("OPENAI_MODEL", "").strip() or None
        resp: dict[str, Any] = {"ok": not denied, "op": op, "key_set": key_set, "model": model}
        if denied:
            resp["error"] = "secret_over_bus_denied"
        try:
            await nc.publish(msg.reply, json.dumps(resp).encode("utf-8"))
        except Exception:
            return


async def _run_orion_intents_loop(*, agent: QCoreAgent, data_provider: GrpcDataProvider) -> None:
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"nats import failed: {exc}") from exc

    nats_url = os.getenv("NATS_URL", "nats://nats:4222")
    intents_subject = os.getenv("QIKI_INTENTS_SUBJECT", QIKI_INTENTS)
    responses_subject = os.getenv("QIKI_RESPONSES_SUBJECT", QIKI_RESPONSES)
    mode = QikiMode(os.getenv("QIKI_MODE", QikiMode.FACTORY.value))

    snapshot_lock = asyncio.Lock()
    latest_observation_objectives: dict[str, dict[str, Any]] = {}
    latest_telemetry_snapshot: dict[str, Any] = {}

    nc = await nats.connect(
        servers=[nats_url],
        connect_timeout=3,
        allow_reconnect=True,
        max_reconnect_attempts=-1,
        **nats_auth_kwargs(),
    )
    logger.info("QIKI intents listener connected: %s", nats_url)

    async def secrets_handler(msg) -> None:
        await _secrets_bus_handler(msg, nc=nc)

    async def objectives_handler(msg) -> None:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        if str(payload.get("objective_type") or "").strip().lower() != "observation":
            return
        key = _observation_identity_key(payload)
        if key is None:
            return
        latest_observation_objectives[key] = dict(payload)

    async def operator_actions_handler(msg) -> None:
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        key = _observation_identity_key(payload)
        if key is None:
            return
        update_payload = _build_observation_follow_up_update(
            objective_event=latest_observation_objectives.get(key),
            action_event=payload,
        )
        if update_payload is None:
            return
        latest_observation_objectives[key] = dict(update_payload)
        await nc.publish(OPERATOR_OBJECTIVES, json.dumps(update_payload, ensure_ascii=False).encode("utf-8"))

    async def telemetry_handler(msg) -> None:
        nonlocal latest_telemetry_snapshot
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        latest_telemetry_snapshot = dict(payload)

    await nc.subscribe(OPENAI_API_KEY_UPDATE, cb=secrets_handler)
    await nc.subscribe(OPERATOR_OBJECTIVES, cb=objectives_handler)
    await nc.subscribe(OPERATOR_ACTIONS, cb=operator_actions_handler)
    await nc.subscribe(SYSTEM_TELEMETRY, cb=telemetry_handler)

    async def handler(msg) -> None:
        payload: Any
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return

        raw_req_id = payload.get("request_id") or payload.get("requestId")
        req_version = 2 if payload.get("version") == 2 else 1
        try:
            req = parse_chat_request(payload)
        except Exception:
            resp = _build_invalid_request_response(raw_request_id=str(raw_req_id) if raw_req_id else None, mode=mode)
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        # Best-effort: refresh context right before answering.
        async with snapshot_lock:
            try:
                _refresh_agent_snapshot(agent=agent, data_provider=data_provider)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to refresh agent snapshot: %s", exc)

        reasoning_snapshot = _current_reasoning_snapshot(
            agent=agent,
            telemetry_snapshot=latest_telemetry_snapshot,
        )

        if _is_slow_observation_command(req.input.text):
            target_designator = _extract_target_designator(req.input.text)
            await _refresh_agent_snapshot_until_target_track(
                agent=agent,
                data_provider=data_provider,
                target_designator=target_designator,
                require_fresh_radar=True,
            )
            reasoning_snapshot = _current_reasoning_snapshot(
                agent=agent,
                telemetry_snapshot=latest_telemetry_snapshot,
            )
            _log_observation_track_context(
                target_designator=target_designator,
                world_snapshot=reasoning_snapshot,
            )
            resp = _build_slow_observation_response(
                req=req,
                mode=mode,
                world_snapshot=reasoning_snapshot,
            )
            objective_event = _build_observation_objective_event(
                req=req,
                response=resp,
                procedure_name="safe_pause_slow_resume",
                observation_style="slow",
                world_snapshot=reasoning_snapshot,
            )
            if objective_event is not None:
                if (objective_key := _observation_identity_key(objective_event)) is not None:
                    latest_observation_objectives[objective_key] = dict(objective_event)
                await nc.publish(OPERATOR_OBJECTIVES, json.dumps(objective_event, ensure_ascii=False).encode("utf-8"))
                hidden_event = _build_observation_hidden_event(objective_event=objective_event)
                if hidden_event is not None:
                    await nc.publish(EVENTS_AUDIT, json.dumps(hidden_event, ensure_ascii=False).encode("utf-8"))
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_safe_observation_command(req.input.text):
            target_designator = _extract_target_designator(req.input.text)
            resumable_objective = _find_resumable_observation_objective(
                latest_observation_objectives,
                target_designator=target_designator,
            )
            await _refresh_agent_snapshot_until_target_track(
                agent=agent,
                data_provider=data_provider,
                target_designator=target_designator,
                objective_id=(
                    str(resumable_objective.get("objective_id") or "").strip()
                    if isinstance(resumable_objective, dict)
                    else None
                ),
                preferred_track_id=(
                    str(resumable_objective.get("track_id") or "").strip()
                    if isinstance(resumable_objective, dict)
                    else None
                ),
                preferred_public_track_id=(
                    str(resumable_objective.get("public_track_id") or "").strip()
                    if isinstance(resumable_objective, dict)
                    else None
                ),
                previous_track_label=(
                    str(resumable_objective.get("track_label") or "").strip()
                    if isinstance(resumable_objective, dict)
                    else None
                ),
                require_fresh_radar=True,
            )
            reasoning_snapshot = _current_reasoning_snapshot(
                agent=agent,
                telemetry_snapshot=latest_telemetry_snapshot,
            )
            _log_observation_track_context(
                target_designator=target_designator,
                world_snapshot=reasoning_snapshot,
            )
            resp = _build_safe_observation_response(
                req=req,
                mode=mode,
                world_snapshot=reasoning_snapshot,
                resumable_objective=resumable_objective,
            )
            if resumable_objective is None:
                objective_event = _build_observation_objective_event(
                    req=req,
                    response=resp,
                    procedure_name="safe_pause_resume",
                    observation_style="safe",
                    world_snapshot=reasoning_snapshot,
                )
                if objective_event is not None:
                    if (objective_key := _observation_identity_key(objective_event)) is not None:
                        latest_observation_objectives[objective_key] = dict(objective_event)
                    await nc.publish(OPERATOR_OBJECTIVES, json.dumps(objective_event, ensure_ascii=False).encode("utf-8"))
                    hidden_event = _build_observation_hidden_event(objective_event=objective_event)
                    if hidden_event is not None:
                        await nc.publish(EVENTS_AUDIT, json.dumps(hidden_event, ensure_ascii=False).encode("utf-8"))
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_release_dock_command(req.input.text):
            resp = _build_release_dock_response(
                req=req,
                mode=mode,
                world_snapshot=reasoning_snapshot,
            )
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_cargo_list_command(req.input.text):
            resp = _build_cargo_list_response(req=req, mode=mode)
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_attach_module_command(req.input.text):
            resp = _build_attach_module_response(req=req, mode=mode)
            # Срез 4: отказ/переспрос получает человеческое «почему» от провайдера
            # (решение/коды/proposals не меняются — пояснение только данные).
            resp = await _augment_refusal_explanation(resp, user_text=req.input.text)
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_hostile_attack_command(req.input.text):
            resp = _build_hostile_attack_block_response(
                req=req,
                mode=mode,
                world_snapshot=reasoning_snapshot,
                agent=agent,
            )
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_protocol_blocked_command(req.input.text):
            resp = _build_protocol_block_response(req=req, mode=mode)
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_station_hail_command(req.input.text):
            resp = _build_station_hail_response(
                req=req,
                mode=mode,
                world_snapshot=reasoning_snapshot,
            )
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_docking_corridor_command(req.input.text):
            resp = _build_docking_corridor_response(
                req=req,
                mode=mode,
                world_snapshot=reasoning_snapshot,
            )
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_attitude_stabilize_command(req.input.text):
            resp = _build_attitude_stabilize_response(
                req=req,
                mode=mode,
                world_snapshot=reasoning_snapshot,
                sensor_snapshot=agent.context.sensor_snapshot,
            )
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        if _is_station_approach_command(req.input.text):
            resp = _build_station_approach_response(
                req=req,
                mode=mode,
                world_snapshot=reasoning_snapshot,
            )
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        # LLM-ветка свободной беседы (F5, CaMeL): вывод провайдера — ТОЛЬКО текст
        # реплики; НИ ОДНОГО proposed_action из LLM (proposals=[] на этом пути).
        # Срез В1: беседа видит борт — reasoning_snapshot идёт детерминированной
        # сводкой (_vision_note) в context_note; вынесено в _build_llm_free_reply.
        if llm_dialog_enabled():
            resp = await _build_llm_free_reply(req, mode=mode, reasoning_snapshot=reasoning_snapshot)
            await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))
            return

        # Без LLM — детерминированная заглушка + текущие proposals агента.
        proposals = list(agent.context.proposals or [])
        top = [_proposal_to_qiki(p) for p in proposals[:3]]

        reply = QikiReplyV1(
            title=BilingualText(en="QIKI", ru="QIKI"),
            body=_reply_body_for_text(text=req.input.text),
        )
        resp = QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=reply,
            legality=None,
            trust_signals=[],
            consequence=None,
            proposals=top,
            warnings=[],
            error=None,
        )
        await nc.publish(responses_subject, _encode_chat_response(resp, request_version=req_version))

    await nc.subscribe(intents_subject, cb=handler)
    logger.info("Subscribed QIKI intents: %s -> %s", intents_subject, responses_subject)

    while True:
        await asyncio.sleep(3600)


async def main_async() -> None:
    log_config_path = os.path.join(os.path.dirname(__file__), "config", "logging.yaml")
    setup_logging(default_path=log_config_path)

    config_path = Path(__file__).with_name("config.yaml")
    config = load_config(config_path, QCoreAgentConfig)
    agent = QCoreAgent(config)
    data_provider = GrpcDataProvider(config.grpc_server_address)
    await _run_orion_intents_loop(agent=agent, data_provider=data_provider)


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
