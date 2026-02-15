from __future__ import annotations

from pathlib import Path

from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.q_core_agent.core.radar_clock import ReplayClock
from qiki.services.q_core_agent.core.radar_pipeline import RadarPipeline, RadarRenderConfig
from qiki.services.q_core_agent.core.radar_replay import load_trace
from qiki.services.q_core_agent.core.trace_export import TraceExportFilter, export_event_store_jsonl_async
from qiki.services.q_core_agent.core.training_evaluator import TrainingEvaluator
from qiki.services.q_core_agent.core.training_mode import TrainingSessionRunner, evaluate_training_trace
from qiki.services.q_core_agent.core.training_scenarios import (
    available_training_scenarios,
    build_training_scenario,
)


def _pipeline(store: EventStore) -> RadarPipeline:
    return RadarPipeline(
        RadarRenderConfig(renderer="unicode", view="top", fps_max=10, color=False),
        event_store=store,
        clock=ReplayClock(0.0),
    )


def test_training_scenarios_available_minimum_three() -> None:
    names = available_training_scenarios()
    assert len(names) >= 3
    assert "cpa_warning" in names
    assert "sensor_dropout" in names


def test_training_scenario_with_scripted_actions_passes() -> None:
    store = EventStore(maxlen=5000, enabled=True)
    scenario = build_training_scenario("cpa_warning", seed=7)
    runner = TrainingSessionRunner(
        pipeline=_pipeline(store),
        event_store=store,
        scenario=scenario,
        clock=ReplayClock(0.0),
    )
    result = runner.run(scripted_actions={"CPA_ALERT": ["ALERT_ACK"]})
    assert result.verdict == "PASS"
    assert result.score >= 70
    training_result_events = store.filter(subsystem="TRAINING", event_type="TRAINING_RESULT")
    assert training_result_events


def test_training_scenario_without_actions_fails() -> None:
    store = EventStore(maxlen=5000, enabled=True)
    scenario = build_training_scenario("cpa_warning", seed=7)
    runner = TrainingSessionRunner(
        pipeline=_pipeline(store),
        event_store=store,
        scenario=scenario,
        clock=ReplayClock(0.0),
    )
    result = runner.run(scripted_actions={})
    assert result.verdict == "FAIL"
    assert result.score < 70


def test_training_replay_trace_keeps_same_score(tmp_path: Path) -> None:
    store = EventStore(maxlen=10000, enabled=True)
    scenario = build_training_scenario("policy_degradation", seed=42)
    runner = TrainingSessionRunner(
        pipeline=_pipeline(store),
        event_store=store,
        scenario=scenario,
        clock=ReplayClock(0.0),
    )
    first = runner.run(scripted_actions={"POLICY_DEGRADE": ["POLICY_PROFILE_SWITCH"]})
    assert first.verdict == "PASS"

    trace_path = tmp_path / "training_trace.jsonl"
    export_event_store_jsonl_async(
        store,
        str(trace_path),
        export_filter=TraceExportFilter(
            from_ts=0.0,
            to_ts=10_000.0,
            subsystems=frozenset({"TRAINING"}),
            max_lines=20_000,
        ),
    )
    replay_events = load_trace(str(trace_path), strict=True)
    second = evaluate_training_trace(scenario=scenario, events=replay_events)
    assert second.score == first.score
    assert second.verdict == first.verdict


def test_training_evaluator_reaction_time_metric() -> None:
    scenario = build_training_scenario("sensor_dropout", seed=9)
    evaluator = TrainingEvaluator()
    events = [
        {
            "ts": 1.0,
            "subsystem": "TRAINING",
            "event_type": "TRAINING_STATUS",
            "truth_state": "OK",
            "reason": "IN_PROGRESS",
            "payload": {"scenario": "sensor_dropout", "status": "IN_PROGRESS"},
        },
        {
            "ts": 2.0,
            "subsystem": "TRAINING",
            "event_type": "TRAINING_CHECKPOINT",
            "truth_state": "OK",
            "reason": "NO_DATA_START",
            "payload": {"scenario": "sensor_dropout", "checkpoint": "NO_DATA_START"},
        },
        {
            "ts": 3.0,
            "subsystem": "TRAINING",
            "event_type": "TRAINING_ACTION",
            "truth_state": "OK",
            "reason": "TOGGLE_INSPECTOR",
            "payload": {"scenario": "sensor_dropout", "action_type": "TOGGLE_INSPECTOR"},
        },
    ]
    result = evaluator.evaluate(scenario=scenario, events=events)
    assert result.verdict == "PASS"
    assert result.reaction_time_s is not None
    assert abs(result.reaction_time_s - 1.0) < 1e-6
