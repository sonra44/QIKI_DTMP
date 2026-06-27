from __future__ import annotations

import asyncio
import time
from uuid import UUID

import pytest

from qiki.services.operator_console.orion_v.app import OrionVApp, _parse_safe_mode_event, _trend_ascii
from qiki.services.operator_console.orion_v.screens.cockpit import OrionVCockpitScreen
from qiki.services.operator_console.orion_v.screens.deep_dive import OrionVDeepDiveScreen
from qiki.services.operator_console.orion_v.screens.evidence_stream import OrionVEvidenceScreen
from qiki.services.operator_console.orion_v.screens.systems import OrionVSystemsScreen
from qiki.services.operator_console.orion_v.widgets.evidence_card_view import OrionVEvidenceCard
from qiki.services.operator_console.orion_v.widgets.alerts_overlay import (
    OrionVAlertsOverlay,
    build_level0_alerts,
)
from qiki.services.operator_console.orion_v.hardware_view_model.types import (
    HardwareViewModel,
    SubsystemView,
    TelemetryField,
    ViewStatus,
)
from qiki.services.operator_console.orion_v.widgets.status_bars import OrionVStatusBars
from qiki.shared.models.qiki_chat import BilingualText, QikiChatResponseV1, QikiMode
from qiki.shared.nats_subjects import (
    EVENTS_AUDIT,
    EVENTS_STREAM_NAME,
    OPERATOR_ACTIONS,
    OPERATOR_INCIDENTS,
    OPERATOR_OBJECTIVES,
    OPERATOR_PROCEDURES,
)


class _TaskStub:
    def cancel(self) -> None:
        return


def _drop_task(coro):
    coro.close()
    return _TaskStub()


def _field(key: str, label: str, value: object, unit: str, status: ViewStatus) -> TelemetryField:
    return TelemetryField(
        key=key,
        label=label,
        value=value,
        unit=unit,
        status=status,
        hint="",
        ts=None,
    )


def test_ack_incident_marks_event_and_sets_message(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    app._incident_first_seen["inc-42"] = time.time() - 1.0

    app._events_store.append(
        {
            "subject": "qiki.events.v1.audit",
            "data": {
                "incident_id": "inc-42",
                "severity": "C",
                "description": "critical",
            },
        }
    )

    monkeypatch.setattr(app, "_refresh_ui", lambda: None)
    monkeypatch.setattr(app, "_set_help_text", lambda text: messages.append(text))
    monkeypatch.setattr(asyncio, "create_task", _drop_task)

    app._ack_incident("inc-42")

    incidents = app._events_store.active_incidents()
    assert incidents == []
    assert "inc-42" not in app._incident_first_seen
    assert messages[-1] == "Подтверждено: inc-42"


def test_clear_acknowledged_incidents_removes_entries(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    app._incident_first_seen["inc-1"] = time.time() - 1.0
    app._incident_first_seen["inc-2"] = time.time() - 1.0

    app._events_store.append(
        {
            "subject": "qiki.events.v1.audit",
            "data": {
                "incident_id": "inc-1",
                "severity": "A",
                "description": "alarm",
                "acked": True,
            },
        }
    )
    app._events_store.append(
        {
            "subject": "qiki.events.v1.audit",
            "data": {
                "incident_id": "inc-2",
                "severity": "C",
                "description": "critical",
            },
        }
    )

    monkeypatch.setattr(app, "_refresh_ui", lambda: None)
    monkeypatch.setattr(app, "_set_help_text", lambda text: messages.append(text))
    monkeypatch.setattr(asyncio, "create_task", _drop_task)

    app._clear_acknowledged_incidents()

    assert app._events_store.count() == 1
    assert app._events_store.last(1)[0]["data"]["incident_id"] == "inc-2"
    assert "inc-1" not in app._incident_first_seen
    assert "inc-2" in app._incident_first_seen
    assert messages[-1] == "Снято подтвержденных инцидентов: 1"


def test_build_objective_timeline_lines_matches_objective_and_linked_events() -> None:
    app = OrionVApp()
    app._active_observation_objective = {
        "objective_id": "observation-123",
        "proposal_id": "proposal-123",
        "request_id": "request-123",
        "procedure_name": "safe_pause_slow_resume",
        "target_designator": "ALLY-4D1ED5",
        "route_role": "deviation",
    }
    app._events_store.append(
        {
            "subject": OPERATOR_OBJECTIVES,
            "data": {
                "objective_id": "observation-123",
                "status": "prepared",
                "summary_ru": "Observation-цель подготовлена.",
            },
        }
    )
    app._events_store.append(
        {
            "subject": EVENTS_AUDIT,
            "data": {
                "proposal_id": "proposal-123",
                "event_type": "HIDDEN_EVENT_REVEALED",
                "message": "Off-route выбор раскрыл скрытую аномалию.",
            },
        }
    )
    app._events_store.append(
        {
            "subject": EVENTS_AUDIT,
            "data": {
                "proposal_id": "proposal-999",
                "event_type": "IGNORED",
                "message": "Это событие не связано с objective.",
            },
        }
    )

    lines = app._build_objective_timeline_lines(app._events_store)

    assert lines == [
        "audit | HIDDEN_EVENT_REVEALED | Off-route выбор раскрыл скрытую аномалию.",
        "objectives | prepared | Observation-цель подготовлена.",
    ]


@pytest.mark.asyncio
async def test_ack_incident_publishes_incident_ack_audit_event() -> None:
    app = OrionVApp()
    published: list[tuple[str, dict[str, object]]] = []

    async def publish_audit(subject: str, payload: dict[str, object]) -> None:
        published.append((subject, payload))

    app._publish_audit_event = publish_audit  # type: ignore[method-assign]
    app._set_help_text = lambda _: None  # type: ignore[method-assign]
    app._refresh_ui = lambda: None  # type: ignore[method-assign]
    app._events_store.append(
        {
            "subject": "qiki.events.v1.audit",
            "data": {"incident_id": "inc-ack-1", "severity": "C", "description": "critical"},
        }
    )

    app._ack_incident("inc-ack-1")
    await asyncio.sleep(0)

    row = published[-1]
    assert row[0] == OPERATOR_INCIDENTS
    assert row[1]["kind"] == "incident_ack"
    assert row[1]["incident_id"] == "inc-ack-1"
    assert row[1]["ok"] is True
    assert isinstance(row[1]["ack_time_ms"], float)


@pytest.mark.asyncio
async def test_app_mounts_named_top_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)
    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()

        header = app.query_one("#orionv-header")
        safety_strip = app.query_one("#orionv-safety-strip")
        actions = app.query_one("#orionv-actions")
        bars = app.query_one("#orionv-bars")
        overlay = app.query_one("#orionv-overlay")
        command_strip = app.query_one("#orionv-command-strip")
        command = app.query_one("#orionv-command")
        command_shell = app.query_one("#orionv-command-shell")
        command_open = app.query_one("#orionv-command-open")

        assert header.border_title == "MISSION CONTROL STRIP"
        assert safety_strip.border_title == "SAFETY & HEALTH STRIP"
        assert actions.border_title == "ACTION RAIL"
        assert bars.border_title is None
        assert overlay.border_title is None
        assert command_strip.id == "orionv-command-strip"
        assert command.border_title == "ВВОД/INPUT"
        assert command.has_class("hidden") is True
        assert command_shell.has_class("hidden") is False
        assert command_open.has_class("hidden") is False


@pytest.mark.asyncio
async def test_command_mode_opens_and_closes_without_persistent_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)
    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()

        command = app.query_one("#orionv-command")
        command_shell = app.query_one("#orionv-command-shell")
        command_open = app.query_one("#orionv-command-open")

        assert command.has_class("hidden") is True
        app.action_open_command_mode()
        await pilot.pause()

        assert command.has_class("hidden") is False
        assert command_shell.has_class("hidden") is True
        assert command_open.has_class("hidden") is True

        app.action_close_command_mode()
        await pilot.pause()

        assert command.has_class("hidden") is True
        assert command_shell.has_class("hidden") is False
        assert command_open.has_class("hidden") is False
        assert app.focused is not command


