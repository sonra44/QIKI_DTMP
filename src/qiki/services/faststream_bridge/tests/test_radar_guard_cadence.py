from datetime import UTC, datetime, timedelta
import math
from uuid import uuid4

from qiki.services.faststream_bridge.radar_guard_cadence import RadarGuardCadence
from qiki.services.q_core_agent.core.guard_table import GuardRule, GuardTable
from qiki.shared.models.radar import FriendFoeEnum, RadarTrackModel, RadarTrackStatusEnum, TransponderModeEnum


def _track(*, ts: datetime, range_m: float) -> RadarTrackModel:
    return RadarTrackModel(
        track_id=uuid4(),
        status=RadarTrackStatusEnum.TRACKED,
        range_m=range_m,
        bearing_deg=0.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=1.0,
        rcs_dbsm=1.0,
        quality=0.5,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
        timestamp=ts,
        ts_event=ts,
    )


def test_guard_cadence_edge_only_with_hysteresis_and_cooldown() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "iff": int(FriendFoeEnum.UNKNOWN),
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 10.0,
            "hysteresis_m": 5.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=2.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    # Entry: publish once.
    assert cadence.update(make(base, 60.0))
    # Still active: do not spam.
    assert cadence.update(make(base + timedelta(seconds=1), 60.0)) == []
    # Still within hysteresis-clear band (70 + 5): remain active.
    assert cadence.update(make(base + timedelta(seconds=2), 74.0)) == []
    # Leave hysteresis-clear band: clear.
    assert cadence.update(make(base + timedelta(seconds=3), 76.0)) == []
    # Re-enter before cooldown: suppressed.
    assert cadence.update(make(base + timedelta(seconds=4), 60.0)) == []
    # Re-enter after cooldown: publish again.
    assert cadence.update(make(base + timedelta(seconds=11), 60.0))


def test_guard_cadence_min_duration_requires_continuous_matches() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "min_duration_s": 3.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    # Pending: not enough duration.
    assert cadence.update(make(base, 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=1), 60.0)) == []
    # Gap larger than min_duration resets the pending window.
    assert cadence.update(make(base + timedelta(seconds=10), 60.0)) == []
    # Now hold continuously for >= 3 seconds => publish.
    assert cadence.update(make(base + timedelta(seconds=11), 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=14), 60.0))


def test_guard_cadence_time_source_is_canonical_timestamp_when_times_differ() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 10.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts_event: datetime, ts_legacy: datetime, range_m: float) -> RadarTrackModel:
        t = _track(ts=ts_legacy, range_m=range_m)
        t.track_id = track_id
        t.ts_event = ts_event
        return t

    # First publish.
    assert cadence.update(make(base, base, 60.0))
    # Clear active by leaving condition.
    assert cadence.update(make(base + timedelta(seconds=1), base + timedelta(seconds=1), 90.0)) == []

    # Re-enter with legacy timestamp far in the future and manually changed ts_event.
    # RadarTrackModel normalizes ts_event to timestamp (single time source),
    # so cooldown should follow the canonical timestamp timeline.
    assert (
        cadence.update(
            make(
                base + timedelta(seconds=5),
                base + timedelta(seconds=100),
                60.0,
            )
        )
        != []
    )

    # Still active immediately after publishing, so no extra edge event.
    assert cadence.update(make(base + timedelta(seconds=11), base + timedelta(seconds=200), 60.0)) == []


def test_guard_cadence_falls_back_to_timestamp_when_ts_event_missing() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 10.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        t.ts_event = None
        return t

    # Entry: publish.
    assert cadence.update(make(base, 60.0))
    # Leave active zone.
    assert cadence.update(make(base + timedelta(seconds=1), 90.0)) == []
    # Re-enter before cooldown: suppressed (using timestamp fallback).
    assert cadence.update(make(base + timedelta(seconds=5), 60.0)) == []
    # Re-enter after cooldown: publish.
    assert cadence.update(make(base + timedelta(seconds=11), 60.0))


