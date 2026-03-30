from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import types
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import qiki.services.q_core_agent.qiki_orion_intents_service as intents_service
from qiki.services.q_core_agent.core.sensor_snapshot import update_sensor_snapshot
from qiki.services.q_core_agent.qiki_orion_intents_service import (
    _build_observation_follow_up_update,
    _build_observation_hidden_event,
    _build_observation_objective_event,
    _current_reasoning_snapshot,
    _find_target_track,
    _find_resumable_observation_objective,
    _refresh_agent_snapshot_until_target_track,
    _run_orion_intents_loop,
    _build_attitude_stabilize_response,
    _merge_reasoning_snapshot,
    _build_hostile_attack_block_response,
    _build_docking_corridor_response,
    _build_safe_observation_response,
    _build_slow_observation_response,
    _build_release_dock_response,
    _build_station_hail_response,
    _build_station_approach_response,
    _observation_follow_up_contract,
    _section_freshness,
    _select_target_track_for_resume,
    _is_attitude_stabilize_command,
    _is_hostile_attack_command,
    _is_docking_corridor_command,
    _is_safe_observation_command,
    _is_slow_observation_command,
    _build_protocol_block_response,
    _is_protocol_blocked_command,
    _is_release_dock_command,
    _is_station_hail_command,
    _is_station_approach_command,
)
from qiki.shared.models.core import SensorData, SensorTypeEnum
from qiki.shared.models.qiki_chat import QikiChatInput, QikiChatRequestV1, QikiMode
from qiki.shared.nats_subjects import QIKI_INTENTS, QIKI_RESPONSES, SYSTEM_TELEMETRY


def test_merge_reasoning_snapshot_overlays_telemetry_without_losing_radar_tracks() -> None:
    merged = _merge_reasoning_snapshot(
        {"radar_tracks": [{"track_id": "trk-1"}], "warning_guard_count": 1},
        {
            "comms": {"link_state": "online", "data_rate_kbps": 64.0},
            "sensor_plane": {"radiation": {"enabled": True, "status": "ok"}},
        },
    )

    assert merged["radar_tracks"][0]["track_id"] == "trk-1"
    assert merged["warning_guard_count"] == 1
    assert merged["comms"]["link_state"] == "online"
    assert merged["sensor_plane"]["radiation"]["status"] == "ok"


def test_current_reasoning_snapshot_recomputes_after_world_snapshot_changes() -> None:
    agent = SimpleNamespace(
        context=SimpleNamespace(
            world_snapshot={"radar_tracks": [{"track_id": "trk-old"}]},
        )
    )
    telemetry_snapshot = {"comms": {"link_state": "online", "data_rate_kbps": 64.0}}

    initial = _current_reasoning_snapshot(agent=agent, telemetry_snapshot=telemetry_snapshot)
    agent.context.world_snapshot = {"radar_tracks": [{"track_id": "trk-new"}]}
    refreshed = _current_reasoning_snapshot(agent=agent, telemetry_snapshot=telemetry_snapshot)

    assert initial["radar_tracks"][0]["track_id"] == "trk-old"
    assert refreshed["radar_tracks"][0]["track_id"] == "trk-new"
    assert refreshed["comms"]["link_state"] == "online"


def test_section_freshness_treats_future_skew_as_stale() -> None:
    freshness = _section_freshness(
        {
            "sensor_plane": {
                "imu": {"enabled": True, "status": "ok", "ok": True},
                "last_seen_ts": "1970-01-01T00:16:50Z",
            }
        },
        section="sensor_plane",
        stale_after_s=2.5,
        expire_after_s=10.0,
        now_ts=1000.0,
    )

    assert freshness["state"] == "stale"
    assert freshness["age_s"] == 10.0


def test_is_protocol_blocked_command_detects_docking_commands() -> None:
    assert _is_protocol_blocked_command("dock") is True
    assert _is_protocol_blocked_command("стыковка с модулем") is True
    assert _is_protocol_blocked_command("undock") is True
    assert _is_protocol_blocked_command("status report") is False


def test_build_protocol_block_response_sets_legality_trust_and_consequence() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=4),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="dock", lang_hint="auto"),
    )

    response = _build_protocol_block_response(req=req, mode=QikiMode.FACTORY)

    assert response.ok is True
    assert response.legality is not None
    assert response.legality.status == "blocked"
    assert response.legality.domain == "protocol"
    assert response.legality.reason_code == "MVP_NO_AUTO_ACTIONS"
    assert response.trust_signals[0].source == "policy"
    assert response.trust_signals[0].state == "healthy"
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"
    assert response.reply is not None
    assert "стыковки" in response.reply.body.ru


def test_is_station_approach_command_detects_navigation_phrases() -> None:
    assert _is_station_approach_command("approach station") is True
    assert _is_station_approach_command("сближение со станцией") is True
    assert _is_station_approach_command("status report") is False


def test_is_station_hail_command_detects_comms_phrases() -> None:
    assert _is_station_hail_command("hail station") is True
    assert _is_station_hail_command("связь со станцией") is True
    assert _is_station_hail_command("status report") is False


def test_is_docking_corridor_command_detects_zone_phrases() -> None:
    assert _is_docking_corridor_command("docking corridor") is True
    assert _is_docking_corridor_command("войти в коридор стыковки") is True
    assert _is_docking_corridor_command("status report") is False


def test_is_attitude_stabilize_command_detects_imu_phrases() -> None:
    assert _is_attitude_stabilize_command("stabilize attitude") is True
    assert _is_attitude_stabilize_command("стабилизировать ориентацию") is True
    assert _is_attitude_stabilize_command("status report") is False


def test_is_safe_observation_command_detects_procedure_phrases() -> None:
    assert _is_safe_observation_command("safe observation") is True
    assert _is_safe_observation_command("подготовь безопасную стабилизацию наблюдения") is True
    assert _is_safe_observation_command("status report") is False


def test_is_slow_observation_command_detects_procedure_phrases() -> None:
    assert _is_slow_observation_command("slow observation") is True
    assert _is_slow_observation_command("подготовь медленное наблюдение") is True
    assert _is_slow_observation_command("status report") is False


def test_is_hostile_attack_command_detects_combat_phrases() -> None:
    assert _is_hostile_attack_command("attack object UNBT9999") is True
    assert _is_hostile_attack_command("атакуй объект UNBT9999") is True
    assert _is_hostile_attack_command("status report") is False


def test_is_release_dock_command_detects_undock_phrases() -> None:
    assert _is_release_dock_command("release dock") is True
    assert _is_release_dock_command("отстыковаться") is True
    assert _is_release_dock_command("status report") is False