@pytest.mark.asyncio
async def test_evidence_level_renders_nbl_card_from_live_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)
    app = OrionVApp()
    app._snapshot = {"power": {"nbl_active": True, "nbl_allowed": False, "nbl_budget_w": 0.0}}

    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()

        app.action_show_level("f8")
        await pilot.pause()

        evidence = app.query_one("#orionv-evidence", OrionVEvidenceScreen)
        assert evidence.has_class("hidden") is False
        assert app.query_one("#orionv-cockpit").has_class("hidden") is True

        cards = evidence.query(OrionVEvidenceCard)
        assert len(cards) == 1
        rendered = str(cards.first().render())
        assert "NBL_NOT_IMPLEMENTED" in rendered
        assert "NBL_RULES_ONLY" in rendered
        assert "NBL_PDU_DENIED" in rendered

        app._snapshot = {}
        app._refresh_ui()
        await pilot.pause()

        cards = evidence.query(OrionVEvidenceCard)
        assert len(cards) == 1
        assert "NBL_PDU_DENIED" not in str(cards.first().render())


@pytest.mark.asyncio
async def test_clear_acknowledged_incidents_publishes_incident_clear_audit_event() -> None:
    app = OrionVApp()
    published: list[tuple[str, dict[str, object]]] = []

    async def publish_audit(subject: str, payload: dict[str, object]) -> None:
        published.append((subject, payload))

    app._publish_audit_event = publish_audit  # type: ignore[method-assign]
    app._set_help_text = lambda _: None  # type: ignore[method-assign]
    app._refresh_ui = lambda: None  # type: ignore[method-assign]
    app._events_store.append(
        {
            "subject": "qiki.events.v1.audit",
            "data": {
                "incident_id": "inc-clear-1",
                "severity": "A",
                "description": "alarm",
                "acked": True,
            },
        }
    )

    app._clear_acknowledged_incidents()
    await asyncio.sleep(0)

    row = published[-1]
    assert row[0] == OPERATOR_INCIDENTS
    assert row[1]["kind"] == "incident_clear"
    assert row[1]["ok"] is True


def test_event_filter_commands_update_state(monkeypatch) -> None:
    app = OrionVApp()
    monkeypatch.setattr(app, "_refresh_ui", lambda: None)
    monkeypatch.setattr(app, "_set_help_text", lambda _text: None)

    app._set_severity_filter("warn,c")
    app._set_subsystem_filter("thermal")
    app._set_time_filter("120")

    assert app._filter_severities == {"WARN", "C"}
    assert app._filter_subsystem == "thermal"
    assert app._filter_window_sec == 120

    app._set_severity_filter("all")
    app._set_subsystem_filter("all")
    app._set_time_filter("all")

    assert app._filter_severities == set()
    assert app._filter_subsystem is None
    assert app._filter_window_sec is None


@pytest.mark.asyncio
async def test_on_event_tracks_latest_observation_objective(monkeypatch) -> None:
    app = OrionVApp()
    refresh_calls: list[str] = []
    monkeypatch.setattr(app, "_request_refresh_ui", lambda: refresh_calls.append("refresh"))

    await app._on_event(
        {
            "subject": OPERATOR_OBJECTIVES,
            "timestamp": "2026-03-07T00:00:00+00:00",
            "data": {
                "objective_id": "observation-123",
                "status": "prepared",
                "observation_style": "safe",
                "procedure_name": "safe_pause_resume",
                "target_designator": "AST44995",
            },
        }
    )

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["objective_id"] == "observation-123"
    assert app._active_observation_objective["target_designator"] == "AST44995"
    assert refresh_calls == ["refresh"]


@pytest.mark.asyncio
async def test_hydrate_last_observation_objective_from_jetstream(monkeypatch) -> None:
    app = OrionVApp()
    refresh_calls: list[str] = []
    monkeypatch.setattr(app, "_request_refresh_ui", lambda: refresh_calls.append("refresh"))

    class _FakeNatsClient:
        async def fetch_last_event_json(self, *, stream: str, subject: str):  # noqa: ANN001
            assert stream == EVENTS_STREAM_NAME
            assert subject == OPERATOR_OBJECTIVES
            return {
                "event_schema_version": 1,
                "source": "q_core_intents",
                "subject": OPERATOR_OBJECTIVES,
                "timestamp": "2026-03-13T12:00:00+00:00",
                "objective_id": "observation-jetstream-1",
                "objective_type": "observation",
                "status": "prepared",
                "observation_style": "safe",
                "procedure_name": "safe_pause_resume",
                "route_role": "official",
                "target_designator": "AST44995",
            }

    app._nats_client = _FakeNatsClient()  # type: ignore[assignment]

    await app._hydrate_last_observation_objective_from_jetstream()

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["objective_id"] == "observation-jetstream-1"
    assert app._active_observation_objective["route_role"] == "official"
    assert app._events_store.last(1)[0]["subject"] == OPERATOR_OBJECTIVES
    assert refresh_calls == ["refresh"]


@pytest.mark.asyncio
async def test_publish_observation_objective_update_updates_local_state_and_bus(monkeypatch) -> None:
    app = OrionVApp()
    refresh_calls: list[str] = []
    published: list[tuple[str, dict[str, object]]] = []
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": OPERATOR_OBJECTIVES,
        "timestamp": "2026-03-07T00:00:00+00:00",
        "ts_epoch": 1.0,
        "kind": "observation_objective_seed",
        "objective_id": "observation-123",
        "objective_type": "observation",
        "status": "prepared",
        "observation_style": "safe",
        "procedure_name": "safe_pause_resume",
        "request_id": "req-1",
        "proposal_id": "prop-1",
        "mode": "FACTORY",
        "target_designator": "ALLY-4D1ED5",
        "track_visible": True,
        "title_ru": "Безопасное наблюдение готово",
        "title_en": "Safe observation ready",
        "summary_ru": "Процедура подготовлена.",
        "summary_en": "Procedure prepared.",
        "reason_code": "SAFE_OBSERVATION_PROCEDURE_READY",
    }
    monkeypatch.setattr(app, "_request_refresh_ui", lambda: refresh_calls.append("refresh"))

    async def publish_event(subject: str, payload: dict[str, object]) -> None:
        published.append((subject, payload))

    app._publish_operator_event = publish_event  # type: ignore[method-assign]

    await app._publish_observation_objective_update(
        status="confirmed",
        summary_en="The observation objective completed and its telemetry consequence is confirmed.",
        summary_ru="Observation-цель завершена, и её телеметрический эффект подтверждён.",
        reason_code="OBJECTIVE_CONFIRMED",
        procedure_name="safe_pause_resume",
    )

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["kind"] == "observation_objective_update"
    assert app._active_observation_objective["status"] == "confirmed"
    assert app._active_observation_objective["source"] == "orion_v"
    assert published[-1][0] == OPERATOR_OBJECTIVES
    assert published[-1][1]["status"] == "confirmed"
    assert published[-1][1]["kind"] == "observation_objective_update"
    assert refresh_calls == ["refresh"]