def test_guard_cadence_uses_stable_rule_track_dedup_key_and_suppresses_repeat() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    t0 = _track(ts=base, range_m=60.0)
    t0.track_id = track_id
    assert cadence.update(t0)

    key = f"{rule.rule_id}:{track_id}"
    assert key in cadence._states

    # Same rule+track while active must not produce duplicate incidents.
    t1 = _track(ts=base + timedelta(seconds=1), range_m=60.0)
    t1.track_id = track_id
    assert cadence.update(t1) == []


def test_guard_cadence_track_id_churn_creates_independent_keys() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_a = uuid4()
    track_b = uuid4()

    t_a0 = _track(ts=base, range_m=60.0)
    t_a0.track_id = track_a
    assert cadence.update(t_a0)

    t_b0 = _track(ts=base + timedelta(seconds=1), range_m=60.0)
    t_b0.track_id = track_b
    assert cadence.update(t_b0)

    key_a = f"{rule.rule_id}:{track_a}"
    key_b = f"{rule.rule_id}:{track_b}"
    assert key_a in cadence._states
    assert key_b in cadence._states

    # Each key stays edge-only independently.
    t_a1 = _track(ts=base + timedelta(seconds=2), range_m=60.0)
    t_a1.track_id = track_a
    assert cadence.update(t_a1) == []

    t_b1 = _track(ts=base + timedelta(seconds=3), range_m=60.0)
    t_b1.track_id = track_b
    assert cadence.update(t_b1) == []


def test_guard_cadence_gc_drops_only_stale_inactive_keys() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    stale_track = uuid4()
    active_track = uuid4()
    trigger_track = uuid4()

    stale_on = _track(ts=base, range_m=60.0)
    stale_on.track_id = stale_track
    assert cadence.update(stale_on)

    stale_off = _track(ts=base + timedelta(seconds=1), range_m=90.0)
    stale_off.track_id = stale_track
    assert cadence.update(stale_off) == []

    active_on = _track(ts=base + timedelta(seconds=2), range_m=60.0)
    active_on.track_id = active_track
    assert cadence.update(active_on)

    # Trigger GC after TTL via an unrelated non-matching track update.
    trigger = _track(ts=base + timedelta(seconds=302), range_m=90.0)
    trigger.track_id = trigger_track
    assert cadence.update(trigger) == []

    stale_key = f"{rule.rule_id}:{stale_track}"
    active_key = f"{rule.rule_id}:{active_track}"
    assert stale_key not in cadence._states
    assert active_key in cadence._states


def test_guard_cadence_cooldown_is_key_scoped_across_tracks() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 10.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_a = uuid4()
    track_b = uuid4()

    a_on = _track(ts=base, range_m=60.0)
    a_on.track_id = track_a
    assert cadence.update(a_on)

    # Cooldown from track A must not suppress independent key for track B.
    b_on = _track(ts=base + timedelta(seconds=1), range_m=60.0)
    b_on.track_id = track_b
    assert cadence.update(b_on)

    # Deactivate A, then re-enter before cooldown expiry -> suppressed for A only.
    a_off = _track(ts=base + timedelta(seconds=2), range_m=90.0)
    a_off.track_id = track_a
    assert cadence.update(a_off) == []

    a_reenter_early = _track(ts=base + timedelta(seconds=5), range_m=60.0)
    a_reenter_early.track_id = track_a
    assert cadence.update(a_reenter_early) == []

    # After cooldown window A can emit again.
    a_reenter_late = _track(ts=base + timedelta(seconds=11), range_m=60.0)
    a_reenter_late.track_id = track_a
    assert cadence.update(a_reenter_late)


def test_guard_cadence_min_duration_boundary_and_short_gaps_keep_window() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "min_duration_s": 3.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    t0 = _track(ts=base, range_m=60.0)
    t0.track_id = track_id
    assert cadence.update(t0) == []

    # Short gap (< min_duration) should keep accumulation window.
    t1 = _track(ts=base + timedelta(seconds=2), range_m=60.0)
    t1.track_id = track_id
    assert cadence.update(t1) == []

    # Exactly at boundary (3s since first match) should publish.
    t2 = _track(ts=base + timedelta(seconds=3), range_m=60.0)
    t2.track_id = track_id
    assert cadence.update(t2)