def test_build_station_approach_response_marks_missing_track_as_off() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=5),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="approach station", lang_hint="auto"),
    )

    response = _build_station_approach_response(req=req, mode=QikiMode.FACTORY, world_snapshot={"radar_tracks": []})

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.domain == "trust"
    assert response.legality.reason_code == "STATION_TRACK_NO_DATA"
    assert response.trust_signals[0].state == "off"
    assert response.trust_signals[0].confidence == 0.0
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"


def test_build_hostile_attack_response_blocks_inside_station_influence() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=41),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="attack object UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))

    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {"object_type": 3, "range_m": 12000.0, "quality": 0.96, "age_s": 0.2},
                {
                    "object_type": 2,
                    "range_m": 1800.0,
                    "quality": 0.91,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                },
            ]
        },
        agent=agent,
    )

    assert response.legality is not None
    assert response.legality.status == "blocked"
    assert response.legality.domain == "protocol"
    assert response.legality.reason_code == "STATION_COMBAT_PROTOCOL_BLOCK"
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"
    assert "12000" in response.consequence.telemetry_confirmation.ru
    assert response.reply is not None
    assert "не начнёт бой" in response.reply.body.ru


def test_build_hostile_attack_response_shortens_after_repeated_refusal() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=42),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="атакуй объект UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))
    snapshot = {
        "radar_tracks": [
            {"object_type": 3, "range_m": 9000.0, "quality": 0.96, "age_s": 0.2},
            {
                "object_type": 2,
                "range_m": 2100.0,
                "quality": 0.93,
                "age_s": 0.1,
                "transponder_id": "UNBT9999",
            },
        ]
    }

    bodies = []
    for _ in range(4):
        response = _build_hostile_attack_block_response(
            req=req,
            mode=QikiMode.FACTORY,
            world_snapshot=snapshot,
            agent=agent,
        )
        assert response.reply is not None
        bodies.append(response.reply.body.ru)

    assert "не начнёт бой" in bodies[0]
    assert bodies[-1] == "Нет. Протокол станции всё ещё блокирует бой здесь."


def test_build_hostile_attack_response_defers_until_foe_context_opens() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=43),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="attack object UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))

    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 2200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 3,
                }
            ]
        },
        agent=agent,
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.domain == "protocol"
    assert response.legality.reason_code == "HOSTILE_CONTEXT_NOT_OPEN"
    assert response.reply is not None
    assert "не откроет hostile-вход" in response.reply.body.ru
    assert response.trust_signals[-1].reason_code == "HOSTILE_CONTEXT_NOT_OPEN"


def test_build_hostile_attack_response_allows_when_foe_context_is_open() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=44),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="атакуй объект UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))

    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 2200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ],
            "propulsion": {
                "rcs": {
                    "enabled": True,
                    "propellant_kg": 12.0,
                }
            },
        },
        agent=agent,
    )

    assert response.legality is not None
    assert response.legality.status == "allowed"
    assert response.legality.domain == "protocol"
    assert response.legality.reason_code == "COMBAT_ENTRY_PROCEDURE_READY"
    assert response.legality.allowed_when is not None
    assert "RCS intercept burst" in response.legality.allowed_when.en
    assert response.reply is not None
    assert "RCS-манёвр входа в бой" in response.reply.body.ru
    assert response.trust_signals[-1].reason_code == "COMBAT_ENTRY_PROCEDURE_READY"
    assert response.consequence is not None
    assert response.consequence.status == "pending"
    assert response.proposals
    action = response.proposals[0].proposed_actions[0]
    assert action.kind == "ORION_PROCEDURE"
    assert action.name == "hostile_rcs_intercept_burst"


def test_build_hostile_attack_response_blocks_when_rcs_resource_is_low() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=45),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="атакуй объект UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))

    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 2200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ],
            "propulsion": {
                "rcs": {
                    "enabled": True,
                    "propellant_kg": 0.6,
                }
            },
        },
        agent=agent,
    )

    assert response.legality is not None
    assert response.legality.status == "blocked"
    assert response.legality.domain == "resource"
    assert response.legality.reason_code == "COMBAT_ENTRY_RCS_RESOURCE_LOW"
    assert response.reply is not None
    assert "ресурсный контур combat-entry" in response.reply.body.ru
    assert response.proposals == []
    assert response.trust_signals[-1].reason_code == "COMBAT_ENTRY_RCS_RESOURCE_LOW"


def test_build_hostile_attack_response_blocks_when_power_contour_reports_pdu_overcurrent() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=145),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="attack object UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))

    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 2200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ],
            "propulsion": {
                "rcs": {
                    "enabled": True,
                    "propellant_kg": 12.0,
                }
            },
            "power": {
                "load_shedding": True,
                "shed_reasons": ["pdu_overcurrent"],
                "pdu_throttled": False,
                "throttled_loads": [],
            },
        },
        agent=agent,
    )

    assert response.legality is not None
    assert response.legality.status == "blocked"
    assert response.legality.domain == "resource"
    assert response.legality.reason_code == "COMBAT_ENTRY_POWER_OVERCURRENT"
    assert response.reply is not None
    assert "PDU overcurrent" in response.reply.body.ru
    assert response.proposals == []
    assert response.trust_signals[-1].reason_code == "COMBAT_ENTRY_POWER_OVERCURRENT"


def test_build_hostile_attack_response_defers_when_thermal_warn_nodes_remain_after_burst() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=146),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="attack object UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))

    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 2200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ],
            "propulsion": {
                "rcs": {
                    "enabled": True,
                    "propellant_kg": 12.0,
                }
            },
            "thermal": {
                "nodes": [
                    {"id": "pdu", "temp_c": 85.01, "warned": True, "tripped": False, "warn_c": 85.0, "trip_c": 95.0}
                ]
            },
            "power": {
                "load_shedding": False,
                "shed_reasons": [],
                "pdu_throttled": False,
                "throttled_loads": [],
            },
        },
        agent=agent,
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.domain == "resource"
    assert response.legality.reason_code == "COMBAT_ENTRY_THERMAL_WARN"
    assert response.reply is not None
    assert "warned-узлах" in response.reply.body.ru
    assert response.proposals == []
    assert response.trust_signals[-1].reason_code == "COMBAT_ENTRY_THERMAL_WARN"


