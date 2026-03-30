from qiki.services.operator_console.orion_v.events_store import BoundedEventsStore


def test_bounded_store_keeps_latest_n() -> None:
    store = BoundedEventsStore(max_events=3)
    for i in range(5):
        store.append({"data": {"id": i}})

    last = store.last(10)
    assert [item["data"]["id"] for item in last] == [2, 3, 4]
    assert store.count() == 3


def test_active_incidents_filters_only_unacked_ca() -> None:
    store = BoundedEventsStore(max_events=10)
    store.append({"subject": "a", "data": {"incident_id": "i1", "severity": "C", "description": "crit"}})
    store.append({"subject": "a", "data": {"incident_id": "i2", "severity": "warning", "description": "warn"}})
    store.append({"subject": "a", "data": {"incident_id": "i3", "severity": "A", "acked": True}})

    incidents = store.active_incidents()
    assert [inc["id"] for inc in incidents] == ["i2", "i1"]
    assert [inc["severity"] for inc in incidents] == ["A", "C"]


def test_mark_acknowledged_and_clear_acknowledged() -> None:
    store = BoundedEventsStore(max_events=10)
    store.append(
        {
            "subject": "qiki.events.v1.audit",
            "data": {
                "incident_id": "inc-1",
                "severity": "critical",
                "description": "overheat",
            },
        }
    )
    store.append(
        {
            "subject": "qiki.events.v1.audit",
            "data": {
                "incident_id": "inc-2",
                "severity": "alarm",
                "description": "power",
            },
        }
    )

    assert store.mark_acknowledged("inc-1") is True
    incidents = store.active_incidents()
    assert [inc["id"] for inc in incidents] == ["inc-2"]

    assert store.clear_acknowledged() == 1
    assert store.count() == 1
    remaining = store.last(10)
    assert remaining[0]["data"]["incident_id"] == "inc-2"


def test_query_filters_by_severity_subsystem_and_time() -> None:
    store = BoundedEventsStore(max_events=20)
    store.append(
        {
            "subject": "qiki.events.v1.power.bus",
            "timestamp": "2026-02-26T10:00:00+00:00",
            "data": {"severity": "WARN", "message": "power warn"},
        }
    )
    store.append(
        {
            "subject": "qiki.events.v1.thermal.trip",
            "timestamp": "2026-02-26T10:00:10+00:00",
            "data": {"severity": "C", "message": "thermal crit"},
        }
    )
    store.append(
        {
            "subject": "qiki.events.v1.comms.link",
            "timestamp": "2026-02-26T10:00:20+00:00",
            "data": {"severity": "INFO", "message": "comms ok"},
        }
    )

    result = store.query(
        limit=10,
        severities={"C", "A"},
        subsystem="thermal",
        since_epoch_s=1_700_000_000.0,
    )
    assert len(result) == 1
    assert result[0]["subject"] == "qiki.events.v1.thermal.trip"


def test_query_supports_pagination() -> None:
    store = BoundedEventsStore(max_events=20)
    for idx in range(7):
        store.append(
            {
                "subject": f"qiki.events.v1.test.{idx}",
                "data": {"severity": "INFO", "message": f"m{idx}"},
            }
        )

    page1 = store.query(limit=3, offset=0)
    page2 = store.query(limit=3, offset=3)
    page3 = store.query(limit=3, offset=6)

    assert [item["subject"] for item in page1] == [
        "qiki.events.v1.test.6",
        "qiki.events.v1.test.5",
        "qiki.events.v1.test.4",
    ]
    assert [item["subject"] for item in page2] == [
        "qiki.events.v1.test.3",
        "qiki.events.v1.test.2",
        "qiki.events.v1.test.1",
    ]
    assert [item["subject"] for item in page3] == ["qiki.events.v1.test.0"]