@pytest.mark.asyncio
async def test_publish_observation_objective_update_adds_hidden_event_follow_up(monkeypatch) -> None:
    app = OrionVApp()
    refresh_calls: list[str] = []
    published: list[tuple[str, dict[str, object]]] = []
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": OPERATOR_OBJECTIVES,
        "timestamp": "2026-03-07T00:00:00+00:00",
        "ts_epoch": 1.0,
        "kind": "observation_objective_seed",
        "objective_id": "observation-123",
        "objective_type": "observation",
        "status": "prepared",
        "observation_style": "slow",
        "procedure_name": "safe_pause_slow_resume",
        "route_role": "deviation",
        "request_id": "req-1",
        "proposal_id": "prop-1",
        "mode": "FACTORY",
        "target_designator": "ALLY-4D1ED5",
        "track_visible": True,
        "title_ru": "Медленное наблюдение готово",
        "title_en": "Slow observation ready",
        "summary_ru": "Процедура подготовлена.",
        "summary_en": "Procedure prepared.",
        "reason_code": "SLOW_OBSERVATION_PROCEDURE_READY",
        "follow_up_status": "review_required",
        "follow_up_reason_code": "HIDDEN_EVENT_REVIEW_REQUIRED",
        "follow_up_event_type": "HIDDEN_EVENT_REVEALED",
        "follow_up_summary_en": "Hidden-event follow-up is required.",
        "follow_up_summary_ru": "Нужен follow-up по скрытому событию.",
        "follow_up_allowed_when_en": "Review the linked hidden fact before issuing the next observation objective.",
        "follow_up_allowed_when_ru": (
            "Сначала проверьте связанный hidden fact, "
            "затем задавайте следующую observation-цель."
        ),
    }
    app._events_store.append(
        {
            "subject": EVENTS_AUDIT,
            "data": {
                "proposal_id": "prop-1",
                "objective_id": "observation-123",
                "event_type": "HIDDEN_EVENT_REVEALED",
                "procedure_name": "safe_pause_slow_resume",
                "target_designator": "ALLY-4D1ED5",
                "route_role": "deviation",
                "message": "Deviation route revealed a hidden fact.",
            },
        }
    )
    monkeypatch.setattr(app, "_request_refresh_ui", lambda: refresh_calls.append("refresh"))

    async def publish_event(subject: str, payload: dict[str, object]) -> None:
        published.append((subject, payload))

    app._publish_operator_event = publish_event  # type: ignore[method-assign]

    await app._publish_observation_objective_update(
        status="confirmed",
        summary_en="The observation objective completed and its telemetry consequence is confirmed.",
        summary_ru="Observation-цель завершена, и её телеметрический эффект подтверждён.",
        reason_code="OBJECTIVE_CONFIRMED",
        procedure_name="safe_pause_slow_resume",
    )

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["follow_up_status"] == "review_required"
    assert app._active_observation_objective["follow_up_reason_code"] == "HIDDEN_EVENT_REVIEW_REQUIRED"
    assert app._active_observation_objective["follow_up_event_type"] == "HIDDEN_EVENT_REVEALED"
    assert "hidden" in str(app._active_observation_objective["follow_up_summary_en"]).lower()
    assert published[-1][0] == OPERATOR_OBJECTIVES
    assert published[-1][1]["follow_up_status"] == "review_required"
    assert refresh_calls == ["refresh"]


@pytest.mark.asyncio
async def test_publish_observation_objective_update_marks_review_completed_after_ack(monkeypatch) -> None:
    app = OrionVApp()
    refresh_calls: list[str] = []
    published: list[tuple[str, dict[str, object]]] = []
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "orion_v",
        "subject": OPERATOR_OBJECTIVES,
        "timestamp": "2026-03-07T00:00:00+00:00",
        "ts_epoch": 1.0,
        "kind": "observation_objective_update",
        "objective_id": "observation-123",
        "objective_type": "observation",
        "status": "confirmed",
        "observation_style": "slow",
        "procedure_name": "safe_pause_slow_resume",
        "route_role": "deviation",
        "request_id": "req-1",
        "proposal_id": "prop-1",
        "mode": "FACTORY",
        "target_designator": "ALLY-4D1ED5",
        "track_visible": True,
        "title_ru": "Наблюдение завершено",
        "title_en": "Observation complete",
        "summary_ru": "Observation-цель завершена.",
        "summary_en": "Observation complete.",
        "reason_code": "OBJECTIVE_CONFIRMED",
        "follow_up_status": "review_completed",
        "follow_up_reason_code": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
        "follow_up_event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
        "follow_up_summary_en": "Hidden-event review is closed and one post-review follow-up choice is open.",
        "follow_up_summary_ru": "Review скрытого события закрыт, и один post-review follow-up choice открыт.",
        "follow_up_allowed_when_en": (
            "Select the post-review follow-up choice before issuing the next observation objective."
        ),
        "follow_up_allowed_when_ru": (
            "Сначала выберите post-review follow-up choice, "
            "затем задавайте следующую observation-цель."
        ),
    }
    app._events_store.append(
        {
            "subject": EVENTS_AUDIT,
            "data": {
                "proposal_id": "prop-1",
                "objective_id": "observation-123",
                "event_type": "HIDDEN_EVENT_REVEALED",
                "procedure_name": "safe_pause_slow_resume",
                "target_designator": "ALLY-4D1ED5",
                "route_role": "deviation",
                "message": "Deviation route revealed a hidden fact.",
            },
        }
    )
    app._audit_store.append(
        {
            "subject": OPERATOR_ACTIONS,
            "data": {
                "proposal_id": "prop-1",
                "objective_id": "observation-123",
                "event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
                "procedure_name": "safe_pause_slow_resume",
                "target_designator": "ALLY-4D1ED5",
                "route_role": "deviation",
                "message": "Operator reviewed the linked hidden fact.",
            },
        }
    )
    monkeypatch.setattr(app, "_request_refresh_ui", lambda: refresh_calls.append("refresh"))

    async def publish_event(subject: str, payload: dict[str, object]) -> None:
        published.append((subject, payload))

    app._publish_operator_event = publish_event  # type: ignore[method-assign]

    await app._publish_observation_objective_update(
        status="confirmed",
        summary_en="The hidden-event review closure is confirmed on the existing observation path.",
        summary_ru="Closure review скрытого события подтверждён на существующем observation path.",
        reason_code="OBJECTIVE_REVIEW_CLOSED",
        procedure_name="safe_pause_slow_resume",
    )

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["follow_up_status"] == "review_completed"
    assert app._active_observation_objective["follow_up_reason_code"] == "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED"
    assert app._active_observation_objective["follow_up_event_type"] == "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED"
    assert "follow-up choice is open" in str(app._active_observation_objective["follow_up_summary_en"]).lower()
    assert published[-1][0] == OPERATOR_OBJECTIVES
    assert published[-1][1]["follow_up_status"] == "review_completed"
    assert refresh_calls == ["refresh"]


