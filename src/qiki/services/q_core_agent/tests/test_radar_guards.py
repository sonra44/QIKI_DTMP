from __future__ import annotations

from uuid import uuid4

import pytest

import qiki.services.q_core_agent.core.world_model as world_model_module

from qiki.services.q_core_agent.core.agent import AgentContext
from qiki.services.q_core_agent.core.fsm_handler import FSMHandler
from qiki.services.q_core_agent.core.guard_table import (
    GuardEvaluationResult,
    GuardRule,
    GuardTable,
    load_guard_table,
)
from qiki.services.q_core_agent.core.rule_engine import RuleEngine
from qiki.services.q_core_agent.core.world_model import WorldModel
from generated.bios_status_pb2 import BiosStatusReport
from generated.fsm_state_pb2 import FsmStateSnapshot, FSMStateEnum
from qiki.shared.models.core import ProposalTypeEnum, SensorData, SensorTypeEnum
from qiki.shared.models.radar import (
    FriendFoeEnum,
    RadarTrackModel,
    RadarTrackStatusEnum,
    TransponderModeEnum,
)


def _build_track(**overrides) -> RadarTrackModel:
    base = dict(
        track_id=uuid4(),
        range_m=50.0,
        bearing_deg=0.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=20.0,
        rcs_dbsm=1.0,
        quality=0.6,
        status=RadarTrackStatusEnum.TRACKED,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
        iff=FriendFoeEnum.UNKNOWN,
    )
    base.update(overrides)
    return RadarTrackModel(**base)


def _default_guard_table() -> GuardTable:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CLOSE",
            "description": "Unknown contact within 70m.",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "iff": FriendFoeEnum.UNKNOWN,
            "max_range_m": 70.0,
            "min_quality": 0.1,
        }
    )
    return GuardTable(schema_version=1, rules=[rule])


def _warning_guard_table() -> GuardTable:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_WARNING",
            "description": "Unknown contact within 150m.",
            "severity": "warning",
            "fsm_event": "RADAR_WARNING_UNKNOWN_PROXIMITY",
            "iff": FriendFoeEnum.UNKNOWN,
            "max_range_m": 150.0,
            "min_quality": 0.1,
        }
    )
    return GuardTable(schema_version=1, rules=[rule])


def test_guard_table_triggers_on_unknown_contact():
    guard_table = _default_guard_table()
    track = _build_track(range_m=45.0)

    results = guard_table.evaluate_track(track)

    assert len(results) == 1
    assert results[0].severity == "critical"
    assert results[0].fsm_event == "RADAR_ALERT_UNKNOWN_CLOSE"


def test_world_model_records_guard_event():
    guard_table = _default_guard_table()
    world_model = WorldModel(guard_table)
    track = _build_track(range_m=30.0)
    sensor_data = SensorData(
        sensor_id="radar_primary",
        sensor_type=SensorTypeEnum.RADAR,
        radar_track=track,
    )

    world_model.ingest_sensor_data(sensor_data)

    guard_results = world_model.guard_results()
    assert guard_results
    assert guard_results[0].rule_id == "UNKNOWN_CLOSE"


def test_world_model_snapshot_contains_counts():
    guard_table = _default_guard_table()
    world_model = WorldModel(guard_table)
    track = _build_track(range_m=30.0)
    sensor_data = SensorData(
        sensor_id="radar_primary",
        sensor_type=SensorTypeEnum.RADAR,
        radar_track=track,
    )

    world_model.ingest_sensor_data(sensor_data)

    snapshot = world_model.snapshot()
    assert snapshot["active_track_count"] == 1
    assert snapshot["critical_guard_count"] == 1
    assert snapshot["warning_guard_count"] == 0


def test_world_model_deduplicates_guard_results(monkeypatch):
    guard_table = _default_guard_table()
    world_model = WorldModel(guard_table)
    metrics_calls = []

    monkeypatch.setattr(
        world_model_module,
        "publish_world_model_metrics",
        lambda active_tracks, guard_results, new_warning_events: metrics_calls.append(
            (active_tracks, len(guard_results), new_warning_events)
        ),
    )

    track = _build_track(range_m=30.0)
    result = guard_table.evaluate_track(track)[0]

    monkeypatch.setattr(
        GuardTable,
        "evaluate_tracks",
        lambda self, *_args, **_kwargs: [result, result],
    )

    world_model._radar_tracks[str(track.track_id)] = track
    world_model._recalculate_guards()

    assert len(world_model.guard_results()) == 1
    assert metrics_calls[-1] == (1, 1, 0)