def test_guard_cadence_min_duration_resets_on_gap_gt_threshold_per_key_with_multitrack() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "min_duration_s": 3.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_a = uuid4()
    track_b = uuid4()

    a0 = _track(ts=base, range_m=60.0)
    a0.track_id = track_a
    assert cadence.update(a0) == []

    # Other track activity must not affect key A timing.
    b0 = _track(ts=base + timedelta(seconds=1), range_m=60.0)
    b0.track_id = track_b
    assert cadence.update(b0) == []

    # Gap on A is > min_duration => pending window for A must reset.
    a1 = _track(ts=base + timedelta(seconds=4), range_m=60.0)
    a1.track_id = track_a
    assert cadence.update(a1) == []

    # Not enough time since reset point.
    a2 = _track(ts=base + timedelta(seconds=6), range_m=60.0)
    a2.track_id = track_a
    assert cadence.update(a2) == []

    # Reaches boundary after reset => publish.
    a3 = _track(ts=base + timedelta(seconds=7), range_m=60.0)
    a3.track_id = track_a
    assert cadence.update(a3)


def test_guard_cadence_oscillation_with_hysteresis_and_cooldown_reentry() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "iff": int(FriendFoeEnum.UNKNOWN),
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 5.0,
            "hysteresis_m": 5.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    # Initial entry -> publish.
    assert cadence.update(make(base, 60.0))
    # Oscillation within hysteresis-clear band keeps active and suppresses duplicates.
    assert cadence.update(make(base + timedelta(seconds=1), 74.0)) == []
    # Leave clear band (> 70 + 5) -> deactivate.
    assert cadence.update(make(base + timedelta(seconds=2), 76.0)) == []
    # Re-enter before cooldown expiry -> suppressed.
    assert cadence.update(make(base + timedelta(seconds=4), 60.0)) == []
    # Re-enter after cooldown expiry -> publish again.
    assert cadence.update(make(base + timedelta(seconds=8), 60.0))


def test_guard_cadence_uses_default_cooldown_when_rule_cooldown_missing() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    # Initial edge publish.
    assert cadence.update(make(base, 60.0))
    # Deactivate key.
    assert cadence.update(make(base + timedelta(seconds=1), 90.0)) == []
    # Re-entry before default cooldown expiry is suppressed.
    assert cadence.update(make(base + timedelta(seconds=4), 60.0)) == []
    # Re-entry after default cooldown expiry publishes.
    assert cadence.update(make(base + timedelta(seconds=6), 60.0))


def test_guard_cadence_explicit_zero_cooldown_overrides_default_fallback() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    # Initial edge publish.
    assert cadence.update(make(base, 60.0))
    # Deactivate key.
    assert cadence.update(make(base + timedelta(seconds=1), 90.0)) == []
    # Re-entry shortly after deactivation should publish because explicit cooldown=0
    # must override default_cooldown_s fallback.
    assert cadence.update(make(base + timedelta(seconds=2), 60.0))


def test_guard_cadence_malformed_cooldown_uses_default_fallback() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    # Simulate malformed runtime value bypassing schema validation.
    rule.cooldown_s = "bad"  # type: ignore[assignment]
    class _Table:
        def __init__(self, rules: list[GuardRule]) -> None:
            self.rules = rules

    table = _Table([rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    assert cadence.update(make(base, 60.0))
    assert cadence.update(make(base + timedelta(seconds=1), 90.0)) == []
    # Suppressed by default fallback cooldown.
    assert cadence.update(make(base + timedelta(seconds=4), 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=6), 60.0))


def test_guard_cadence_nan_cooldown_uses_default_fallback() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    # Simulate non-finite numeric cooldown.
    rule.cooldown_s = math.nan
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    assert cadence.update(make(base, 60.0))
    assert cadence.update(make(base + timedelta(seconds=1), 90.0)) == []
    # NaN must not disable suppression; fallback default cooldown applies.
    assert cadence.update(make(base + timedelta(seconds=4), 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=6), 60.0))


def test_guard_cadence_inf_cooldown_uses_default_fallback() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    # Simulate non-finite positive cooldown.
    rule.cooldown_s = math.inf
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    assert cadence.update(make(base, 60.0))
    assert cadence.update(make(base + timedelta(seconds=1), 90.0)) == []
    # +inf must not lead to permanent suppression; fallback default cooldown applies.
    assert cadence.update(make(base + timedelta(seconds=4), 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=6), 60.0))