@pytest.mark.asyncio
async def test_ack_observation_review_uses_follow_up_contract_when_hidden_event_scrolled_out(monkeypatch) -> None:
    app = OrionVApp()
    help_messages: list[str] = []
    published: list[dict[str, object]] = []
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "orion_v",
        "subject": OPERATOR_OBJECTIVES,
        "timestamp": "2026-03-13T00:00:00+00:00",
        "ts_epoch": 1.0,
        "kind": "observation_objective_update",
        "objective_id": "observation-123",
        "objective_type": "observation",
        "status": "confirmed",
        "observation_style": "slow",
        "procedure_name": "safe_pause_slow_resume",
        "route_role": "deviation",
        "request_id": "req-1",
        "proposal_id": "prop-1",
        "mode": "FACTORY",
        "target_designator": "ALLY-4D1ED5",
        "track_visible": True,
        "title_ru": "Наблюдение завершено",
        "title_en": "Observation complete",
        "summary_ru": "Observation-цель завершена.",
        "summary_en": "Observation complete.",
        "reason_code": "OBJECTIVE_CONFIRMED",
        "follow_up_status": "review_required",
        "follow_up_reason_code": "HIDDEN_EVENT_REVIEW_REQUIRED",
        "follow_up_event_type": "HIDDEN_EVENT_REVEALED",
        "follow_up_summary_en": "Hidden-event follow-up is required.",
        "follow_up_summary_ru": "Нужен follow-up по скрытому событию.",
        "follow_up_allowed_when_en": "Review the linked hidden fact before issuing the next observation objective.",
        "follow_up_allowed_when_ru": (
            "Сначала проверьте связанный hidden fact, "
            "затем задавайте следующую observation-цель."
        ),
    }
    for index in range(45):
        app._events_store.append(
            {
                "subject": EVENTS_AUDIT,
                "data": {
                    "event_type": f"NOISE_EVENT_{index}",
                    "objective_id": f"noise-{index}",
                },
            }
        )
    monkeypatch.setattr(app, "_set_help_text", lambda text: help_messages.append(text))
    monkeypatch.setattr(app, "_request_refresh_ui", lambda: None)

    async def publish_action(payload: dict[str, object]) -> None:
        published.append(payload)

    app._publish_operator_action = publish_action  # type: ignore[method-assign]

    await app._ack_observation_review()

    assert help_messages[-1] == "Review action published: waiting for canonical follow-up update"
    assert published[-1]["event_type"] == "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED"
    assert published[-1]["objective_id"] == "observation-123"
    assert published[-1]["proposal_id"] == "prop-1"
    assert published[-1]["request_id"] == "req-1"
    assert published[-1]["procedure_name"] == "safe_pause_slow_resume"
    assert published[-1]["target_designator"] == "ALLY-4D1ED5"
    assert published[-1]["route_role"] == "deviation"


@pytest.mark.asyncio
async def test_publish_observation_objective_update_marks_post_review_hold_after_choice(monkeypatch) -> None:
    app = OrionVApp()
    refresh_calls: list[str] = []
    published: list[tuple[str, dict[str, object]]] = []
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "orion_v",
        "subject": OPERATOR_OBJECTIVES,
        "timestamp": "2026-03-07T00:00:00+00:00",
        "ts_epoch": 1.0,
        "kind": "observation_objective_update",
        "objective_id": "observation-123",
        "objective_type": "observation",
        "status": "confirmed",
        "observation_style": "slow",
        "procedure_name": "safe_pause_slow_resume",
        "route_role": "deviation",
        "request_id": "req-1",
        "proposal_id": "prop-1",
        "mode": "FACTORY",
        "target_designator": "ALLY-4D1ED5",
        "track_visible": True,
        "title_ru": "Наблюдение завершено",
        "title_en": "Observation complete",
        "summary_ru": "Observation-цель завершена.",
        "summary_en": "Observation complete.",
        "reason_code": "OBJECTIVE_REVIEW_CLOSED",
        "follow_up_status": "hold_for_recheck",
        "follow_up_reason_code": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
        "follow_up_event_type": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
        "follow_up_summary_en": "Post-review hold for recheck is selected on the cautious recheck contour.",
        "follow_up_summary_ru": "Выбран post-review hold for recheck на осторожном recheck-контуре.",
        "follow_up_allowed_when_en": (
            "Run a cautious safe recheck for the same target before resuming the next general observation objective."
        ),
        "follow_up_allowed_when_ru": (
            "Сначала выполните осторожный safe recheck для той же цели, "
            "затем возвращайтесь к следующей общей observation-цели."
        ),
    }
    app._events_store.append(
        {
            "subject": EVENTS_AUDIT,
            "data": {
                "proposal_id": "prop-1",
                "objective_id": "observation-123",
                "event_type": "HIDDEN_EVENT_REVEALED",
                "procedure_name": "safe_pause_slow_resume",
                "target_designator": "ALLY-4D1ED5",
                "route_role": "deviation",
                "message": "Deviation route revealed a hidden fact.",
            },
        }
    )
    app._audit_store.append(
        {
            "subject": OPERATOR_ACTIONS,
            "data": {
                "proposal_id": "prop-1",
                "objective_id": "observation-123",
                "event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
                "procedure_name": "safe_pause_slow_resume",
                "target_designator": "ALLY-4D1ED5",
                "route_role": "deviation",
                "message": "Operator reviewed the linked hidden fact.",
            },
        }
    )
    app._audit_store.append(
        {
            "subject": OPERATOR_ACTIONS,
            "data": {
                "proposal_id": "prop-1",
                "objective_id": "observation-123",
                "event_type": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
                "procedure_name": "safe_pause_slow_resume",
                "target_designator": "ALLY-4D1ED5",
                "route_role": "deviation",
                "message": "Operator selected hold for recheck.",
            },
        }
    )
    monkeypatch.setattr(app, "_request_refresh_ui", lambda: refresh_calls.append("refresh"))

    async def publish_event(subject: str, payload: dict[str, object]) -> None:
        published.append((subject, payload))

    app._publish_operator_event = publish_event  # type: ignore[method-assign]

    await app._publish_observation_objective_update(
        status="confirmed",
        summary_en="The post-review hold for recheck is selected on the existing observation path.",
        summary_ru="Post-review hold for recheck выбран на существующем observation path.",
        reason_code="OBJECTIVE_POST_REVIEW_HOLD_SELECTED",
        procedure_name="safe_pause_slow_resume",
    )

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["follow_up_status"] == "hold_for_recheck"
    assert app._active_observation_objective["follow_up_reason_code"] == "HIDDEN_EVENT_RECHECK_HOLD_SELECTED"
    assert app._active_observation_objective["follow_up_event_type"] == "HIDDEN_EVENT_RECHECK_HOLD_SELECTED"
    assert "recheck contour" in str(app._active_observation_objective["follow_up_summary_en"]).lower()
    assert published[-1][0] == OPERATOR_OBJECTIVES
    assert published[-1][1]["follow_up_status"] == "hold_for_recheck"
    assert refresh_calls == ["refresh"]