def test_world_model_warning_metrics_increment_once(monkeypatch):
    guard_table = _warning_guard_table()
    world_model = WorldModel(guard_table)
    calls = []

    monkeypatch.setattr(
        world_model_module,
        "publish_world_model_metrics",
        lambda active_tracks, guard_results, new_warning_events: calls.append(
            (active_tracks, len(list(guard_results)), new_warning_events)
        ),
    )

    track = _build_track(range_m=120.0)
    warning_sensor_data = SensorData(
        sensor_id="radar_primary",
        sensor_type=SensorTypeEnum.RADAR,
        radar_track=track,
    )

    world_model.ingest_sensor_data(warning_sensor_data)
    assert calls
    assert calls[-1][2] == 1

    world_model.ingest_sensor_data(warning_sensor_data)
    assert calls[-1][2] == 0


def test_rule_engine_generates_proposal_for_guard_event():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=True)
    guard_event = GuardEvaluationResult(
        rule_id="UNKNOWN_CLOSE",
        severity="critical",
        fsm_event="RADAR_ALERT_UNKNOWN_CLOSE",
        message="Unknown contact within 70m.",
        track_id="track-1",
        range_m=45.0,
        quality=0.8,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
    )
    context.guard_events = [guard_event]

    engine = RuleEngine(context, config={})

    proposals = engine.generate_proposals(context)

    assert proposals
    assert proposals[0].type == ProposalTypeEnum.SAFETY


def test_spoof_guard_creates_diagnostic_proposal():
    guard_table = load_guard_table()
    world_model = WorldModel(guard_table)
    context = AgentContext(bios_status=BiosStatusReport(all_systems_go=True))

    spoof_track = _build_track(
        range_m=120.0,
        transponder_on=True,
        transponder_mode=TransponderModeEnum.SPOOF,
        quality=0.9,
    )
    sensor_data = SensorData(
        sensor_id="radar_primary",
        sensor_type=SensorTypeEnum.RADAR,
        radar_track=spoof_track,
    )

    world_model.ingest_sensor_data(sensor_data)

    guard_results = world_model.guard_results()
    assert any(result.rule_id == "SPOOFING_DETECTED" for result in guard_results)

    context.guard_events = guard_results
    engine = RuleEngine(context, config={})

    proposals = engine.generate_proposals(context)
    assert proposals
    diagnostic = proposals[0]
    assert diagnostic.type == ProposalTypeEnum.DIAGNOSTICS
    assert "SPOOFING_DETECTED" in diagnostic.justification


@pytest.mark.asyncio
async def test_fsm_handler_transitions_on_critical_guard():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=True)
    critical_event = GuardEvaluationResult(
        rule_id="TEST_RULE",
        severity="critical",
        fsm_event="RADAR_CRITICAL",
        message="Critical radar alert",
        track_id="test-track",
        range_m=25.0,
        quality=0.8,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
    )
    context.guard_events = [critical_event]

    handler = FSMHandler(context)
    initial_state = FsmStateSnapshot(current_state=FSMStateEnum.IDLE)

    new_state = await handler.process_fsm_dto(initial_state)

    assert new_state.current_state == FSMStateEnum.ERROR_STATE


@pytest.mark.asyncio
async def test_fsm_handler_warning_spoof_moves_to_active():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=True)
    warning_event = GuardEvaluationResult(
        rule_id="SPOOFING_DETECTED",
        severity="warning",
        fsm_event="RADAR_ALERT_SPOOF",
        message="Spoof detected",
        track_id="spoof-track",
        range_m=120.0,
        quality=0.7,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=True,
        transponder_mode=TransponderModeEnum.SPOOF,
    )
    context.guard_events = [warning_event]

    handler = FSMHandler(context)
    initial_state = FsmStateSnapshot(current_state=FSMStateEnum.IDLE)

    new_state = await handler.process_fsm_dto(initial_state)

    assert new_state.current_state == FSMStateEnum.ACTIVE
