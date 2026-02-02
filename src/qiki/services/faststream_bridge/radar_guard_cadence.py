from __future__ import annotations

from dataclasses import dataclass

from qiki.services.q_core_agent.core.guard_table import GuardTable
from qiki.services.q_core_agent.core.guard_table import GuardEvaluationResult
from qiki.shared.models.radar import RadarTrackModel


@dataclass
class _GuardKeyState:
    # Uses simulation-truth time (track.ts_event) in epoch seconds.
    first_match_ts_epoch: float = 0.0
    last_match_ts_epoch: float = 0.0
    last_publish_ts_epoch: float = 0.0
    active: bool = False


class RadarGuardCadence:
    """Edge-triggered cadence for guard alerts (anti-flap, no-spam).

    The cadence operates in simulation time (ts_event) for replay determinism.
    It publishes at most one alert per (rule_id, track_id) while the condition remains active.
    Re-entry alerts are suppressed by rule.cooldown_s (or a default).
    """

    def __init__(self, table: GuardTable, *, default_cooldown_s: float = 2.0) -> None:
        self._table = table
        self._default_cooldown_s = max(0.0, float(default_cooldown_s))
        self._states: dict[str, _GuardKeyState] = {}

    @staticmethod
    def _ts_epoch(track: RadarTrackModel) -> float:
        dt = track.ts_event or track.timestamp
        return float(dt.timestamp())

    def update(self, track: RadarTrackModel) -> list[GuardEvaluationResult]:
        """Return guard alert evaluations to publish (edge-only)."""

        now_ts = self._ts_epoch(track)
        to_publish: list[GuardEvaluationResult] = []

        for rule in self._table.rules:
            key = f"{rule.rule_id}|{track.track_id}"
            state = self._states.get(key)
            is_active = bool(state.active) if state else False

            matches = rule.matches(track, active=is_active)
            if not matches:
                # Clear active state immediately when the hysteresis-expanded matcher drops.
                if state and state.active:
                    state.active = False
                    state.first_match_ts_epoch = 0.0
                    state.last_match_ts_epoch = 0.0
                continue

            if state is None:
                state = _GuardKeyState(first_match_ts_epoch=now_ts, last_match_ts_epoch=now_ts)
                self._states[key] = state
            else:
                min_duration_s = max(0.0, float(getattr(rule, "min_duration_s", 0.0) or 0.0))
                if min_duration_s and state.last_match_ts_epoch:
                    # Require the condition to hold continuously: if there is a long gap between
                    # matches, reset the pending window.
                    if (now_ts - float(state.last_match_ts_epoch)) > min_duration_s:
                        state.first_match_ts_epoch = now_ts
                if not state.first_match_ts_epoch:
                    state.first_match_ts_epoch = now_ts
                state.last_match_ts_epoch = now_ts

            # Already active => do not spam.
            if state.active:
                continue

            if min_duration_s and (now_ts - float(state.first_match_ts_epoch or now_ts)) < min_duration_s:
                continue

            cooldown_s = getattr(rule, "cooldown_s", None)
            cooldown_s = (
                max(0.0, float(cooldown_s)) if isinstance(cooldown_s, (int, float)) else self._default_cooldown_s
            )
            if cooldown_s and (now_ts - float(state.last_publish_ts_epoch or 0.0)) < cooldown_s:
                continue

            state.active = True
            state.last_publish_ts_epoch = now_ts
            to_publish.append(rule.build_result(track))

        self._gc(now_ts)
        return to_publish

    def _gc(self, now_ts: float) -> None:
        # Best-effort bound: drop inactive keys after a while to avoid unbounded growth
        # in long-running stacks with many transient tracks.
        ttl_s = 300.0
        for key, state in list(self._states.items()):
            if state.active:
                continue
            last = float(state.last_publish_ts_epoch or 0.0)
            # If never published, use last_match.
            if not last:
                last = float(state.last_match_ts_epoch or 0.0)
            if last and (now_ts - last) > ttl_s:
                self._states.pop(key, None)