@pytest.mark.asyncio
async def test_execute_qiki_pending_procedure_emits_failed_objective_update(monkeypatch) -> None:
    app = OrionVApp()
    published: list[tuple[str, dict[str, object]]] = []
    messages: list[str] = []
    app._qiki_pending_action = {"action_kind": "ORION_PROCEDURE", "name": "safe_pause_resume"}
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": OPERATOR_OBJECTIVES,
        "timestamp": "2026-03-07T00:00:00+00:00",
        "ts_epoch": 1.0,
        "kind": "observation_objective_seed",
        "objective_id": "observation-123",
        "objective_type": "observation",
        "status": "prepared",
        "observation_style": "safe",
        "procedure_name": "safe_pause_resume",
        "request_id": "req-1",
        "proposal_id": "prop-1",
        "mode": "FACTORY",
        "target_designator": "ALLY-4D1ED5",
        "track_visible": True,
        "title_ru": "Безопасное наблюдение готово",
        "title_en": "Safe observation ready",
        "summary_ru": "Процедура подготовлена.",
        "summary_en": "Procedure prepared.",
        "reason_code": "SAFE_OBSERVATION_PROCEDURE_READY",
    }
    app._qiki_last_response = QikiChatResponseV1(
        request_id=UUID("12345678-1234-5678-1234-567812345678"),
        ok=True,
        mode=QikiMode.FACTORY,
        consequence=None,
        proposals=[],
        warnings=[],
        reply=None,
        legality=None,
        trust_signals=[],
        error=None,
    )

    async def publish_event(subject: str, payload: dict[str, object]) -> None:
        published.append((subject, payload))

    async def run_procedure(_name: str) -> None:
        return None

    monkeypatch.setattr(app, "_publish_operator_event", publish_event)
    monkeypatch.setattr(app, "_run_procedure", run_procedure)
    monkeypatch.setattr(app, "_wait_for_procedure_completion", lambda _name, _timeout: asyncio.sleep(0, result=False))
    monkeypatch.setattr(app, "_request_refresh_ui", lambda: None)
    monkeypatch.setattr(app, "_set_help_text", lambda text: messages.append(text))

    await app._execute_qiki_pending_procedure("safe_pause_resume")

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["kind"] == "observation_objective_update"
    assert app._active_observation_objective["status"] == "failed"
    assert app._active_observation_objective["reason_code"] == "OBJECTIVE_PROCEDURE_FAILED"
    assert published[-1][0] == OPERATOR_OBJECTIVES
    assert published[-1][1]["status"] == "failed"
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "failed"
    assert app._qiki_last_response.consequence.summary == BilingualText(
        en="The prepared ORION procedure did not finish successfully.",
        ru="Подготовленная процедура ORION не завершилась успешно.",
    )
    assert app._qiki_pending_action is None
    assert messages[-1] == "QIKI execution failed: процедура safe_pause_resume"


def test_cancel_qiki_pending_action_emits_cancelled_objective_update(monkeypatch) -> None:
    app = OrionVApp()
    statuses: list[str] = []
    app._qiki_pending_action = {"action_kind": "ORION_PROCEDURE", "name": "safe_pause_resume"}
    app._active_observation_objective = {
        "objective_id": "observation-123",
        "objective_type": "observation",
        "procedure_name": "safe_pause_resume",
        "status": "prepared",
    }

    async def publish_update(**kwargs):  # type: ignore[no-untyped-def]
        statuses.append(str(kwargs["status"]))

    def _run_task(coro):
        asyncio.run(coro)
        return _TaskStub()

    monkeypatch.setattr(app, "_publish_observation_objective_update", publish_update)
    monkeypatch.setattr(asyncio, "create_task", _run_task)
    monkeypatch.setattr(app, "_request_refresh_ui", lambda: None)
    monkeypatch.setattr(app, "_set_help_text", lambda _: None)

    app._cancel_qiki_pending_action()

    assert statuses == ["cancelled"]
    assert app._qiki_pending_action is None


def test_events_page_navigation(monkeypatch) -> None:
    app = OrionVApp()
    monkeypatch.setattr(app, "_refresh_ui", lambda: None)

    app.action_events_page_next()
    app.action_events_page_next()
    assert app._events_page == 2

    app.action_events_page_prev()
    app.action_events_page_prev()
    app.action_events_page_prev()
    assert app._events_page == 0


def test_replay_guardrails_block_controls(monkeypatch) -> None:
    app = OrionVApp()
    app._replay_mode = True
    messages: list[str] = []

    monkeypatch.setattr(app, "_set_help_text", lambda text: messages.append(text))

    app.action_ack_selected_incident()
    app.action_clear_acknowledged_incidents()
    app._start_procedure("safe_pause_resume")

    assert messages
    assert messages[-1] == "РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО"
    assert app._procedure_task is None


def test_action_ack_incident_selects_then_uses_confirm_path(monkeypatch: pytest.MonkeyPatch) -> None:
    app = OrionVApp()
    callbacks = []
    acked: list[str] = []

    monkeypatch.setattr(app, "push_screen", lambda _dialog, callback: callbacks.append(callback))
    monkeypatch.setattr(app, "_ack_incident", lambda incident_id: acked.append(incident_id))

    app.action_ack_incident(" inc-click ")

    assert app._selected_incident_id == "inc-click"
    assert callbacks
    assert acked == []

    callbacks[0](True)

    assert acked == ["inc-click"]


def test_action_ack_incident_replay_guard_blocks_without_selection_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = OrionVApp()
    app._replay_mode = True
    app._selected_incident_id = "inc-old"
    messages: list[str] = []

    monkeypatch.setattr(app, "_set_help_text", lambda text: messages.append(text))

    app.action_ack_incident("inc-new")

    assert app._selected_incident_id == "inc-old"
    assert messages[-1] == "РЕЖИМ АНАЛИЗА ИСТОРИИ — УПРАВЛЕНИЕ ОТКЛЮЧЕНО"


def test_audit_publish_routes_by_subject() -> None:
    app = OrionVApp()
    published: list[tuple[str, dict]] = []

    class _StubNats:
        async def publish_command(self, subject: str, payload: dict) -> None:
            published.append((subject, payload))

    app._nats_client = _StubNats()  # type: ignore[assignment]

    asyncio.run(app._publish_operator_action({"kind": "level_switch", "action_type": "actions"}))
    asyncio.run(app._publish_procedure_audit({"kind": "procedure_step"}))

    assert len(published) == 2
    assert published[0][0] == OPERATOR_ACTIONS
    assert published[1][0] == OPERATOR_PROCEDURES
    assert app._audit_store.count() == 2


def test_wait_for_ack_ignores_stale_command_id() -> None:
    app = OrionVApp()
    started = time.monotonic()
    app._pending_ack_command_id = "req-current"
    app._ack_wait_started_mono = started
    app._control_acks.append(
        {
            "_received_mono": started + 0.01,
            "data": {
                "ok": True,
                "kind": "sim.pause",
                "request_id": "req-old",
                "payload": {"command_name": "sim.pause", "status": "applied"},
            },
        }
    )

    ok = asyncio.run(app._wait_for_ack("sim.pause", 0.05))

    assert ok is False


def test_publish_sim_command_clears_ack_queue_and_waits_for_matching_id(monkeypatch) -> None:
    app = OrionVApp()
    app._control_acks.append({"data": {"ok": True, "request_id": "stale"}})
    published: list[dict] = []

    class _StubNats:
        async def publish_command(self, _subject: str, payload: dict) -> None:
            published.append(payload)

    app._nats_client = _StubNats()  # type: ignore[assignment]
    monkeypatch.setattr("qiki.services.operator_console.orion_v.app.uuid4", lambda: UUID(int=1))

    async def run() -> bool:
        await app._publish_sim_command("sim.pause")
        assert len(app._control_acks) == 0
        assert app._pending_ack_command_id == str(UUID(int=1))
        app._control_acks.append(
            {
                "_received_mono": time.monotonic(),
                "data": {
                    "ok": True,
                    "kind": "sim.pause",
                    "request_id": "wrong-id",
                    "payload": {"command_name": "sim.pause", "status": "applied"},
                },
            }
        )
        app._control_acks.append(
            {
                "_received_mono": time.monotonic(),
                "data": {
                    "ok": True,
                    "kind": "sim.pause",
                    "request_id": str(UUID(int=1)),
                    "payload": {"command_name": "sim.pause", "status": "applied"},
                },
            }
        )
        return await app._wait_for_ack("sim.pause", 0.2)

    ack_ok = asyncio.run(run())

    assert len(published) == 1
    assert ack_ok is True