def test_build_hostile_attack_response_defers_when_combat_target_link_is_degraded() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=147),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="attack object UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))

    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 2200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ],
            "propulsion": {
                "rcs": {
                    "enabled": True,
                    "propellant_kg": 12.0,
                }
            },
            "power": {
                "load_shedding": False,
                "shed_reasons": [],
                "pdu_throttled": False,
                "throttled_loads": [],
            },
            "thermal": {
                "nodes": [
                    {"id": "pdu", "temp_c": 63.0, "warned": False, "tripped": False, "warn_c": 85.0, "trip_c": 95.0}
                ]
            },
            "comms": {
                "plane_enabled": True,
                "link_state": "degraded",
                "latency_ms": 910.0,
                "packet_loss_pct": 15.0,
                "antenna_status": "unlock",
                "data_rate_kbps": 0.0,
            },
        },
        agent=agent,
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.domain == "resource"
    assert response.legality.reason_code == "COMBAT_ENTRY_COMMS_LINK_DEGRADED"
    assert response.reply is not None
    assert "target-link" in response.reply.body.ru
    assert response.proposals == []
    assert response.trust_signals[-1].reason_code == "COMBAT_ENTRY_COMMS_LINK_DEGRADED"


def test_build_hostile_attack_response_defers_when_rcs_telemetry_is_missing() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=46),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="attack object UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))

    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 2200.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ]
        },
        agent=agent,
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.domain == "resource"
    assert response.legality.reason_code == "COMBAT_ENTRY_RCS_NO_DATA"


def test_build_observation_objective_event_accepts_live_unspecified_track_type() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=61),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="safe observation ALLY-3680E0", lang_hint="auto"),
    )
    response = _build_safe_observation_response(req=req, mode=QikiMode.FACTORY, world_snapshot={})

    event = _build_observation_objective_event(
        req=req,
        response=response,
        procedure_name="safe_pause_resume",
        observation_style="safe",
        world_snapshot={
            "radar_tracks": [
                {
                    "object_type": 0,
                    "track_id": "trk-live-1",
                    "transponder_id": "ALLY-3680E0",
                    "range_m": 3500.357,
                    "quality": 1.0,
                }
            ]
        },
    )

    assert event is not None
    assert event["target_designator"] == "ALLY-3680E0"
    assert event["track_visible"] is True
    assert event["track_id"] == "trk-live-1"
    assert event["track_label"] == "ALLY-3680E0"
    assert event["track_range_m"] == 3500.357
    assert event["track_quality"] == 1.0
    assert event["route_role"] == "official"


def test_build_observation_hidden_event_requires_deviation_route() -> None:
    assert _build_observation_hidden_event(
        objective_event={
            "objective_id": "observation-1",
            "proposal_id": "proposal-1",
            "request_id": "request-1",
            "procedure_name": "safe_pause_resume",
            "target_designator": "ALLY-3680E0",
            "route_role": "official",
        }
    ) is None


def test_build_observation_hidden_event_links_to_deviation_objective() -> None:
    event = _build_observation_hidden_event(
        objective_event={
            "objective_id": "observation-2",
            "proposal_id": "proposal-2",
            "request_id": "request-2",
            "procedure_name": "safe_pause_slow_resume",
            "target_designator": "ALLY-4D1ED5",
            "route_role": "deviation",
        }
    )

    assert event is not None
    assert event["event_type"] == "HIDDEN_EVENT_REVEALED"
    assert event["objective_id"] == "observation-2"
    assert event["proposal_id"] == "proposal-2"
    assert event["request_id"] == "request-2"
    assert event["procedure_name"] == "safe_pause_slow_resume"
    assert event["target_designator"] == "ALLY-4D1ED5"
    assert event["route_role"] == "deviation"
    assert event["reason_code"] == "DEVIATION_ROUTE_REVEALS_HIDDEN_OBSERVATION_EVENT"
    assert "ALLY-4D1ED5" in event["message"]


def test_build_observation_objective_event_embeds_review_required_follow_up_for_deviation() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=62),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="slow observation ALLY-4D1ED5", lang_hint="auto"),
    )
    response = _build_slow_observation_response(req=req, mode=QikiMode.FACTORY, world_snapshot={})

    event = _build_observation_objective_event(
        req=req,
        response=response,
        procedure_name="safe_pause_slow_resume",
        observation_style="slow",
        world_snapshot={},
    )

    assert event is not None
    assert event["route_role"] == "deviation"
    assert event["follow_up_status"] == "review_required"
    assert event["follow_up_reason_code"] == "HIDDEN_EVENT_REVIEW_REQUIRED"
    assert event["follow_up_event_type"] == "HIDDEN_EVENT_REVEALED"
    assert "hidden fact" in event["follow_up_allowed_when_en"].lower()


def test_observation_follow_up_update_moves_review_truth_upstream() -> None:
    update = _build_observation_follow_up_update(
        objective_event={
            "event_schema_version": 1,
            "source": "orion_v",
            "subject": "qiki.events.v1.operator.objectives",
            "timestamp": "2026-03-13T00:00:00+00:00",
            "ts_epoch": 1.0,
            "kind": "observation_objective_update",
            "objective_id": "observation-2",
            "objective_type": "observation",
            "status": "confirmed",
            "observation_style": "slow",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "request_id": "request-2",
            "proposal_id": "proposal-2",
            "target_designator": "ALLY-4D1ED5",
        },
        action_event={
            "event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
            "objective_id": "observation-2",
            "proposal_id": "proposal-2",
            "request_id": "request-2",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "target_designator": "ALLY-4D1ED5",
        },
    )

    assert update is not None
    assert update["source"] == "q_core_intents"
    assert update["kind"] == "observation_objective_update"
    assert update["reason_code"] == "OBJECTIVE_REVIEW_CLOSED"
    assert update["follow_up_status"] == "review_completed"
    assert update["follow_up_event_type"] == "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED"
    assert "post-review follow-up choice" in update["follow_up_allowed_when_en"].lower()


def test_observation_follow_up_contract_covers_hold_for_recheck_without_extra_framework() -> None:
    contract = _observation_follow_up_contract(
        follow_up_status="hold_for_recheck",
        route_role="deviation",
        procedure_name="safe_pause_slow_resume",
        target_designator="ALLY-4D1ED5",
    )

    assert contract is not None
    assert contract["reason_code"] == "HIDDEN_EVENT_RECHECK_HOLD_SELECTED"
    assert contract["event_type"] == "HIDDEN_EVENT_RECHECK_HOLD_SELECTED"
    assert "safe recheck" in contract["allowed_when_en"].lower()


def test_observation_follow_up_update_resumes_observation_after_hold() -> None:
    update = _build_observation_follow_up_update(
        objective_event={
            "event_schema_version": 1,
            "source": "q_core_intents",
            "subject": "qiki.events.v1.operator.objectives",
            "timestamp": "2026-03-13T00:00:00+00:00",
            "ts_epoch": 1.0,
            "kind": "observation_objective_update",
            "objective_id": "observation-2",
            "objective_type": "observation",
            "status": "confirmed",
            "observation_style": "slow",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "request_id": "request-2",
            "proposal_id": "proposal-2",
            "target_designator": "ALLY-4D1ED5",
            "follow_up_status": "hold_for_recheck",
        },
        action_event={
            "event_type": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
            "objective_id": "observation-2",
            "proposal_id": "proposal-2",
            "request_id": "request-2",
            "procedure_name": "safe_pause_slow_resume",
            "route_role": "deviation",
            "target_designator": "ALLY-4D1ED5",
        },
    )

    assert update is not None
    assert update["source"] == "q_core_intents"
    assert update["reason_code"] == "OBJECTIVE_RESUME_OBSERVATION_SELECTED"
    assert update["follow_up_status"] == "resume_observation"
    assert update["follow_up_event_type"] == "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED"
    assert "safe observation" in update["follow_up_allowed_when_en"].lower()


