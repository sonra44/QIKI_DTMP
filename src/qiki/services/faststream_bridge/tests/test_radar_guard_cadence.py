from datetime import UTC, datetime, timedelta
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