def test_guard_cadence_neg_inf_cooldown_uses_default_fallback() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    # Simulate non-finite negative cooldown.
    rule.cooldown_s = -math.inf
    class _Table:
        def __init__(self, rules: list[GuardRule]) -> None:
            self.rules = rules

    table = _Table([rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    assert cadence.update(make(base, 60.0))
    assert cadence.update(make(base + timedelta(seconds=1), 90.0)) == []
    assert cadence.update(make(base + timedelta(seconds=4), 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=6), 60.0))


def test_guard_cadence_negative_finite_cooldown_is_clamped_to_zero() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    # Simulate invalid negative finite cooldown after model creation.
    rule.cooldown_s = -1.0
    class _Table:
        def __init__(self, rules: list[GuardRule]) -> None:
            self.rules = rules

    table = _Table([rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    assert cadence.update(make(base, 60.0))
    assert cadence.update(make(base + timedelta(seconds=1), 90.0)) == []
    # Negative finite cooldown clamps to zero => no suppression on re-entry.
    assert cadence.update(make(base + timedelta(seconds=2), 60.0))


def test_guard_cadence_gc_handles_many_inactive_keys_with_edge_cooldowns() -> None:
    rule_zero = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE_ZERO",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE_ZERO",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    rule_nonfinite = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE_NONFINITE",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE_NONFINITE",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    # Simulate unsafe runtime value that must fallback to default cooldown.
    rule_nonfinite.cooldown_s = math.nan
    table = GuardTable(schema_version=1, rules=[rule_zero, rule_nonfinite])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_ids = [uuid4() for _ in range(120)]

    # Build many inactive keys for both rules: publish once, then deactivate.
    for idx, track_id in enumerate(track_ids):
        t_on = _track(ts=base + timedelta(seconds=idx), range_m=60.0)
        t_on.track_id = track_id
        assert cadence.update(t_on)

        t_off = _track(ts=base + timedelta(seconds=idx, milliseconds=500), range_m=90.0)
        t_off.track_id = track_id
        assert cadence.update(t_off) == []

    assert len(cadence._states) == len(track_ids) * 2

    # Trigger GC after TTL via unrelated non-matching update.
    trigger = _track(ts=base + timedelta(seconds=600), range_m=90.0)
    trigger.track_id = uuid4()
    assert cadence.update(trigger) == []

    # All previously inactive keys should be dropped regardless of cooldown edge path.
    assert len(cadence._states) == 0


def test_guard_cadence_gc_keeps_recently_reactivated_keys_under_mixed_cooldowns() -> None:
    rule_zero = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE_ZERO_KEEP",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE_ZERO_KEEP",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    rule_nonfinite = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE_NONFINITE_KEEP",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE_NONFINITE_KEEP",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    # Force fallback path for one rule.
    rule_nonfinite.cooldown_s = math.nan
    table = GuardTable(schema_version=1, rules=[rule_zero, rule_nonfinite])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    stale_track = uuid4()
    hot_track = uuid4()

    # Create a stale key that should be removed by GC.
    stale_on = _track(ts=base, range_m=60.0)
    stale_on.track_id = stale_track
    assert cadence.update(stale_on)
    stale_off = _track(ts=base + timedelta(seconds=1), range_m=90.0)
    stale_off.track_id = stale_track
    assert cadence.update(stale_off) == []

    # Same track becomes active again shortly before GC trigger.
    hot_on = _track(ts=base + timedelta(seconds=299), range_m=60.0)
    hot_on.track_id = hot_track
    assert cadence.update(hot_on)
    hot_off = _track(ts=base + timedelta(seconds=300), range_m=90.0)
    hot_off.track_id = hot_track
    assert cadence.update(hot_off) == []
    hot_reenter = _track(ts=base + timedelta(seconds=301), range_m=60.0)
    hot_reenter.track_id = hot_track
    assert cadence.update(hot_reenter)

    # Trigger GC after TTL with unrelated non-match.
    trigger = _track(ts=base + timedelta(seconds=302), range_m=90.0)
    trigger.track_id = uuid4()
    assert cadence.update(trigger) == []

    stale_zero_key = f"{rule_zero.rule_id}:{stale_track}"
    stale_nonfinite_key = f"{rule_nonfinite.rule_id}:{stale_track}"
    hot_zero_key = f"{rule_zero.rule_id}:{hot_track}"
    hot_nonfinite_key = f"{rule_nonfinite.rule_id}:{hot_track}"

    # Old inactive keys are removed; recently reactivated keys are preserved.
    assert stale_zero_key not in cadence._states
    assert stale_nonfinite_key not in cadence._states
    assert hot_zero_key in cadence._states
    assert hot_nonfinite_key in cadence._states


def test_guard_cadence_min_duration_reactivation_after_long_gap_under_churn() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE_MIN_DURATION_REACT",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE_MIN_DURATION_REACT",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "min_duration_s": 3.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    hot_track = uuid4()
    churn_tracks = [uuid4() for _ in range(20)]

    def make(track_id: object, ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id  # type: ignore[assignment]
        return t

    # Initial activation requires full accumulation to min_duration.
    assert cadence.update(make(hot_track, base, 60.0)) == []
    assert cadence.update(make(hot_track, base + timedelta(seconds=1), 60.0)) == []
    assert cadence.update(make(hot_track, base + timedelta(seconds=3), 60.0))

    # Deactivate hot key, then keep long inactive period with churn traffic.
    assert cadence.update(make(hot_track, base + timedelta(seconds=4), 90.0)) == []
    for idx, track_id in enumerate(churn_tracks):
        ts = base + timedelta(seconds=200 + idx)
        assert cadence.update(make(track_id, ts, 60.0)) == []
        assert cadence.update(make(track_id, ts + timedelta(milliseconds=200), 90.0)) == []

    # Reactivation after long gap must start a new min_duration window.
    assert cadence.update(make(hot_track, base + timedelta(seconds=250), 60.0)) == []
    assert cadence.update(make(hot_track, base + timedelta(seconds=252), 60.0)) == []
    # Exactly at boundary (3 seconds from reactivation) publishes.
    assert cadence.update(make(hot_track, base + timedelta(seconds=253), 60.0))


def test_guard_cadence_cooldown_timestamp_remains_key_local_after_gc_churn() -> None:
    rule_zero = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE_ZERO_COOLDOWN_LOCAL",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE_ZERO_COOLDOWN_LOCAL",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    rule_nonfinite = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE_NONFINITE_COOLDOWN_LOCAL",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE_NONFINITE_COOLDOWN_LOCAL",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "cooldown_s": 0.0,
            "hysteresis_m": 0.0,
        }
    )
    # Force fallback path.
    rule_nonfinite.cooldown_s = math.nan
    table = GuardTable(schema_version=1, rules=[rule_zero, rule_nonfinite])
    cadence = RadarGuardCadence(table, default_cooldown_s=5.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    hot_track = uuid4()
    stale_track = uuid4()

    def make(track_id: object, ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id  # type: ignore[assignment]
        return t

    # Build stale key and make it eligible for GC.
    assert cadence.update(make(stale_track, base, 60.0))
    assert cadence.update(make(stale_track, base + timedelta(seconds=1), 90.0)) == []

    # Publish hot key near GC moment, then deactivate.
    assert cadence.update(make(hot_track, base + timedelta(seconds=300), 60.0))
    assert cadence.update(make(hot_track, base + timedelta(seconds=301), 90.0)) == []

    # Trigger GC after TTL for stale key: stale key should be removed; hot key remains recent.
    assert cadence.update(make(uuid4(), base + timedelta(seconds=302), 90.0)) == []

    stale_zero_key = f"{rule_zero.rule_id}:{stale_track}"
    stale_nonfinite_key = f"{rule_nonfinite.rule_id}:{stale_track}"
    hot_zero_key = f"{rule_zero.rule_id}:{hot_track}"
    hot_nonfinite_key = f"{rule_nonfinite.rule_id}:{hot_track}"
    assert stale_zero_key not in cadence._states
    assert stale_nonfinite_key not in cadence._states
    assert hot_zero_key in cadence._states
    assert hot_nonfinite_key in cadence._states

    # Reactivate hot key shortly after deactivation:
    # - zero cooldown rule should emit immediately (key-local no suppression),
    # - non-finite fallback rule should still suppress until default cooldown expires.
    out_early = cadence.update(make(hot_track, base + timedelta(seconds=303), 60.0))
    out_early_ids = {o.rule_id for o in out_early}
    assert rule_zero.rule_id in out_early_ids
    assert rule_nonfinite.rule_id not in out_early_ids

    # After fallback cooldown window, non-finite path can emit for the same key.
    assert cadence.update(make(hot_track, base + timedelta(seconds=307), 60.0))


def test_guard_cadence_gc_clear_prevents_old_cooldown_leak_at_min_duration_boundary() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE_GC_MIN_DURATION_COOLDOWN_BOUNDARY",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE_GC_MIN_DURATION_COOLDOWN_BOUNDARY",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "min_duration_s": 3.0,
            "cooldown_s": 308.0,
            "hysteresis_m": 0.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    # First lifecycle: publish after initial min_duration accumulation.
    assert cadence.update(make(base, 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=1), 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=3), 60.0))
    assert cadence.update(make(base + timedelta(seconds=4), 90.0)) == []

    # Trigger GC after TTL to clear stale inactive state for this key.
    trigger = _track(ts=base + timedelta(seconds=305), range_m=90.0)
    trigger.track_id = uuid4()
    assert cadence.update(trigger) == []
    key = f"{rule.rule_id}:{track_id}"
    assert key not in cadence._states

    # Re-enter near old cooldown cutoff and require fresh min_duration.
    assert cadence.update(make(base + timedelta(seconds=307), 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=309), 60.0)) == []
    # At boundary publish must happen; old cooldown from previous lifecycle must not leak.
    assert cadence.update(make(base + timedelta(seconds=310), 60.0))


def test_guard_cadence_combined_hysteresis_min_duration_cooldown_with_gc_between_cycles() -> None:
    rule = GuardRule.model_validate(
        {
            "id": "UNKNOWN_CONTACT_CLOSE_COMBINED_BOUNDARY",
            "description": "test",
            "severity": "critical",
            "fsm_event": "RADAR_ALERT_UNKNOWN_CLOSE_COMBINED_BOUNDARY",
            "min_range_m": 0.0,
            "max_range_m": 70.0,
            "min_quality": 0.0,
            "min_duration_s": 3.0,
            "cooldown_s": 5.0,
            "hysteresis_m": 5.0,
        }
    )
    table = GuardTable(schema_version=1, rules=[rule])
    cadence = RadarGuardCadence(table, default_cooldown_s=0.0)

    base = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()

    def make(ts: datetime, r: float) -> RadarTrackModel:
        t = _track(ts=ts, range_m=r)
        t.track_id = track_id
        return t

    # Cycle 1: accumulate min_duration then publish once.
    assert cadence.update(make(base, 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=2), 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=3), 60.0))

    # Hysteresis clear-band (<= 75) keeps active, no spam.
    assert cadence.update(make(base + timedelta(seconds=4), 74.0)) == []
    # Leave clear-band (> 75) to deactivate.
    assert cadence.update(make(base + timedelta(seconds=5), 76.0)) == []

    # Re-entry before cooldown expiry is suppressed.
    assert cadence.update(make(base + timedelta(seconds=8), 60.0)) == []

    # Force another deactivation before GC.
    assert cadence.update(make(base + timedelta(seconds=9), 76.0)) == []

    # GC after TTL should clear stale inactive state.
    trigger = _track(ts=base + timedelta(seconds=310), range_m=90.0)
    trigger.track_id = uuid4()
    assert cadence.update(trigger) == []
    key = f"{rule.rule_id}:{track_id}"
    assert key not in cadence._states

    # Cycle 2 after GC: must re-accumulate min_duration.
    assert cadence.update(make(base + timedelta(seconds=311), 60.0)) == []
    assert cadence.update(make(base + timedelta(seconds=312), 60.0)) == []
    # Boundary publish in fresh cycle.
    assert cadence.update(make(base + timedelta(seconds=314), 60.0))
