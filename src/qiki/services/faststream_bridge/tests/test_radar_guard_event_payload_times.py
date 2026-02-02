from datetime import UTC, datetime
from uuid import uuid4

from qiki.services.faststream_bridge.app import _build_radar_guard_event_payload
from qiki.services.q_core_agent.core.guard_table import GuardEvaluationResult
from qiki.shared.models.radar import FriendFoeEnum, RadarTrackModel, RadarTrackStatusEnum, TransponderModeEnum


def test_guard_event_payload_uses_ts_event_and_ts_ingest() -> None:
    event_dt = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    ingest_dt = datetime(2026, 2, 2, 12, 0, 1, tzinfo=UTC)
    track_id = uuid4()
    track = RadarTrackModel(
        track_id=track_id,
        status=RadarTrackStatusEnum.TRACKED,
        range_m=10.0,
        bearing_deg=0.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=1.0,
        rcs_dbsm=1.0,
        timestamp=event_dt,
        ts_ingest=ingest_dt,
    )
    evaluation = GuardEvaluationResult(
        rule_id="UNKNOWN_CONTACT_CLOSE",
        severity="critical",
        fsm_event="RADAR_ALERT_UNKNOWN_CLOSE",
        message="test",
        track_id=str(track_id),
        range_m=10.0,
        quality=0.5,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
    )

    payload = _build_radar_guard_event_payload(track=track, evaluation=evaluation)

    assert payload["ts_epoch"] == float(event_dt.timestamp())
    assert payload["ts_ingest_epoch"] == float(ingest_dt.timestamp())


def test_guard_event_payload_omits_ts_ingest_when_missing() -> None:
    event_dt = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    track_id = uuid4()
    track = RadarTrackModel(
        track_id=track_id,
        status=RadarTrackStatusEnum.TRACKED,
        range_m=10.0,
        bearing_deg=0.0,
        elev_deg=0.0,
        vr_mps=0.0,
        snr_db=1.0,
        rcs_dbsm=1.0,
        timestamp=event_dt,
    )
    evaluation = GuardEvaluationResult(
        rule_id="UNKNOWN_CONTACT_CLOSE",
        severity="critical",
        fsm_event="RADAR_ALERT_UNKNOWN_CLOSE",
        message="test",
        track_id=str(track_id),
        range_m=10.0,
        quality=0.5,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
    )

    payload = _build_radar_guard_event_payload(track=track, evaluation=evaluation)

    assert payload["ts_epoch"] == float(event_dt.timestamp())
    assert "ts_ingest_epoch" not in payload