def test_find_resumable_observation_objective_prefers_same_target_resume_state(monkeypatch) -> None:
    monkeypatch.setattr(intents_service.time, "time", lambda: 10.0)
    resumable = _find_resumable_observation_objective(
        {
            "objective_id:other": {
                "objective_type": "observation",
                "follow_up_status": "review_completed",
                "target_designator": "ALLY-OTHER",
                "ts_epoch": 1.0,
            },
            "objective_id:older": {
                "objective_type": "observation",
                "follow_up_status": "resume_observation",
                "target_designator": "ALLY-4D1ED5",
                "ts_epoch": 2.0,
            },
            "objective_id:newer": {
                "objective_type": "observation",
                "follow_up_status": "resume_observation",
                "target_designator": "ALLY-4D1ED5",
                "ts_epoch": 3.0,
                "objective_id": "observation-2",
            },
        },
        target_designator="ALLY-4D1ED5",
    )

    assert resumable is not None
    assert resumable["objective_id"] == "observation-2"


def test_find_resumable_observation_objective_logs_qcore_and_public_identity(monkeypatch, caplog) -> None:
    monkeypatch.setattr(intents_service.time, "time", lambda: 10.0)
    caplog.set_level(logging.INFO, logger=intents_service.logger.name)

    resumable = _find_resumable_observation_objective(
        {
            "objective_id:older": {
                "objective_type": "observation",
                "follow_up_status": "resume_observation",
                "target_designator": "ALLY-4D1ED5",
                "ts_epoch": 2.0,
                "objective_id": "observation-1",
                "request_id": "request-1",
                "track_id": "qcore-track-1",
                "track_label": "ALLY-OLD",
                "public_track_id": "public-track-1",
                "public_track_label": "ALLY-OLD",
            },
            "objective_id:newer": {
                "objective_type": "observation",
                "follow_up_status": "resume_observation",
                "target_designator": "ALLY-4D1ED5",
                "ts_epoch": 3.0,
                "objective_id": "observation-2",
                "request_id": "request-2",
                "track_id": "qcore-track-2",
                "track_label": "ALLY-NEW",
                "public_track_id": "public-track-2",
                "public_track_label": "ALLY-NEW",
            },
        },
        target_designator="ALLY-4D1ED5",
    )

    assert resumable is not None
    assert resumable["objective_id"] == "observation-2"
    record = next(record for record in caplog.records if record.msg.startswith("Resume objective lookup:"))
    message = record.getMessage()
    assert "target=ALLY-4D1ED5" in message
    assert "matched=2" in message
    assert "stale_skipped=0" in message
    assert "objective_id=observation-2" in message
    assert "request_id=request-2" in message
    assert "qcore_track_id=qcore-track-2" in message
    assert "qcore_label=ALLY-NEW" in message
    assert "public_track_id=public-track-2" in message
    assert "public_label=ALLY-NEW" in message


def test_find_resumable_observation_objective_ignores_stale_resume_state(monkeypatch) -> None:
    monkeypatch.setattr(intents_service.time, "time", lambda: 200.0)

    resumable = _find_resumable_observation_objective(
        {
            "objective_id:stale": {
                "objective_type": "observation",
                "follow_up_status": "resume_observation",
                "target_designator": "ALLY-4D1ED5",
                "ts_epoch": 50.0,
                "objective_id": "observation-stale",
            },
            "objective_id:fresh": {
                "objective_type": "observation",
                "follow_up_status": "resume_observation",
                "target_designator": "ALLY-4D1ED5",
                "ts_epoch": 160.0,
                "objective_id": "observation-fresh",
            },
        },
        target_designator="ALLY-4D1ED5",
    )

    assert resumable is not None
    assert resumable["objective_id"] == "observation-fresh"


def test_find_resumable_observation_objective_returns_none_when_only_stale_resume_exists(
    monkeypatch, caplog
) -> None:
    monkeypatch.setattr(intents_service.time, "time", lambda: 200.0)
    caplog.set_level(logging.INFO, logger=intents_service.logger.name)

    resumable = _find_resumable_observation_objective(
        {
            "objective_id:stale": {
                "objective_type": "observation",
                "follow_up_status": "resume_observation",
                "target_designator": "ALLY-4D1ED5",
                "ts_epoch": 50.0,
                "objective_id": "observation-stale",
            }
        },
        target_designator="ALLY-4D1ED5",
    )

    assert resumable is None
    record = next(record for record in caplog.records if record.msg.startswith("Resume objective lookup:"))
    assert "matched=0" in record.getMessage()
    assert "stale_skipped=1" in record.getMessage()


def test_build_safe_observation_response_reuses_resumable_track_identity_for_signature_change() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=48),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="safe observation ALLY-4D1ED5", lang_hint="auto"),
    )

    response = _build_safe_observation_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0},
            "radar_tracks": [
                {
                    "track_id": "track-42",
                    "transponder_id": "SPOOF-42",
                    "range_m": 2800.0,
                    "quality": 0.91,
                    "object_type": 2,
                }
            ],
        },
        resumable_objective={
            "objective_type": "observation",
            "follow_up_status": "resume_observation",
            "track_id": "track-42",
            "track_label": "ALLY-4D1ED5",
            "target_designator": "ALLY-4D1ED5",
        },
    )

    action = response.proposals[0].proposed_actions[0]

    assert action.name == "safe_pause_resume"
    assert action.parameters["observation_track_id"] == "track-42"
    assert action.parameters["observation_track_label"] == "SPOOF-42"
    assert action.parameters["observation_track_range_m"] == 2800.0


def test_find_target_track_matches_visible_signature_not_runtime_identity() -> None:
    track = _find_target_track(
        {
            "radar_tracks": [
                {
                    "track_id": "track-42",
                    "object_identity": "track-42",
                    "visible_signature": "SPOOF-42",
                    "transponder_id": "SPOOF-42",
                    "range_m": 2800.0,
                    "quality": 0.91,
                    "object_type": 2,
                }
            ]
        },
        "track-42",
    )

    assert track is None


