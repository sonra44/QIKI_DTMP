import time

from qiki.services.operator_console.core.incidents import IncidentStore
from qiki.services.operator_console.core.incident_rules import IncidentRule, IncidentRulesConfig


def _config_for_radar_guards() -> IncidentRulesConfig:
    return IncidentRulesConfig(
        version=1,
        rules=[
            IncidentRule.model_validate(
                {
                    "id": "FOE_TRANSPONDER_OFF_APPROACH",
                    "enabled": True,
                    "title": "Foe approach (transponder off)",
                    "description": "guard",
                    "match": {
                        "type": "radar",
                        "source": "guard",
                        "subject": "FOE_TRANSPONDER_OFF_APPROACH",
                        "field": "range_m",
                    },
                    "threshold": {"op": "<", "value": 150, "cooldown_s": 60},
                    "severity": "A",
                    "require_ack": True,
                    "auto_clear": False,
                }
            ),
            IncidentRule.model_validate(
                {
                    "id": "SPOOFING_DETECTED",
                    "enabled": True,
                    "title": "Spoofing detected",
                    "description": "guard",
                    "match": {
                        "type": "radar",
                        "source": "guard",
                        "subject": "SPOOFING_DETECTED",
                        "field": "transponder_mode",
                    },
                    "threshold": {"op": "=", "value": 3, "cooldown_s": 60},
                    "severity": "W",
                    "require_ack": True,
                    "auto_clear": False,
                }
            ),
        ],
    )


def _event(
    *,
    ts: float,
    subject: str,
    payload: dict,
    source: str = "guard",
    etype: str = "radar",
) -> dict:
    return {
        "type": etype,
        "source": source,
        "subject": subject,
        "ts_epoch": ts,
        "payload": payload,
    }


def test_foe_transponder_off_approach_true_false_borderline() -> None:
    store = IncidentStore(_config_for_radar_guards())
    ts = time.time()
    track_id = "trk-1"

    # true: < 150
    store.ingest(
        _event(
            ts=ts,
            subject="FOE_TRANSPONDER_OFF_APPROACH",
            payload={"id": track_id, "track_id": track_id, "range_m": 149.0},
        )
    )
    incidents = store.list_incidents()
    assert len(incidents) == 1
    assert incidents[0].rule_id == "FOE_TRANSPONDER_OFF_APPROACH"

    # borderline: == 150 => should not match (<)
    store2 = IncidentStore(_config_for_radar_guards())
    store2.ingest(
        _event(
            ts=ts,
            subject="FOE_TRANSPONDER_OFF_APPROACH",
            payload={"id": track_id, "track_id": track_id, "range_m": 150.0},
        )
    )
    assert store2.list_incidents() == []

    # false: wrong subject
    store3 = IncidentStore(_config_for_radar_guards())
    store3.ingest(
        _event(
            ts=ts,
            subject="UNKNOWN_CONTACT_CLOSE",
            payload={"id": track_id, "track_id": track_id, "range_m": 1.0},
        )
    )
    assert store3.list_incidents() == []


def test_spoofing_detected_true_false_borderline() -> None:
    store = IncidentStore(_config_for_radar_guards())
    ts = time.time()
    track_id = "trk-2"

    # true: mode == 3 (SPOOF)
    store.ingest(
        _event(
            ts=ts,
            subject="SPOOFING_DETECTED",
            payload={"id": track_id, "track_id": track_id, "transponder_mode": 3},
        )
    )
    incidents = store.list_incidents()
    assert len(incidents) == 1
    assert incidents[0].rule_id == "SPOOFING_DETECTED"

    # borderline: mode != 3 => should not match
    store2 = IncidentStore(_config_for_radar_guards())
    store2.ingest(
        _event(
            ts=ts,
            subject="SPOOFING_DETECTED",
            payload={"id": track_id, "track_id": track_id, "transponder_mode": 2},
        )
    )
    assert store2.list_incidents() == []

    # false: wrong source
    store3 = IncidentStore(_config_for_radar_guards())
    store3.ingest(
        _event(
            ts=ts,
            subject="SPOOFING_DETECTED",
            source="sensor",
            payload={"id": track_id, "track_id": track_id, "transponder_mode": 3},
        )
    )
    assert store3.list_incidents() == []


def test_incident_key_is_stable_and_updates_not_duplicates() -> None:
    store = IncidentStore(_config_for_radar_guards())
    ts = time.time()
    track_id = "trk-3"

    # First match creates incident with deterministic key that includes payload.id (track_id).
    store.ingest(
        _event(
            ts=ts,
            subject="FOE_TRANSPONDER_OFF_APPROACH",
            payload={"id": track_id, "track_id": track_id, "range_m": 10.0},
        )
    )
    incidents = store.list_incidents()
    assert len(incidents) == 1
    key = incidents[0].incident_id
    assert "FOE_TRANSPONDER_OFF_APPROACH" in key
    assert track_id in key
    assert incidents[0].count == 1

    # Second match on same track updates the same incident (count++).
    store.ingest(
        _event(
            ts=ts + 1.0,
            subject="FOE_TRANSPONDER_OFF_APPROACH",
            payload={"id": track_id, "track_id": track_id, "range_m": 9.0},
        )
    )
    incidents2 = store.list_incidents()
    assert len(incidents2) == 1
    assert incidents2[0].incident_id == key
    assert incidents2[0].count == 2

    # Different track_id => different incident.
    store.ingest(
        _event(
            ts=ts + 2.0,
            subject="FOE_TRANSPONDER_OFF_APPROACH",
            payload={"id": "trk-4", "track_id": "trk-4", "range_m": 9.0},
        )
    )
    assert len(store.list_incidents()) == 2