def test_parse_safe_mode_event_enter_from_fsm_transition() -> None:
    parsed = _parse_safe_mode_event(
        subject="qiki.events.v1.fsm",
        payload={
            "subsystem": "FSM",
            "event_type": "FSM_TRANSITION",
            "to_state": "SAFE_MODE",
            "trigger_event": "SAFE_MODE_ENTER_SENSORS_STALE",
        },
    )
    assert parsed is not None
    assert parsed["active"] is True
    assert "SAFE_MODE_ENTER" in str(parsed["reason"])


def test_parse_safe_mode_event_exit_from_safe_mode_signal() -> None:
    parsed = _parse_safe_mode_event(
        subject="qiki.events.v1.safe_mode",
        payload={
            "subsystem": "SAFE_MODE",
            "event_type": "SAFE_MODE",
            "action": "exit",
            "reason": "SAFE_MODE_EXIT_CONFIRMED",
        },
    )
    assert parsed is not None
    assert parsed["active"] is False
    assert parsed["reason"] == "SAFE_MODE_EXIT_CONFIRMED"


def test_on_event_updates_safe_mode_state() -> None:
    app = OrionVApp()
    asyncio.run(
        app._on_event(
            {
                "subject": "qiki.events.v1.fsm",
                "data": {
                    "subsystem": "FSM",
                    "event_type": "FSM_TRANSITION",
                    "to_state": "SAFE_MODE",
                    "trigger_event": "SAFE_MODE_ENTER_BIOS_UNAVAILABLE",
                },
            }
        )
    )
    assert app._safe_mode_state["active"] is True
    assert "SAFE_MODE_ENTER_BIOS_UNAVAILABLE" in str(app._safe_mode_state["reason"])