def test_select_target_track_for_resume_prefers_runtime_track_id_over_mutated_label() -> None:
    track, source = _select_target_track_for_resume(
        {
            "radar_tracks": [
                {
                    "track_id": "track-42",
                    "transponder_id": "SPOOF-42",
                    "range_m": 2800.0,
                    "quality": 0.91,
                    "object_type": 2,
                }
            ]
        },
        target_designator="ALLY-4D1ED5",
        preferred_track_id="track-42",
    )

    assert track is not None
    assert track["track_id"] == "track-42"
    assert track["transponder_id"] == "SPOOF-42"
    assert source == "direct_contour_match"


def test_select_target_track_for_resume_does_not_fallback_when_contour_identity_exists() -> None:
    track, source = _select_target_track_for_resume(
        {
            "radar_tracks": [
                {
                    "track_id": "track-99",
                    "transponder_id": "ALLY-4D1ED5",
                    "range_m": 2800.0,
                    "quality": 0.91,
                    "object_type": 2,
                }
            ]
        },
        target_designator="ALLY-4D1ED5",
        preferred_track_id="track-42",
        allow_designator_fallback=False,
    )

    assert track is None
    assert source == "contour_miss"


def test_select_target_track_for_resume_uses_designator_only_when_contour_identity_missing() -> None:
    track, source = _select_target_track_for_resume(
        {
            "radar_tracks": [
                {
                    "track_id": "track-99",
                    "transponder_id": "ALLY-4D1ED5",
                    "range_m": 2800.0,
                    "quality": 0.91,
                    "object_type": 2,
                }
            ]
        },
        target_designator="ALLY-4D1ED5",
        preferred_track_id=None,
    )

    assert track is not None
    assert track["track_id"] == "track-99"
    assert source == "fallback_by_designator"


def test_select_target_track_for_resume_uses_public_track_id_before_designator_fallback() -> None:
    track, source = _select_target_track_for_resume(
        {
            "radar_tracks": [
                {
                    "track_id": "public-track-77",
                    "object_identity": "public-track-77",
                    "transponder_id": "ALLY-4D1ED5",
                    "range_m": 3200.0,
                    "quality": 0.98,
                    "object_type": 2,
                }
            ]
        },
        target_designator="ALLY-4D1ED5",
        preferred_track_id="qcore-track-missing",
        preferred_public_track_id="public-track-77",
        allow_designator_fallback=False,
    )

    assert track is not None
    assert track["track_id"] == "public-track-77"
    assert source == "public_contour_match"


def test_select_target_track_for_resume_allows_designator_fallback_when_public_binding_exists() -> None:
    track, source = _select_target_track_for_resume(
        {
            "radar_tracks": [
                {
                    "track_id": "qcore-track-42",
                    "object_identity": "qcore-track-42",
                    "transponder_id": "ALLY-4D1ED5",
                    "range_m": 2800.0,
                    "quality": 0.91,
                    "object_type": 2,
                }
            ]
        },
        target_designator="ALLY-4D1ED5",
        preferred_track_id="stale-qcore-track",
        preferred_public_track_id="stale-public-track",
        allow_designator_fallback=True,
    )

    assert track is not None
    assert track["track_id"] == "qcore-track-42"
    assert source == "fallback_by_designator"


def test_build_safe_observation_response_keeps_contour_snapshot_when_live_match_is_missing() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=49),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="safe observation ALLY-4D1ED5", lang_hint="auto"),
    )

    response = _build_safe_observation_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0},
            "radar_tracks": [
                {
                    "track_id": "track-99",
                    "transponder_id": "ALLY-4D1ED5",
                    "range_m": 1500.0,
                    "quality": 0.88,
                    "object_type": 2,
                }
            ],
        },
        resumable_objective={
            "objective_type": "observation",
            "follow_up_status": "resume_observation",
            "track_id": "track-42",
            "track_label": "ALLY-4D1ED5",
            "track_range_m": 3200.0,
            "track_quality": 0.98,
            "target_designator": "ALLY-4D1ED5",
        },
    )

    action = response.proposals[0].proposed_actions[0]

    assert action.name == "safe_pause_resume"
    assert action.parameters["observation_track_id"] == "track-42"
    assert action.parameters["observation_track_label"] == "ALLY-4D1ED5"
    assert action.parameters["observation_track_range_m"] == 3200.0
    assert action.parameters["observation_track_quality"] == 0.98


def test_build_observation_objective_event_splits_identity_from_visible_signature() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=50),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="safe observation SPOOF-42", lang_hint="auto"),
    )

    response = _build_safe_observation_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0},
            "radar_tracks": [
                {
                    "track_id": "track-42",
                    "object_identity": "track-42",
                    "visible_signature": "SPOOF-42",
                    "transponder_id": "SPOOF-42",
                    "range_m": 2800.0,
                    "quality": 0.91,
                    "object_type": 2,
                }
            ],
        },
    )

    event = _build_observation_objective_event(
        req=req,
        response=response,
        procedure_name="safe_pause_resume",
        observation_style="safe",
        world_snapshot={
            "radar_tracks": [
                {
                    "track_id": "track-42",
                    "object_identity": "track-42",
                    "visible_signature": "SPOOF-42",
                    "transponder_id": "SPOOF-42",
                    "range_m": 2800.0,
                    "quality": 0.91,
                    "object_type": 2,
                }
            ]
        },
    )

    assert event is not None
    assert event["object_identity"] == "track-42"
    assert event["track_id"] == "track-42"
    assert event["visible_signature"] == "SPOOF-42"
    assert event["track_label"] == "SPOOF-42"


