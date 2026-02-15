"""Training mode runtime: scenario execution, action recording, and scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .event_store import EventStore, TruthState
from .radar_clock import Clock, ensure_clock
from .radar_pipeline import RadarPipeline
from .training_evaluator import TrainingEvaluation, TrainingEvaluator, extract_training_actions
from .training_scenarios import TrainingScenario


@dataclass(frozen=True)
class TrainingResult:
    scenario: str
    score: int
    verdict: str
    reaction_time_s: float | None
    errors: tuple[str, ...]


class TrainingActionRecorder:
    def __init__(self, *, event_store: EventStore, clock: Clock | None = None) -> None:
        self._event_store = event_store
        self._clock = ensure_clock(clock)

    def record(
        self,
        *,
        scenario: str,
        action_type: str,
        source: str = "operator",
        payload: dict[str, Any] | None = None,
        ts: float | None = None,
    ) -> None:
        body = {
            "scenario": str(scenario),
            "action_type": str(action_type).upper(),
            "source": str(source),
        }
        if payload:
            body.update(dict(payload))
        self._event_store.append_new(
            subsystem="TRAINING",
            event_type="TRAINING_ACTION",
            payload=body,
            truth_state=TruthState.OK,
            reason=str(action_type).upper(),
            ts=self._clock.now() if ts is None else float(ts),
        )


class TrainingSessionRunner:
    def __init__(
        self,
        *,
        pipeline: RadarPipeline,
        event_store: EventStore,
        scenario: TrainingScenario,
        clock: Clock | None = None,
        evaluator: TrainingEvaluator | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.event_store = event_store
        self.scenario = scenario
        self.clock = ensure_clock(clock)
        self.evaluator = evaluator or TrainingEvaluator()
        self.recorder = TrainingActionRecorder(event_store=event_store, clock=self.clock)

    def run(self, *, scripted_actions: dict[str, Iterable[str]] | None = None) -> TrainingResult:
        action_map = {str(k): tuple(v) for k, v in (scripted_actions or {}).items()}
        start_ts = float(self.scenario.frames[0].ts) if self.scenario.frames else self.clock.now()
        self._emit_status(ts=start_ts, status="IN_PROGRESS", elapsed_s=0.0)

        for frame in self.scenario.frames:
            self._set_clock(float(frame.ts))
            self.pipeline.render_observations(
                list(frame.observations),
                truth_state=frame.truth_state,
                reason=frame.reason,
                is_fallback=frame.is_fallback,
            )
            if frame.checkpoint:
                self.event_store.append_new(
                    subsystem="TRAINING",
                    event_type="TRAINING_CHECKPOINT",
                    payload={
                        "scenario": self.scenario.name,
                        "checkpoint": frame.checkpoint,
                        "hint": frame.hint,
                    },
                    truth_state=TruthState.OK,
                    reason=str(frame.checkpoint),
                    ts=float(frame.ts),
                )
                for action in action_map.get(frame.checkpoint, ()):
                    self.recorder.record(
                        scenario=self.scenario.name,
                        action_type=str(action).upper(),
                        source="scripted",
                        payload={"checkpoint": frame.checkpoint},
                        ts=float(frame.ts) + 0.001,
                    )
            self._emit_status(ts=float(frame.ts), status="IN_PROGRESS", elapsed_s=max(0.0, float(frame.ts) - start_ts))

        end_ts = float(self.scenario.frames[-1].ts) if self.scenario.frames else start_ts
        events = self.event_store.query(from_ts=start_ts - 0.001, to_ts=end_ts + 0.5, order="asc")
        actions = extract_training_actions(events, scenario=self.scenario.name)
        evaluation = self.evaluator.evaluate(scenario=self.scenario, events=events, actions=actions)

        self.event_store.append_new(
            subsystem="TRAINING",
            event_type="TRAINING_RESULT",
            payload={
                "scenario": evaluation.scenario,
                "score": int(evaluation.score),
                "verdict": evaluation.verdict,
                "metrics": {
                    "reaction_time_s": evaluation.reaction_time_s,
                    "correct_actions": evaluation.correct_actions,
                    "missed_actions": evaluation.missed_actions,
                    "wrong_actions": evaluation.wrong_actions,
                },
                "errors": list(evaluation.errors),
            },
            truth_state=TruthState.OK if evaluation.verdict == "PASS" else TruthState.NO_DATA,
            reason=evaluation.verdict,
            ts=end_ts + 0.01,
        )
        self._emit_status(
            ts=end_ts + 0.02,
            status=evaluation.verdict,
            elapsed_s=max(0.0, end_ts - start_ts),
            score=evaluation.score,
        )
        return TrainingResult(
            scenario=evaluation.scenario,
            score=evaluation.score,
            verdict=evaluation.verdict,
            reaction_time_s=evaluation.reaction_time_s,
            errors=evaluation.errors,
        )

    def _emit_status(self, *, ts: float, status: str, elapsed_s: float, score: int | None = None) -> None:
        payload: dict[str, Any] = {
            "scenario": self.scenario.name,
            "title": self.scenario.title,
            "objective": self.scenario.objective,
            "status": status,
            "duration_s": float(self.scenario.duration_s),
            "elapsed_s": float(elapsed_s),
            "expected_outcome": self.scenario.expected_outcome,
        }
        if score is not None:
            payload["score"] = int(score)
        self.event_store.append_new(
            subsystem="TRAINING",
            event_type="TRAINING_STATUS",
            payload=payload,
            truth_state=TruthState.OK,
            reason=status,
            ts=float(ts),
        )

    def _set_clock(self, ts: float) -> None:
        setter = getattr(self.clock, "set", None)
        if callable(setter):
            setter(float(ts))
        pipeline_clock = getattr(self.pipeline, "_clock", None)
        pipeline_setter = getattr(pipeline_clock, "set", None)
        if callable(pipeline_setter):
            pipeline_setter(float(ts))


def evaluate_training_trace(
    *,
    scenario: TrainingScenario,
    events: Iterable[Any],
) -> TrainingEvaluation:
    evaluator = TrainingEvaluator()
    return evaluator.evaluate(scenario=scenario, events=events)