@pytest.mark.asyncio
async def test_safe_mode_event_updates_f2_f3_via_refresh_ui(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()

        await app._on_event(
            {
                "subject": "qiki.events.v1.fsm",
                "data": {
                    "subsystem": "FSM",
                    "event_type": "FSM_TRANSITION",
                    "to_state": "SAFE_MODE",
                    "trigger_event": "SAFE_MODE_ENTER_TEST",
                },
            }
        )
        await pilot.pause()

        systems = app.query_one("#orionv-systems", OrionVSystemsScreen)
        deep = app.query_one("#orionv-deep", OrionVDeepDiveScreen)
        assert systems._safe_mode.get("active") is True
        assert deep._safe_mode.get("active") is True
        assert "SAFE_MODE_ENTER_TEST" in str(deep._safe_mode.get("reason"))

        await app._on_event(
            {
                "subject": "qiki.events.v1.safe_mode",
                "data": {
                    "subsystem": "SAFE_MODE",
                    "event_type": "SAFE_MODE",
                    "action": "exit",
                    "reason": "SAFE_MODE_EXIT_TEST",
                },
            }
        )
        await pilot.pause()

        assert systems._safe_mode.get("active") is False
        assert deep._safe_mode.get("active") is False
        assert deep._safe_mode.get("reason") == "SAFE_MODE_EXIT_TEST"


@pytest.mark.asyncio
async def test_telemetry_shed_reasons_visible_in_f1_and_f2_runtime_path(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    systems_updates: list[str] = []
    cockpit_updates: list[str] = []
    original_systems_update = OrionVSystemsScreen.update
    original_cockpit_set_body_text = OrionVCockpitScreen._set_body_text

    def capture_systems(self: OrionVSystemsScreen, renderable) -> None:  # noqa: ANN001
        systems_updates.append(str(renderable))
        original_systems_update(self, renderable)

    def capture_cockpit_body(self: OrionVCockpitScreen, text: str) -> None:
        cockpit_updates.append(text)
        original_cockpit_set_body_text(self, text)

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)
    monkeypatch.setattr(OrionVSystemsScreen, "update", capture_systems)
    monkeypatch.setattr(OrionVCockpitScreen, "_set_body_text", capture_cockpit_body)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        await app._on_telemetry(
            {
                "data": {
                    "power": {
                        "soc_pct": 42.0,
                        "bus_v": 27.9,
                        "bus_a": 1.8,
                        "load_shedding": True,
                        "shed_reasons": ["low_soc", "pdu_overcurrent"],
                    }
                }
            }
        )
        await pilot.pause()

        app.action_show_level("f2")
        await pilot.pause()
        systems_widget = app.query_one("#orionv-systems", OrionVSystemsScreen)
        assert not systems_widget.has_class("hidden")

        app.action_show_level("f1")
        await pilot.pause()
        cockpit_widget = app.query_one("#orionv-cockpit", OrionVCockpitScreen)
        assert not cockpit_widget.has_class("hidden")

    assert any("Track shed reasons: low_soc, pdu_overcurrent." in text for text in systems_updates)
    assert any("Причины сброса: low_soc, pdu_overcurrent" in text for text in cockpit_updates)


@pytest.mark.asyncio
async def test_telemetry_thermal_warn_trip_visible_in_f1_and_f2_runtime_path(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    systems_updates: list[str] = []
    cockpit_updates: list[str] = []
    original_systems_update = OrionVSystemsScreen.update
    original_cockpit_set_body_text = OrionVCockpitScreen._set_body_text

    def capture_systems(self: OrionVSystemsScreen, renderable) -> None:  # noqa: ANN001
        systems_updates.append(str(renderable))
        original_systems_update(self, renderable)

    def capture_cockpit_body(self: OrionVCockpitScreen, text: str) -> None:
        cockpit_updates.append(text)
        original_cockpit_set_body_text(self, text)

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)
    monkeypatch.setattr(OrionVSystemsScreen, "update", capture_systems)
    monkeypatch.setattr(OrionVCockpitScreen, "_set_body_text", capture_cockpit_body)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        await app._on_telemetry(
            {
                "data": {
                    "temp_core_c": 86.0,
                    "temp_external_c": -60.0,
                    "thermal": {
                        "nodes": [
                            {
                                "id": "core",
                                "temp_c": 86.0,
                                "warned": True,
                                "tripped": False,
                                "warn_c": 80.0,
                                "trip_c": 90.0,
                                "hys_c": 5.0,
                            },
                            {
                                "id": "pdu",
                                "temp_c": 96.0,
                                "warned": False,
                                "tripped": True,
                                "warn_c": 85.0,
                                "trip_c": 95.0,
                                "hys_c": 5.0,
                            },
                        ]
                    },
                }
            }
        )
        await pilot.pause()

        app.action_show_level("f2")
        await pilot.pause()
        systems_widget = app.query_one("#orionv-systems", OrionVSystemsScreen)
        assert not systems_widget.has_class("hidden")

        app.action_show_level("f1")
        await pilot.pause()
        cockpit_widget = app.query_one("#orionv-cockpit", OrionVCockpitScreen)
        assert not cockpit_widget.has_class("hidden")

    assert any("[F2] Systems Overview" in text for text in systems_updates)
    assert any("Safety / Integrity / Hazard [unknown]" in text for text in systems_updates)
    assert any("Core: 86.0 °C | limit 90°C | state=WARN" in text for text in cockpit_updates)
    assert any("TRIP nodes: pdu" in text for text in cockpit_updates)


def test_trend_ascii_uses_semantic_no_data_marker() -> None:
    assert _trend_ascii("soc", []) == "soc: degraded: нет данных"


def test_trend_ascii_formats_last_values() -> None:
    text = _trend_ascii("soc", [10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    assert text.startswith("soc: n=6 последние=[20.0 30.0 40.0 50.0 60.0]")


def test_wait_for_ack_accepts_legacy_success_alias() -> None:
    app = OrionVApp()
    app._pending_ack_command_id = "req-success"
    app._ack_wait_started_mono = time.monotonic()
    app._control_acks.append(
        {
            "_received_mono": time.monotonic(),
            "data": {
                "success": True,
                "kind": "sim.pause",
                "requestId": "req-success",
                "payload": {"command_name": "sim.pause", "status": "applied"},
            },
        }
    )

    ok = asyncio.run(app._wait_for_ack("sim.pause", 0.2))
    assert ok is True


@pytest.mark.asyncio
async def test_on_event_publishes_incident_open_audit_once() -> None:
    app = OrionVApp()
    published: list[tuple[str, dict[str, object]]] = []

    async def publish_audit(subject: str, payload: dict[str, object]) -> None:
        published.append((subject, payload))

    app._publish_audit_event = publish_audit  # type: ignore[method-assign]

    envelope = {
        "subject": "qiki.events.v1.audit",
        "timestamp": "2026-03-05T12:00:01+00:00",
        "data": {
            "incident_id": "inc-open-1",
            "severity": "critical",
            "description": "overheat",
            "ts_unix_ms": 1_741_177_601_000,
        },
    }
    await app._on_event(envelope)
    await asyncio.sleep(0)
    await app._on_event(envelope)
    await asyncio.sleep(0)

    opens = [row for row in published if row[1].get("kind") == "incident_open"]
    assert len(opens) == 1
    assert opens[0][0] == "qiki.events.v1.operator.incidents"
    assert opens[0][1].get("incident_id") == "inc-open-1"
    assert opens[0][1].get("severity") == "C"
    assert opens[0][1].get("ts_epoch") == 1_741_177_601.0


@pytest.mark.asyncio
async def test_overlay_click_selects_incident(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        app._events_store.append(
            {
                "subject": "qiki.events.v1.audit",
                "data": {"incident_id": "inc-click", "severity": "C", "description": "Critical click"},
            }
        )
        app._refresh_ui()
        await pilot.pause()

        await pilot.click("#orionv-overlay-focus")
        await pilot.pause()

        assert app._selected_incident_id == "inc-click"


@pytest.mark.asyncio
async def test_incident_selected_handler_publishes_mouse_operator_action() -> None:
    published: list[dict[str, object]] = []

    async def publish_operator_action(payload: dict[str, object]) -> None:
        published.append(payload)

    app = OrionVApp()
    app._publish_operator_action = publish_operator_action  # type: ignore[method-assign]
    app._set_help_text = lambda _: None  # type: ignore[method-assign]
    app._refresh_ui = lambda: None  # type: ignore[method-assign]

    app.on_orion_v_alerts_overlay_incident_selected(OrionVAlertsOverlay.IncidentSelected("inc-click"))
    await asyncio.sleep(0)

    assert app._selected_incident_id == "inc-click"
    assert published[-1]["kind"] == "incident_select"
    assert published[-1]["input_mode"] == "mouse"
    assert published[-1]["incident_id"] == "inc-click"


@pytest.mark.asyncio
async def test_overlay_hides_stale_buttons_after_incident_list_shrinks(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        app._events_store.append(
            {
                "subject": "qiki.events.v1.audit",
                "data": {"incident_id": "inc-1", "severity": "C", "description": "First"},
            }
        )
        app._events_store.append(
            {
                "subject": "qiki.events.v1.audit",
                "data": {"incident_id": "inc-2", "severity": "A", "description": "Second"},
            }
        )
        app._refresh_ui()
        await pilot.pause()

        focus_button = app.query_one("#orionv-overlay-focus")
        assert "hidden" not in focus_button.classes
        assert focus_button.label.plain == "Фокус inc-2"

        app._events_store = app._events_store.__class__()
        app._events_store.append(
            {
                "subject": "qiki.events.v1.audit",
                "data": {"incident_id": "inc-1", "severity": "C", "description": "First"},
            }
        )
        app._refresh_ui()
        await pilot.pause()

        focus_button = app.query_one("#orionv-overlay-focus")
        assert "hidden" not in focus_button.classes
        assert focus_button.label.plain == "Фокус inc-1"


def test_build_level0_alerts_includes_system_driven_card_alert() -> None:
    model = HardwareViewModel(
        system_status=ViewStatus.CRIT,
        subsystems={
            "power": SubsystemView(
                id="power",
                title="Энергия",
                status=ViewStatus.CRIT,
                fields=[
                    _field("power.soc", "Уровень заряда", 9, "%", ViewStatus.CRIT),
                    _field("power.bus_v", "Напряжение шины", 18.9, "В", ViewStatus.CRIT),
                ],
                summary="Заряд 9%, 18.9В",
            )
        },
        generated_at=0.0,
    )

    alerts = build_level0_alerts(hardware_model=model)

    assert any(
        alert.title == "Power / Charge"
        and alert.severity == "critical"
        and alert.short_meaning == "power constrained"
        for alert in alerts
    )


def test_build_level0_alerts_includes_objective_and_qiki_alerts() -> None:
    response = QikiChatResponseV1.model_validate(
        {
            "version": 1,
            "request_id": str(UUID(int=42)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Approach deferred", "ru": "Сближение отложено"},
                "body": {
                    "en": "QIKI cannot trust the current station track enough to clear the approach.",
                    "ru": "QIKI не может достаточно доверять текущему треку станции, чтобы разрешить сближение.",
                },
            },
            "legality": {
                "status": "deferred",
                "domain": "trust",
                "reason_code": "STATION_TRACK_LOW_QUALITY",
                "reason": {
                    "en": "Station track quality 0.32 is below the minimum 0.50.",
                    "ru": "Качество трека станции 0.32 ниже допустимого минимума 0.50.",
                },
                "allowed_when": {
                    "en": "Retry when station tracking quality recovers above the configured threshold.",
                    "ru": "Повторите попытку, когда качество трекинга станции восстановится выше заданного порога.",
                },
            },
            "trust_signals": [],
            "consequence": {
                "status": "not_sent",
                "summary": {
                    "en": "Approach execution was not started because target confidence is too low.",
                    "ru": "Исполнение сближения не начато, потому что доверие к цели слишком низкое.",
                },
            },
            "proposals": [],
            "warnings": [{"en": "Immediate caution", "ru": "Немедленная осторожность"}],
            "error": None,
        }
    )

    alerts = build_level0_alerts(
        hardware_model=None,
        observation_objective={
            "follow_up_status": "review_required",
            "follow_up_summary_ru": "Нужно закрыть review перед продолжением.",
            "follow_up_allowed_when_ru": "Продолжение разрешено только после review confirm.",
        },
        qiki_response=response,
    )

    assert any(alert.id == "objective:review_required" and alert.severity == "critical" for alert in alerts)
    assert any(alert.id.startswith("qiki:legality:") and alert.title == "Сближение отложено" for alert in alerts)
    assert any(alert.id == "qiki:warning:0" and alert.short_meaning == "Немедленная осторожность" for alert in alerts)


@pytest.mark.asyncio
async def test_action_bar_click_switches_level(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        assert app._current_level == "f1"

        await pilot.click("#orionv-action-f2")
        await pilot.pause()

        assert app._current_level == "f2"


@pytest.mark.asyncio
async def test_action_select_subsystem_sets_f2_and_selected_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    published: list[dict[str, object]] = []

    async def publish_operator_action(payload: dict[str, object]) -> None:
        published.append(payload)

    app = OrionVApp()
    app._publish_operator_action = publish_operator_action  # type: ignore[method-assign]
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        app.action_select_subsystem("power")
        await pilot.pause()

        assert app._current_level == "f2"
        assert app._selected_system_module_slug == "power"
        assert published[-1]["kind"] == "subsystem_select"
        assert published[-1]["action_type"] == "systems"
        assert published[-1]["subsystem"] == "power"


@pytest.mark.asyncio
async def test_action_select_incident_sets_selected_and_publishes(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    published: list[dict[str, object]] = []

    async def publish_operator_action(payload: dict[str, object]) -> None:
        published.append(payload)

    app = OrionVApp()
    app._publish_operator_action = publish_operator_action  # type: ignore[method-assign]
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        app._events_store.append(
            {
                "subject": "qiki.events.v1.audit",
                "data": {"incident_id": "inc-manual", "severity": "C", "description": "manual selection"},
            }
        )
        app._refresh_ui()
        await pilot.pause()
        app.action_select_incident("inc-manual")
        await pilot.pause()

        assert app._selected_incident_id == "inc-manual"
        assert published[-1]["kind"] == "incident_select"
        assert published[-1]["incident_id"] == "inc-manual"


@pytest.mark.asyncio
async def test_status_bars_power_click_opens_f2_and_selects_subsystem(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        await app._on_telemetry({"data": {"power": {"soc_pct": 61.0}}})
        await pilot.pause()

        await pilot.click("#orionv-status-power-action")
        await pilot.pause()

        assert app._current_level == "f2"
        assert app._selected_system_module_slug == "power"


@pytest.mark.asyncio
async def test_status_bars_power_click_opens_f2(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        await app._on_telemetry({"data": {"power": {"soc_pct": 77.0}}})
        await pilot.pause()
        await pilot.click("#orionv-status-power-action")
        await pilot.pause()

        assert app._current_level == "f2"
        assert app._selected_system_module_slug == "power"


@pytest.mark.asyncio
async def test_cockpit_power_click_opens_f2_and_selects_power(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        await pilot.click("#orionv-cockpit-jump-power")
        await pilot.pause()

        assert app._current_level == "f2"
        assert app._selected_system_module_slug == "power"


@pytest.mark.asyncio
async def test_f4_console_shows_operator_history(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        app._set_help_text("QIKI: тестовый ответ")
        app.action_show_level("f4")
        await pilot.pause()

        raw = app.query_one("#orionv-raw")
        text = raw.render().plain
        assert app._current_level == "f4"
        assert "[F4] Консоль/Console" in text
        assert "QIKI: тестовый ответ" in text
        assert "Последние действия и ответы/Recent operator messages:" in text


@pytest.mark.asyncio
async def test_cockpit_docking_click_opens_f2_and_selects_docking(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        await pilot.click("#orionv-cockpit-jump-docking")
        await pilot.pause()

        assert app._current_level == "f2"
        assert app._selected_system_module_slug == "docking"


@pytest.mark.asyncio
async def test_cockpit_procedures_click_opens_f6_and_sets_procedure_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        await pilot.click("#orionv-cockpit-jump-procedures")
        await pilot.pause()

        assert app._current_level == "f6"
        assert app._audit_filter_type == "procedures"


@pytest.mark.asyncio
async def test_cockpit_qiki_cancel_click_clears_pending_action(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(160, 48)) as pilot:
        await pilot.pause()
        await app._on_qiki_response(
            {
                "data": {
                    "version": 1,
                    "request_id": str(UUID(int=999)),
                    "ok": True,
                    "mode": "FACTORY",
                    "reply": {
                        "title": {"en": "Release ready", "ru": "Отстыковка готова"},
                        "body": {
                            "en": "QIKI can prepare a real undock command, but ORION must confirm it explicitly.",
                            "ru": (
                                "QIKI может подготовить реальную команду отстыковки, "
                                "но ORION должен подтвердить её отдельно."
                            ),
                        },
                    },
                    "legality": {
                        "status": "allowed",
                        "domain": "physics",
                        "reason_code": "DOCK_RELEASE_READY",
                        "reason": {
                            "en": "Docking telemetry confirms an attached state on port A.",
                            "ru": "Телеметрия стыковки подтверждает пристыкованное состояние на порту A.",
                        },
                    },
                    "trust_signals": [
                        {
                            "label": {"en": "Docking telemetry", "ru": "Телеметрия стыковки"},
                            "state": "healthy",
                            "source": "sensor",
                            "confidence": 1.0,
                            "reason_code": "DOCK_RELEASE_READY",
                            "reason": {
                                "en": "Docking telemetry confirms an attached state on port A.",
                                "ru": "Телеметрия стыковки подтверждает пристыкованное состояние на порту A.",
                            },
                        }
                    ],
                    "consequence": {
                        "status": "pending",
                        "summary": {
                            "en": "The undock command is prepared and waiting for explicit operator confirmation.",
                            "ru": "Команда отстыковки подготовлена и ждёт явного подтверждения оператора.",
                        },
                    },
                    "proposals": [
                        {
                            "proposal_id": "qiki-release-dock",
                            "title": {"en": "Confirm undock", "ru": "Подтвердить отстыковку"},
                            "justification": {
                                "en": "Telemetry confirms a docked state and a valid release path.",
                                "ru": "Телеметрия подтверждает пристыкованное состояние и валидный путь отстыковки.",
                            },
                            "confidence": 1.0,
                            "priority": 90,
                            "suggested_questions": [],
                            "proposed_actions": [
                                {
                                    "kind": "NATS_COMMAND",
                                    "subject": "qiki.commands.control",
                                    "name": "sim.dock.release",
                                    "parameters": {},
                                    "dry_run": False,
                                }
                            ],
                        }
                    ],
                    "warnings": [],
                    "error": None,
                }
            }
        )
        await pilot.pause()

        assert app._qiki_pending_action is not None

        await pilot.click("#orionv-cockpit-qiki-cancel")
        await pilot.pause()

        assert app._qiki_pending_action is None
        assert app._qiki_last_response is not None
        assert app._qiki_last_response.consequence is not None
        assert app._qiki_last_response.consequence.status == "not_sent"


@pytest.mark.asyncio
async def test_status_bars_always_visible_with_nodata_before_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        bars = app.query_one("#orionv-bars", OrionVStatusBars)
        assert not bars.has_class("hidden")
        power_chip = app.query_one("#orionv-status-power-action")
        assert "NO DATA" in power_chip.label.plain

        await app._on_telemetry({"data": {"power": {"soc_pct": 80.0}}})
        await pilot.pause()
        power_chip = app.query_one("#orionv-status-power-action")
        assert "NO DATA" not in power_chip.label.plain


@pytest.mark.asyncio
async def test_app_uses_dense_profile_class_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    async def no_nats(self: OrionVApp) -> None:
        self._nats_state = "lost"

    monkeypatch.setenv("ORIONV_UI_PROFILE", "dense")
    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", no_nats)

    app = OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        await pilot.pause()
        assert app.has_class("ui-dense")