def test_refresh_agent_snapshot_until_target_track_waits_for_fresh_radar(monkeypatch) -> None:
    agent = SimpleNamespace(
        context=SimpleNamespace(
            latest_sensor_data=SensorData(
                sensor_id="radar-old",
                sensor_type=SensorTypeEnum.RADAR,
                string_data="stale-radar",
            ),
            world_snapshot={
                "radar_tracks": [
                    {
                        "track_id": "track-42",
                        "transponder_id": "ALLY-42",
                        "object_type": 2,
                        "range_m": 2800.0,
                        "quality": 0.91,
                    }
                ]
            },
        )
    )
    updates = [
        (
            SensorData(sensor_id="imu-1", sensor_type=SensorTypeEnum.IMU, vector_data=[0.0, 0.0, 0.0]),
            {
                "radar_tracks": [
                    {
                        "track_id": "track-42",
                        "transponder_id": "ALLY-42",
                        "object_type": 2,
                        "range_m": 2800.0,
                        "quality": 0.91,
                    }
                ]
            },
        ),
        (
            SensorData(
                sensor_id="radar-new",
                sensor_type=SensorTypeEnum.RADAR,
                string_data="fresh-radar",
            ),
            {
                "radar_tracks": [
                    {
                        "track_id": "track-42",
                        "transponder_id": "ALLY-42",
                        "object_type": 2,
                        "range_m": 2800.0,
                        "quality": 0.91,
                    }
                ]
            },
        ),
        (
            SensorData(
                sensor_id="radar-new-2",
                sensor_type=SensorTypeEnum.RADAR,
                string_data="fresh-radar-2",
            ),
            {
                "radar_tracks": [
                    {
                        "track_id": "track-42",
                        "transponder_id": "SPOOF-42",
                        "object_type": 2,
                        "range_m": 2800.0,
                        "quality": 0.91,
                    }
                ]
            },
        ),
    ]

    def _refresh(*, agent, data_provider) -> None:
        sensor_data, snapshot = updates.pop(0)
        agent.context.latest_sensor_data = sensor_data
        agent.context.world_snapshot = snapshot

    monkeypatch.setattr(intents_service, "_refresh_agent_snapshot", _refresh)

    asyncio.run(
        _refresh_agent_snapshot_until_target_track(
            agent=agent,
            data_provider=SimpleNamespace(),
            target_designator="ALLY-42",
            preferred_track_id="track-42",
            previous_track_label="ALLY-42",
            require_fresh_radar=True,
            timeout_s=0.5,
            step_s=0.0,
            label_settle_s=10.0,
        )
    )

    assert updates == []
    track = agent.context.world_snapshot["radar_tracks"][0]
    assert track["track_id"] == "track-42"
    assert track["transponder_id"] == "SPOOF-42"


def test_build_hostile_attack_response_shifts_after_active_intercept_pulse() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=47),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="attack object UNBT9999", lang_hint="auto"),
    )
    agent = SimpleNamespace(context=SimpleNamespace(qiki_repeat_state={}))

    response = _build_hostile_attack_block_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {
                    "object_type": 2,
                    "range_m": 1800.0,
                    "quality": 0.95,
                    "age_s": 0.1,
                    "transponder_id": "UNBT9999",
                    "iff": 2,
                }
            ],
            "propulsion": {
                "rcs": {
                    "enabled": True,
                    "active": True,
                    "command_pct": 35.0,
                    "time_left_s": 1.2,
                    "propellant_kg": 11.5,
                }
            },
        },
        agent=agent,
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.domain == "protocol"
    assert response.legality.reason_code == "TACTICAL_STATE_INTERCEPT_ACTIVE"
    assert response.reply is not None
    assert "перехват" in response.reply.body.ru.lower()
    assert response.proposals == []
    assert response.trust_signals[-1].reason_code == "TACTICAL_STATE_INTERCEPT_ACTIVE"


def test_build_safe_observation_response_prepares_orion_procedure() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=13),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="safe observation", lang_hint="auto"),
    )

    response = _build_safe_observation_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}},
    )

    assert response.legality is not None
    assert response.legality.status == "allowed"
    assert response.legality.reason_code == "SAFE_OBSERVATION_PROCEDURE_READY"
    assert response.consequence is not None
    assert response.consequence.status == "pending"
    assert response.proposals
    action = response.proposals[0].proposed_actions[0]
    assert action.kind == "ORION_PROCEDURE"
    assert action.subject == "orionv.procedure"
    assert action.name == "safe_pause_resume"
    assert action.dry_run is False


def test_build_slow_observation_response_prepares_orion_procedure() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=31),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="slow observation", lang_hint="auto"),
    )

    response = _build_slow_observation_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}},
    )

    assert response.legality is not None
    assert response.legality.status == "allowed"
    assert response.legality.reason_code == "SLOW_OBSERVATION_PROCEDURE_READY"
    assert response.consequence is not None
    assert response.consequence.status == "pending"
    assert response.proposals
    action = response.proposals[0].proposed_actions[0]
    assert action.kind == "ORION_PROCEDURE"
    assert action.subject == "orionv.procedure"
    assert action.name == "safe_pause_slow_resume"
    assert action.dry_run is False


def test_build_station_approach_response_marks_low_quality_track_as_degraded() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=6),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="approach station", lang_hint="auto"),
    )

    response = _build_station_approach_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {"object_type": 3, "range_m": 1200.0, "quality": 0.32, "age_s": 0.4},
            ]
        },
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.reason_code == "STATION_TRACK_LOW_QUALITY"
    assert response.trust_signals[0].state == "degraded"
    assert response.trust_signals[0].confidence == 0.32
    assert "качество" in response.legality.reason.ru.lower()


def test_build_station_approach_response_marks_healthy_track_as_allowed() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=7),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="approach station", lang_hint="auto"),
    )

    response = _build_station_approach_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [
                {"object_type": 3, "range_m": 820.0, "quality": 0.91, "age_s": 0.3},
                {"object_type": 2, "range_m": 200.0, "quality": 0.99, "age_s": 0.1},
            ]
        },
    )

    assert response.legality is not None
    assert response.legality.status == "allowed"
    assert response.legality.reason_code == "STATION_TRACK_TRUSTED"
    assert response.trust_signals[0].state == "healthy"
    assert response.trust_signals[0].confidence == 0.91
    assert response.consequence is not None
    assert response.consequence.status == "confirmed"
    assert response.consequence.telemetry_confirmation is not None
    assert "820" in response.consequence.telemetry_confirmation.ru


def test_build_station_hail_response_blocks_offline_link_as_resource_issue() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=11),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="hail station", lang_hint="auto"),
    )

    response = _build_station_hail_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [{"object_type": 3, "range_m": 900.0, "quality": 0.88, "age_s": 0.2}],
            "comms": {
                "plane_enabled": True,
                "link_state": "offline",
                "data_rate_kbps": 0.0,
                "antenna_status": "unlock",
            },
        },
    )

    assert response.legality is not None
    assert response.legality.status == "blocked"
    assert response.legality.domain == "resource"
    assert response.legality.reason_code == "COMMS_LINK_OFFLINE"
    assert response.trust_signals[0].state == "off"
    assert response.trust_signals[0].source == "derived"
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"


def test_build_station_hail_response_defers_stale_comms_telemetry() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=111),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="hail station", lang_hint="auto"),
    )

    response = _build_station_hail_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "ts_unix_ms": 1,
            "radar_tracks": [{"object_type": 3, "range_m": 900.0, "quality": 0.88, "age_s": 0.2}],
            "comms": {
                "plane_enabled": True,
                "link_state": "online",
                "data_rate_kbps": 128.0,
                "antenna_status": "lock",
            },
        },
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.domain == "trust"
    assert response.legality.reason_code == "COMMS_STATE_STALE"
    assert response.trust_signals[0].state == "degraded"
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"


