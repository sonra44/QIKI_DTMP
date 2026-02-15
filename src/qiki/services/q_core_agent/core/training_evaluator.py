"""Training scoring engine for operator scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .training_scenarios import TrainingExpectedAction, TrainingScenario


@dataclass(frozen=True)
class TrainingAction:
    action_type: str
    ts: float
    payload: dict[str, Any]


@dataclass(frozen=True)
class TrainingEvaluation:
    scenario: str
    score: int
    verdict: str
    reaction_time_s: float | None
    correct_actions: int
    missed_actions: int
    wrong_actions: int
    errors: tuple[str, ...]


def _event_to_dict(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        return dict(event)
    payload = getattr(event, "payload", {})
    truth_state = getattr(event, "truth_state", "")
    truth_state_value = getattr(truth_state, "value", truth_state)
    return {
        "ts": float(getattr(event, "ts", 0.0)),
        "subsystem": str(getattr(event, "subsystem", "")),
        "event_type": str(getattr(event, "event_type", "")),
        "payload": payload if isinstance(payload, dict) else {},
        "reason": str(getattr(event, "reason", "")),
        "truth_state": str(truth_state_value),
    }


def extract_training_actions(events: Iterable[Any], *, scenario: str) -> tuple[TrainingAction, ...]:
    actions: list[TrainingAction] = []
    for raw in events:
        event = _event_to_dict(raw)
        if event.get("subsystem") != "TRAINING" or event.get("event_type") != "TRAINING_ACTION":
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("scenario", "")).strip().lower() != scenario.strip().lower():
            continue
        action_type = str(payload.get("action_type", "")).strip().upper()
        if not action_type:
            continue
        actions.append(
            TrainingAction(
                action_type=action_type,
                ts=float(event.get("ts", 0.0)),
                payload=dict(payload),
            )
        )
    actions.sort(key=lambda item: item.ts)
    return tuple(actions)


class TrainingEvaluator:
    def evaluate(
        self,
        *,
        scenario: TrainingScenario,
        events: Iterable[Any],
        actions: Iterable[TrainingAction] | None = None,
    ) -> TrainingEvaluation:
        event_rows = [_event_to_dict(item) for item in events]
        event_rows.sort(key=lambda row: float(row.get("ts", 0.0)))
        scenario_name = scenario.name.strip().lower()
        training_events = [
            row
            for row in event_rows
            if str(row.get("subsystem", "")).upper() == "TRAINING"
            and str((row.get("payload") or {}).get("scenario", "")).strip().lower() == scenario_name
        ]
        if actions is None:
            tracked_actions = list(extract_training_actions(event_rows, scenario=scenario.name))
        else:
            tracked_actions = sorted(list(actions), key=lambda item: item.ts)

        scenario_start_ts = 0.0
        for row in training_events:
            if str(row.get("event_type", "")) == "TRAINING_STATUS":
                payload = row.get("payload", {})
                if isinstance(payload, dict) and str(payload.get("status", "")).upper() == "IN_PROGRESS":
                    scenario_start_ts = float(row.get("ts", 0.0))
                    break
        if scenario_start_ts <= 0 and event_rows:
            scenario_start_ts = float(event_rows[0].get("ts", 0.0))

        correct = 0
        missed = 0
        errors: list[str] = []
        reaction_times: list[float] = []
        consumed_action_indexes: set[int] = set()

        for expected in scenario.expected_actions:
            trigger_ts = self._checkpoint_ts(training_events, expected.trigger_checkpoint, scenario_start_ts)
            matched = self._find_action(
                expected=expected,
                actions=tracked_actions,
                trigger_ts=trigger_ts,
                consumed=consumed_action_indexes,
            )
            if matched is None:
                if expected.required:
                    missed += 1
                    errors.append(f"MISSED:{expected.action_type}@{expected.trigger_checkpoint}")
                continue
            action_idx, action = matched
            consumed_action_indexes.add(action_idx)
            dt = max(0.0, float(action.ts) - float(trigger_ts))
            reaction_times.append(dt)
            correct += 1

        wrong = max(0, len(tracked_actions) - len(consumed_action_indexes))
        for idx, action in enumerate(tracked_actions):
            if idx not in consumed_action_indexes:
                errors.append(f"UNEXPECTED:{action.action_type}")

        score = 100
        score -= missed * 35
        score -= wrong * 10
        if reaction_times:
            avg_reaction = sum(reaction_times) / len(reaction_times)
            if avg_reaction > 4.0:
                score -= min(20, int((avg_reaction - 4.0) * 4))
        score = max(0, min(100, int(round(score))))
        verdict = "PASS" if missed == 0 and score >= 70 else "FAIL"
        reaction_time = None if not reaction_times else float(sum(reaction_times) / len(reaction_times))

        return TrainingEvaluation(
            scenario=scenario.name,
            score=score,
            verdict=verdict,
            reaction_time_s=reaction_time,
            correct_actions=correct,
            missed_actions=missed,
            wrong_actions=wrong,
            errors=tuple(errors),
        )

    def _checkpoint_ts(self, events: list[dict[str, Any]], checkpoint: str, fallback_ts: float) -> float:
        needle = str(checkpoint).strip()
        for event in events:
            if str(event.get("event_type", "")) != "TRAINING_CHECKPOINT":
                continue
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue
            if str(payload.get("checkpoint", "")).strip() == needle:
                return float(event.get("ts", fallback_ts))
        return float(fallback_ts)

    def _find_action(
        self,
        *,
        expected: TrainingExpectedAction,
        actions: list[TrainingAction],
        trigger_ts: float,
        consumed: set[int],
    ) -> tuple[int, TrainingAction] | None:
        target = expected.action_type.strip().upper()
        deadline = float(expected.deadline_s)
        for idx, action in enumerate(actions):
            if idx in consumed:
                continue
            if action.action_type != target:
                continue
            dt = float(action.ts) - float(trigger_ts)
            if dt < 0:
                continue
            if dt <= deadline:
                return idx, action
        return None