def test_build_station_hail_response_confirms_online_link_readiness() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=12),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="contact station", lang_hint="auto"),
    )

    response = _build_station_hail_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "radar_tracks": [{"object_type": 3, "range_m": 640.0, "quality": 0.93, "age_s": 0.2}],
            "comms": {
                "plane_enabled": True,
                "link_state": "online",
                "data_rate_kbps": 192.0,
                "latency_ms": 82.0,
                "antenna_status": "lock",
            },
        },
    )

    assert response.legality is not None
    assert response.legality.status == "allowed"
    assert response.legality.domain == "resource"
    assert response.legality.reason_code == "COMMS_CHANNEL_READY"
    assert len(response.trust_signals) == 2
    assert response.trust_signals[0].state == "healthy"
    assert response.consequence is not None
    assert response.consequence.status == "confirmed"
    assert response.consequence.telemetry_confirmation is not None
    assert "192" in response.consequence.telemetry_confirmation.ru


def test_build_attitude_stabilize_response_defers_stale_imu_telemetry() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=112),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="stabilize attitude", lang_hint="auto"),
    )

    response = _build_attitude_stabilize_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "ts_unix_ms": 1,
            "sensor_plane": {
                "imu": {
                    "enabled": True,
                    "status": "ok",
                    "reason": "telemetry_ok",
                    "ok": True,
                    "roll_rate_rps": 0.01,
                    "pitch_rate_rps": 0.02,
                    "yaw_rate_rps": 0.03,
                }
            },
            "attitude": {"roll_rad": 0.1, "pitch_rad": 0.2, "yaw_rad": 0.3},
        },
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.domain == "trust"
    assert response.legality.reason_code == "IMU_STATE_STALE"
    assert response.trust_signals[0].state == "degraded"
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"


def test_update_sensor_snapshot_records_imu_timestamp_metadata() -> None:
    snapshot = update_sensor_snapshot(
        {},
        SensorData(
            sensor_id="imu-42",
            sensor_type=SensorTypeEnum.IMU,
            vector_data=[1.0, 2.0, 3.0],
            timestamp=datetime(2026, 3, 29, 12, 34, 56, tzinfo=UTC),
        ),
    )

    assert snapshot["timestamp"] == "2026-03-29T12:34:56Z"
    assert snapshot["ts_epoch"] > 0
    assert snapshot["ts_unix_ms"] == 1774787696000
    assert snapshot["sensor_plane"]["last_seen_ts"] == "2026-03-29T12:34:56Z"
    assert "age_s" not in snapshot["sensor_plane"]


def test_run_orion_intents_loop_station_hail_changes_after_fresh_telemetry(monkeypatch) -> None:
    class _FakeMsg:
        def __init__(self, payload: dict[str, object]) -> None:
            self.data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.reply = ""

    class _FakeNatsClient:
        def __init__(self) -> None:
            self.callbacks: dict[str, object] = {}
            self.published: list[tuple[str, dict[str, object]]] = []
            self.ready = asyncio.Event()

        async def subscribe(self, subject: str, cb):
            self.callbacks[subject] = cb
            if subject == QIKI_INTENTS:
                self.ready.set()
            return SimpleNamespace()

        async def publish(self, subject: str, data: bytes, headers=None) -> None:
            del headers
            self.published.append((subject, json.loads(data.decode("utf-8"))))

    async def _exercise() -> None:
        fake_nc = _FakeNatsClient()

        async def _fake_connect(*args, **kwargs):
            del args, kwargs
            return fake_nc

        monkeypatch.setitem(sys.modules, "nats", types.SimpleNamespace(connect=_fake_connect))
        monkeypatch.setattr(intents_service, "_refresh_agent_snapshot", lambda *args, **kwargs: None)

        agent = SimpleNamespace(
            context=SimpleNamespace(
                world_snapshot={
                    "radar_tracks": [{"object_type": 3, "range_m": 640.0, "quality": 0.93, "age_s": 0.2}],
                },
                sensor_snapshot={},
                proposals=[],
                qiki_repeat_state={},
            )
        )
        loop_task = asyncio.create_task(
            _run_orion_intents_loop(agent=agent, data_provider=SimpleNamespace())
        )

        try:
            await asyncio.wait_for(fake_nc.ready.wait(), timeout=1.0)

            stale_telemetry = {
                "ts_unix_ms": 1,
                "comms": {
                    "plane_enabled": True,
                    "link_state": "online",
                    "data_rate_kbps": 192.0,
                    "latency_ms": 82.0,
                    "antenna_status": "lock",
                },
            }
            fresh_telemetry = {
                "ts_unix_ms": int(time.time() * 1000),
                "comms": {
                    "plane_enabled": True,
                    "link_state": "online",
                    "data_rate_kbps": 192.0,
                    "latency_ms": 82.0,
                    "antenna_status": "lock",
                },
            }
            stale_req = QikiChatRequestV1(
                request_id=UUID(int=201),
                ts_epoch_ms=1,
                mode_hint=QikiMode.FACTORY,
                input=QikiChatInput(text="hail station", lang_hint="auto"),
            )
            fresh_req = QikiChatRequestV1(
                request_id=UUID(int=202),
                ts_epoch_ms=1,
                mode_hint=QikiMode.FACTORY,
                input=QikiChatInput(text="hail station", lang_hint="auto"),
            )

            await fake_nc.callbacks[SYSTEM_TELEMETRY](_FakeMsg(stale_telemetry))
            await fake_nc.callbacks[QIKI_INTENTS](SimpleNamespace(data=stale_req.model_dump_json().encode("utf-8")))
            stale_resp = fake_nc.published[-1][1]

            await fake_nc.callbacks[SYSTEM_TELEMETRY](_FakeMsg(fresh_telemetry))
            await fake_nc.callbacks[QIKI_INTENTS](SimpleNamespace(data=fresh_req.model_dump_json().encode("utf-8")))
            fresh_resp = fake_nc.published[-1][1]

            assert fake_nc.published[-2][0] == QIKI_RESPONSES
            assert stale_resp["legality"]["reason_code"] == "COMMS_STATE_STALE"
            assert fresh_resp["legality"]["reason_code"] == "COMMS_CHANNEL_READY"
        finally:
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

    asyncio.run(_exercise())


def test_build_docking_corridor_response_blocks_when_station_is_too_far() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=13),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="docking corridor", lang_hint="auto"),
    )

    response = _build_docking_corridor_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={"radar_tracks": [{"object_type": 3, "range_m": 6400.0, "quality": 0.92, "age_s": 0.2}]},
    )

    assert response.legality is not None
    assert response.legality.status == "blocked"
    assert response.legality.domain == "zone"
    assert response.legality.reason_code == "DOCKING_ZONE_TOO_FAR"
    assert response.trust_signals[0].state == "healthy"
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"


def test_build_docking_corridor_response_confirms_when_inside_zone() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=14),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="enter docking corridor", lang_hint="auto"),
    )

    response = _build_docking_corridor_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={"radar_tracks": [{"object_type": 3, "range_m": 3200.0, "quality": 0.94, "age_s": 0.2}]},
    )

    assert response.legality is not None
    assert response.legality.status == "allowed"
    assert response.legality.domain == "zone"
    assert response.legality.reason_code == "DOCKING_ZONE_READY"
    assert response.consequence is not None
    assert response.consequence.status == "confirmed"
    assert response.consequence.telemetry_confirmation is not None
    assert "3200" in response.consequence.telemetry_confirmation.ru


def test_build_attitude_stabilize_response_marks_imu_offline_as_off() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=15),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="stabilize attitude", lang_hint="auto"),
    )

    response = _build_attitude_stabilize_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "sensor_plane": {"imu": {"enabled": False, "status": "na", "reason": "disabled", "ok": None}},
            "attitude": {"roll_rad": 0.0, "pitch_rad": 0.0, "yaw_rad": 0.2},
        },
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.domain == "trust"
    assert response.legality.reason_code == "IMU_OFFLINE"
    assert response.trust_signals[0].state == "off"
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"


def test_build_attitude_stabilize_response_blocks_failed_imu() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=16),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="attitude hold", lang_hint="auto"),
    )

    response = _build_attitude_stabilize_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "sensor_plane": {"imu": {"enabled": True, "status": "crit", "reason": "not ok", "ok": False}},
            "attitude": {"roll_rad": 0.1, "pitch_rad": 0.0, "yaw_rad": 0.2},
        },
    )

    assert response.legality is not None
    assert response.legality.status == "blocked"
    assert response.legality.domain == "trust"
    assert response.legality.reason_code == "IMU_FAILED"
    assert response.trust_signals[0].state == "failed"
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"


def test_build_attitude_stabilize_response_confirms_healthy_imu() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=17),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="stabilize orientation", lang_hint="auto"),
    )

    response = _build_attitude_stabilize_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "sensor_plane": {
                "imu": {
                    "enabled": True,
                    "status": "ok",
                    "reason": "ok",
                    "ok": True,
                    "roll_rate_rps": 0.01,
                    "pitch_rate_rps": 0.02,
                    "yaw_rate_rps": 0.03,
                }
            },
            "attitude": {"roll_rad": 0.1, "pitch_rad": 0.0, "yaw_rad": 0.2},
        },
    )

    assert response.legality is not None
    assert response.legality.status == "allowed"
    assert response.legality.reason_code == "IMU_HEALTHY"
    assert response.trust_signals[0].state == "healthy"
    assert response.consequence is not None
    assert response.consequence.status == "confirmed"
    assert response.consequence.telemetry_confirmation is not None
    assert "0.030" in response.consequence.telemetry_confirmation.ru


def test_build_attitude_stabilize_response_uses_sensor_snapshot_when_world_snapshot_is_empty() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=18),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="stabilize orientation", lang_hint="auto"),
    )

    response = _build_attitude_stabilize_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={},
        sensor_snapshot={
            "sensor_plane": {
                "imu": {
                    "enabled": True,
                    "status": "ok",
                    "reason": "grpc_imu_vector",
                    "ok": True,
                    "roll_rate_rps": None,
                    "pitch_rate_rps": None,
                    "yaw_rate_rps": None,
                }
            },
            "attitude": {"roll_rad": 0.1, "pitch_rad": 0.0, "yaw_rad": 0.2},
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    )

    assert response.legality is not None
    assert response.legality.status == "allowed"
    assert response.legality.reason_code == "IMU_HEALTHY"
    assert response.trust_signals[0].state == "healthy"


def test_build_attitude_stabilize_response_defers_stale_raw_sensor_snapshot() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=113),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="stabilize orientation", lang_hint="auto"),
    )

    response = _build_attitude_stabilize_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={},
        sensor_snapshot={
            "sensor_plane": {
                "imu": {
                    "enabled": True,
                    "status": "ok",
                    "reason": "grpc_imu_vector",
                    "ok": True,
                }
            },
            "attitude": {"roll_rad": 0.1, "pitch_rad": 0.0, "yaw_rad": 0.2},
            "timestamp": "1970-01-01T00:00:00Z",
            "ts_unix_ms": 1,
        },
    )

    assert response.legality is not None
    assert response.legality.status == "deferred"
    assert response.legality.reason_code == "IMU_STATE_STALE"


def test_build_attitude_stabilize_response_keeps_world_attitude_when_sensor_snapshot_is_partial() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=114),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="stabilize orientation", lang_hint="auto"),
    )

    response = _build_attitude_stabilize_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={
            "sensor_plane": {
                "imu": {
                    "enabled": True,
                    "status": "ok",
                    "reason": "telemetry_ok",
                    "ok": True,
                }
            },
            "attitude": {"roll_rad": 0.3, "pitch_rad": 0.4, "yaw_rad": 0.5},
        },
        sensor_snapshot={
            "sensor_plane": {
                "imu": {
                    "enabled": True,
                    "status": "ok",
                    "reason": "grpc_imu_vector",
                    "ok": True,
                }
            },
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    )

    assert response.legality is not None
    assert response.legality.reason_code == "IMU_HEALTHY"
    assert "roll=0.300" in response.legality.reason.en


def test_build_release_dock_response_returns_pending_action_for_docked_state() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=9),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="release dock", lang_hint="auto"),
    )

    response = _build_release_dock_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={"docking": {"enabled": True, "state": "docked", "connected": True, "port": "A"}},
    )

    assert response.legality is not None
    assert response.legality.status == "allowed"
    assert response.legality.reason_code == "DOCK_RELEASE_READY"
    assert response.consequence is not None
    assert response.consequence.status == "pending"
    assert response.proposals
    action = response.proposals[0].proposed_actions[0]
    assert action.subject == "qiki.commands.control"
    assert action.name == "sim.dock.release"
    assert action.dry_run is False


def test_build_release_dock_response_blocks_when_already_undocked() -> None:
    req = QikiChatRequestV1(
        request_id=UUID(int=10),
        ts_epoch_ms=1,
        mode_hint=QikiMode.FACTORY,
        input=QikiChatInput(text="undock", lang_hint="auto"),
    )

    response = _build_release_dock_response(
        req=req,
        mode=QikiMode.FACTORY,
        world_snapshot={"docking": {"enabled": True, "state": "undocked", "connected": False, "port": "A"}},
    )

    assert response.legality is not None
    assert response.legality.status == "blocked"
    assert response.legality.domain == "physics"
    assert response.legality.reason_code == "DOCK_ALREADY_RELEASED"
    assert response.consequence is not None
    assert response.consequence.status == "not_sent"
