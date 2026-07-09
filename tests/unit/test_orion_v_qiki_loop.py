from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.shared.models.qiki_chat import BilingualText


def test_publish_qiki_intent_routes_to_nats_and_tracks_pending(monkeypatch) -> None:
    app = OrionVApp()
    published: list[tuple[str, dict]] = []
    messages: list[str] = []

    class _StubNats:
        async def publish_command(self, subject: str, payload: dict) -> None:
            published.append((subject, payload))

    app._nats_client = _StubNats()  # type: ignore[assignment]
    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr("qiki.services.operator_console.orion_v.app.uuid4", lambda: UUID(int=2))

    asyncio.run(app._publish_qiki_intent("dock"))

    assert len(published) == 1
    assert published[0][0] == "qiki.intents"
    assert published[0][1]["input"]["text"] == "dock"
    assert str(UUID(int=2)) in app._qiki_pending
    assert messages[-1] == "QIKI intent отправлен: dock"


def test_publish_qiki_intent_blocks_observation_while_hold_for_recheck_is_open() -> None:
    app = OrionVApp()
    published: list[tuple[str, dict]] = []
    messages: list[str] = []

    class _StubNats:
        async def publish_command(self, subject: str, payload: dict) -> None:
            published.append((subject, payload))

    app._nats_client = _StubNats()  # type: ignore[assignment]
    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    app._active_observation_objective = {
        "objective_id": "observation-123",
        "objective_type": "observation",
        "status": "confirmed",
        "target_designator": "ALLY-4D1ED5",
        "follow_up_status": "hold_for_recheck",
        "follow_up_reason_code": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
        "follow_up_event_type": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
        "follow_up_summary_en": "Post-review hold for recheck is selected.",
        "follow_up_summary_ru": "Выбран post-review hold for recheck.",
        "follow_up_allowed_when_en": "Run a cautious safe recheck before resuming.",
        "follow_up_allowed_when_ru": "Сначала выполните осторожный safe recheck, затем возобновляйте contour.",
    }

    asyncio.run(app._publish_qiki_intent("safe observation ALLY-4D1ED5"))

    assert published == []
    assert app._qiki_pending == {}
    assert "resume observation" in messages[-1]


def test_publish_qiki_intent_allows_observation_after_resume_follow_up(monkeypatch) -> None:
    app = OrionVApp()
    published: list[tuple[str, dict]] = []
    messages: list[str] = []

    class _StubNats:
        async def publish_command(self, subject: str, payload: dict) -> None:
            published.append((subject, payload))

    app._nats_client = _StubNats()  # type: ignore[assignment]
    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr("qiki.services.operator_console.orion_v.app.uuid4", lambda: UUID(int=200))
    app._active_observation_objective = {
        "objective_id": "observation-123",
        "objective_type": "observation",
        "status": "confirmed",
        "target_designator": "ALLY-4D1ED5",
        "follow_up_status": "resume_observation",
        "follow_up_reason_code": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
        "follow_up_event_type": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
        "follow_up_summary_en": "Observation resume is selected.",
        "follow_up_summary_ru": "Выбран resume observation.",
        "follow_up_allowed_when_en": "Issue one cautious safe observation for ALLY-4D1ED5.",
        "follow_up_allowed_when_ru": "Теперь задайте один cautious safe observation для ALLY-4D1ED5.",
    }

    asyncio.run(app._publish_qiki_intent("safe observation ALLY-4D1ED5"))

    assert len(published) == 1
    assert published[0][0] == "qiki.intents"
    assert published[0][1]["input"]["text"] == "safe observation ALLY-4D1ED5"
    assert str(UUID(int=200)) in app._qiki_pending
    assert messages[-1] == "QIKI intent отправлен: safe observation ALLY-4D1ED5"


def test_on_qiki_response_updates_help_and_last_response(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=3)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Command blocked", "ru": "Команда заблокирована"},
                "body": {
                    "en": "QIKI can explain docking commands, but it must not execute them automatically.",
                    "ru": "QIKI может объяснять команды стыковки, но не имеет права исполнять их автоматически.",
                },
            },
            "legality": {
                "status": "blocked",
                "domain": "protocol",
                "reason_code": "MVP_NO_AUTO_ACTIONS",
                "reason": {
                    "en": "Auto-actions are disabled in the current QIKI MVP policy.",
                    "ru": "Автодействия отключены в текущей политике MVP для QIKI.",
                },
                "allowed_when": {
                    "en": "Use explicit operator-approved control flow in a future execution phase.",
                    "ru": "Используйте отдельный подтверждаемый оператором контур исполнения в следующей фазе.",
                },
            },
            "trust_signals": [
                {
                    "label": {"en": "Execution policy", "ru": "Политика исполнения"},
                    "state": "healthy",
                    "source": "policy",
                    "confidence": 1.0,
                    "reason_code": "MVP_POLICY_ACTIVE",
                    "reason": {
                        "en": "The block is deterministic and does not depend on telemetry freshness.",
                        "ru": "Блокировка детерминирована и не зависит от свежести телеметрии.",
                    },
                }
            ],
            "consequence": {
                "status": "not_sent",
                "summary": {
                    "en": "No control-bus command was emitted.",
                    "ru": "Команда не была отправлена на control bus.",
                },
                "telemetry_confirmation": {
                    "en": "Execution state remains unchanged.",
                    "ru": "Состояние исполнения осталось без изменений.",
                },
            },
            "proposals": [],
            "warnings": [BilingualText(en="INVALID REQUEST", ru="НЕВЕРНЫЙ ЗАПРОС").model_dump(mode="json")],
            "error": None,
        }
    }

    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    assert app._qiki_last_response is not None
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.status == "blocked"
    assert messages[-1].startswith("QIKI blocked:")
    assert refreshed


def test_on_qiki_response_handles_data_trust_deferred_state(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=8)),
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
            "trust_signals": [
                {
                    "label": {"en": "Station radar track", "ru": "Радарный трек станции"},
                    "state": "degraded",
                    "source": "sensor",
                    "confidence": 0.32,
                    "reason_code": "STATION_TRACK_LOW_QUALITY",
                    "reason": {
                        "en": "Station track quality 0.32 is below the minimum 0.50.",
                        "ru": "Качество трека станции 0.32 ниже допустимого минимума 0.50.",
                    },
                }
            ],
            "consequence": {
                "status": "not_sent",
                "summary": {
                    "en": "Approach execution was not started because target confidence is too low.",
                    "ru": "Исполнение сближения не начато, потому что доверие к цели слишком низкое.",
                },
                "telemetry_confirmation": {
                    "en": "No new guidance or control-bus command was emitted.",
                    "ru": "Ни новая навигационная команда, ни команда на control bus не отправлялись.",
                },
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }

    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    assert app._qiki_last_response is not None
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.status == "deferred"
    assert messages[-1].startswith("QIKI deferred:")
    assert "STATION_TRACK_LOW_QUALITY" in messages[-1]
    assert refreshed


def test_on_qiki_response_handles_resource_blocked_state(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=11)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Channel blocked", "ru": "Канал заблокирован"},
                "body": {
                    "en": "QIKI cannot request station contact because the communications link is offline.",
                    "ru": "QIKI не может запросить связь со станцией, потому что канал связи находится offline.",
                },
            },
            "legality": {
                "status": "blocked",
                "domain": "resource",
                "reason_code": "COMMS_LINK_OFFLINE",
                "reason": {
                    "en": "The communications link is offline, so a station hail cannot be routed.",
                    "ru": "Канал связи находится offline, поэтому вызов станции не может быть маршрутизирован.",
                },
                "allowed_when": {
                    "en": "Restore an online comms link before requesting station contact.",
                    "ru": "Восстановите online-канал связи перед запросом контакта со станцией.",
                },
            },
            "trust_signals": [
                {
                    "label": {"en": "Comms link state", "ru": "Состояние канала связи"},
                    "state": "off",
                    "source": "derived",
                    "confidence": 1.0,
                    "reason_code": "COMMS_LINK_OFFLINE",
                    "reason": {
                        "en": "The communications link is offline, so a station hail cannot be routed.",
                        "ru": "Канал связи находится offline, поэтому вызов станции не может быть маршрутизирован.",
                    },
                }
            ],
            "consequence": {
                "status": "not_sent",
                "summary": {
                    "en": "The station hail was not started.",
                    "ru": "Вызов станции не был начат.",
                },
                "telemetry_confirmation": {
                    "en": "Comms telemetry still reports an offline link; nothing was sent.",
                    "ru": "Телеметрия связи всё ещё показывает offline-канал; ничего не отправлялось.",
                },
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }

    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    assert app._qiki_last_response is not None
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.status == "blocked"
    assert messages[-1].startswith("QIKI blocked:")
    assert "COMMS_LINK_OFFLINE" in messages[-1]
    assert refreshed


def test_on_qiki_response_handles_zone_blocked_state(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=13)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Corridor blocked", "ru": "Коридор заблокирован"},
                "body": {
                    "en": (
                        "QIKI will not clear docking-corridor entry "
                        "because the craft is still outside the allowed zone."
                    ),
                    "ru": (
                        "QIKI не разрешит вход в коридор стыковки, "
                        "потому что аппарат всё ещё вне допустимой зоны."
                    ),
                },
            },
            "legality": {
                "status": "blocked",
                "domain": "zone",
                "reason_code": "DOCKING_ZONE_TOO_FAR",
                "reason": {
                    "en": "Station range 6400 m exceeds the docking-corridor threshold 5000 m.",
                    "ru": "Дальность до станции 6400 м превышает порог коридора стыковки 5000 м.",
                },
                "allowed_when": {
                    "en": "Reduce the station range below the docking-corridor threshold before retrying.",
                    "ru": "Сократите дальность до станции ниже порога коридора стыковки и повторите попытку.",
                },
            },
            "trust_signals": [
                {
                    "label": {"en": "Station radar track", "ru": "Радарный трек станции"},
                    "state": "healthy",
                    "source": "sensor",
                    "confidence": 0.92,
                    "reason_code": "DOCKING_ZONE_TOO_FAR",
                    "reason": {
                        "en": "Station range 6400 m exceeds the docking-corridor threshold 5000 m.",
                        "ru": "Дальность до станции 6400 м превышает порог коридора стыковки 5000 м.",
                    },
                }
            ],
            "consequence": {
                "status": "not_sent",
                "summary": {
                    "en": "Docking-corridor entry was not started.",
                    "ru": "Вход в коридор стыковки не был начат.",
                },
                "telemetry_confirmation": {
                    "en": "Radar telemetry still shows the craft outside the docking corridor.",
                    "ru": "Радарная телеметрия всё ещё показывает аппарат вне коридора стыковки.",
                },
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }

    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    assert app._qiki_last_response is not None
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.status == "blocked"
    assert messages[-1].startswith("QIKI blocked:")
    assert "DOCKING_ZONE_TOO_FAR" in messages[-1]
    assert refreshed


def test_on_qiki_response_handles_failed_trust_state(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=16)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Attitude hold blocked", "ru": "Удержание ориентации заблокировано"},
                "body": {
                    "en": "QIKI blocks attitude hold because the IMU currently reports a failed state.",
                    "ru": "QIKI блокирует удержание ориентации, потому что IMU сейчас сообщает о сбое.",
                },
            },
            "legality": {
                "status": "blocked",
                "domain": "trust",
                "reason_code": "IMU_FAILED",
                "reason": {
                    "en": "IMU reports a failed state, so QIKI will not trust attitude stabilization commands.",
                    "ru": (
                        "IMU сообщает о сбойном состоянии, "
                        "поэтому QIKI не будет доверять командам стабилизации ориентации."
                    ),
                },
                "allowed_when": {
                    "en": "Recover the IMU before requesting attitude stabilization again.",
                    "ru": "Восстановите IMU перед повторным запросом стабилизации ориентации.",
                },
            },
            "trust_signals": [
                {
                    "label": {"en": "IMU telemetry", "ru": "Телеметрия IMU"},
                    "state": "failed",
                    "source": "sensor",
                    "confidence": 0.0,
                    "reason_code": "IMU_FAILED",
                    "reason": {"en": "IMU status=crit, reason=not ok.", "ru": "Статус IMU=crit, причина=not ok."},
                }
            ],
            "consequence": {
                "status": "not_sent",
                "summary": {
                    "en": "Attitude stabilization was not started.",
                    "ru": "Стабилизация ориентации не была начата.",
                },
                "telemetry_confirmation": {
                    "en": "IMU telemetry still reports a failed state; no action was emitted.",
                    "ru": "Телеметрия IMU всё ещё сообщает о сбое; действие не запускалось.",
                },
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }

    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    assert app._qiki_last_response is not None
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.status == "blocked"
    assert messages[-1].startswith("QIKI blocked:")
    assert "IMU_FAILED" in messages[-1]
    assert refreshed


def test_on_qiki_response_exposes_confirmable_qiki_action(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=9)),
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
                "allowed_when": {
                    "en": "Use the explicit ORION confirmation step to send the undock command.",
                    "ru": "Используйте явный шаг подтверждения в ORION, чтобы отправить команду отстыковки.",
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
                "telemetry_confirmation": {
                    "en": (
                        "No control-bus command has been sent yet; "
                        "the craft remains docked until ORION confirms execution."
                    ),
                    "ru": (
                        "Команда на control bus ещё не отправлялась; аппарат остаётся "
                        "пристыкованным, пока ORION не подтвердит исполнение."
                    ),
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

    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    assert app._qiki_pending_action is not None
    assert app._qiki_pending_action["name"] == "sim.dock.release"
    assert messages[-1].endswith("| q confirm")
    assert refreshed


def test_execute_qiki_pending_action_updates_consequence_after_ack_and_telemetry(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=10)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {"title": {"en": "Release ready", "ru": "Отстыковка готова"}, "body": {"en": "ok", "ru": "ок"}},
            "legality": {
                "status": "allowed",
                "domain": "physics",
                "reason_code": "DOCK_RELEASE_READY",
                "reason": {
                    "en": "Docking telemetry confirms an attached state on port A.",
                    "ru": "Телеметрия стыковки подтверждает пристыкованное состояние на порту A.",
                },
            },
            "trust_signals": [],
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
                    "justification": {"en": "ok", "ru": "ок"},
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
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    published: list[tuple[str, dict | None]] = []

    async def _publish(command_name: str, parameters: dict | None = None) -> None:
        published.append((command_name, parameters))

    async def _wait_ack(_expected: str, _timeout: float, command_id=None) -> bool:
        return True

    async def _wait_effect(_command: str, _timeout: float) -> BilingualText | None:
        return BilingualText(
            en="Docking telemetry confirms undocked state on port A.",
            ru="Телеметрия стыковки подтверждает состояние отстыковки на порту A.",
        )

    monkeypatch.setattr(app, "_publish_sim_command", _publish)
    monkeypatch.setattr(app, "_wait_for_ack", _wait_ack)
    monkeypatch.setattr(app, "_wait_for_qiki_effect", _wait_effect)

    app._seal_pending_decision(app._qiki_pending_action)  # M5: реальный поток пломбирует до execute
    asyncio.run(app._execute_qiki_pending_action())

    assert published == [("sim.dock.release", {})]
    assert app._qiki_pending_action is None
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "confirmed"
    assert "отстыковки" in app._qiki_last_response.consequence.telemetry_confirmation.ru.lower()
    assert messages[-1] == "QIKI execution confirmed: sim.dock.release"
    assert refreshed


def test_on_qiki_response_extracts_orion_procedure_pending_action(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=14)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Safe observation ready", "ru": "Безопасное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SAFE_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Procedure prepared", "ru": "Процедура подготовлена"},
            },
            "proposals": [
                {
                    "proposal_id": "qiki-safe-observation",
                    "title": {"en": "Run safe observation", "ru": "Запустить безопасное наблюдение"},
                    "justification": {"en": "ok", "ru": "ок"},
                    "confidence": 1.0,
                    "priority": 85,
                    "suggested_questions": [],
                    "proposed_actions": [
                        {
                            "kind": "ORION_PROCEDURE",
                            "subject": "orionv.procedure",
                            "name": "safe_pause_resume",
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

    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    assert app._qiki_pending_action is not None
    assert app._qiki_pending_action["action_kind"] == "ORION_PROCEDURE"
    assert app._qiki_pending_action["name"] == "safe_pause_resume"
    assert messages[-1].endswith("| q confirm")
    assert refreshed


def test_execute_qiki_pending_procedure_updates_consequence_after_completion(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))
    app._telemetry = {"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}}
    app._qiki_pending_action = {
        "action_kind": "ORION_PROCEDURE",
        "name": "safe_pause_resume",
        "title_ru": "Запустить безопасное наблюдение",
    }
    app._qiki_last_response = app._qiki_last_response = app._qiki_last_response = None
    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=15)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Safe observation ready", "ru": "Безопасное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SAFE_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Procedure prepared", "ru": "Процедура подготовлена"},
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))
    app._qiki_pending_action = {
        "action_kind": "ORION_PROCEDURE",
        "name": "safe_pause_resume",
        "title_ru": "Запустить безопасное наблюдение",
    }

    async def _fake_run(name: str) -> None:
        app._procedure_engine.state.procedure_name = name
        app._procedure_engine.state.status = "ok"

    async def _fake_wait(name: str, timeout_s: float) -> bool:
        return name == "safe_pause_resume" and timeout_s > 0

    monkeypatch.setattr(app, "_run_procedure", _fake_run)
    monkeypatch.setattr(app, "_wait_for_procedure_completion", _fake_wait)

    app._seal_pending_decision(app._qiki_pending_action)  # M5: реальный поток пломбирует до execute
    asyncio.run(app._execute_qiki_pending_action())

    assert app._qiki_pending_action is None
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "confirmed"
    assert messages[-1] == "QIKI execution confirmed: процедура safe_pause_resume"
    assert refreshed


def test_execute_qiki_pending_slow_procedure_confirms_speed(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))
    app._telemetry = {"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 0.25}}

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=32)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Slow observation ready", "ru": "Медленное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SLOW_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Procedure prepared", "ru": "Процедура подготовлена"},
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))
    app._qiki_pending_action = {
        "action_kind": "ORION_PROCEDURE",
        "name": "safe_pause_slow_resume",
        "title_ru": "Запустить медленное наблюдение",
    }

    async def _fake_run(name: str) -> None:
        app._procedure_engine.state.procedure_name = name
        app._procedure_engine.state.status = "ok"

    async def _fake_wait(name: str, timeout_s: float) -> bool:
        return name == "safe_pause_slow_resume" and timeout_s > 0

    monkeypatch.setattr(app, "_run_procedure", _fake_run)
    monkeypatch.setattr(app, "_wait_for_procedure_completion", _fake_wait)

    app._seal_pending_decision(app._qiki_pending_action)  # M5: реальный поток пломбирует до execute
    asyncio.run(app._execute_qiki_pending_action())

    assert app._qiki_pending_action is None
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "confirmed"
    assert "x0.25" in app._qiki_last_response.consequence.summary.ru
    assert "speed=0.25" in app._qiki_last_response.consequence.telemetry_confirmation.ru
    assert messages[-1] == "QIKI execution confirmed: процедура safe_pause_slow_resume"
    assert refreshed


def test_execute_qiki_pending_slow_procedure_requires_hidden_event_follow_up(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))
    app._telemetry = {"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 0.25}}
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": "qiki.events.v1.operator.objectives",
        "timestamp": "2026-03-13T00:00:00+00:00",
        "ts_epoch": 1.0,
        "kind": "observation_objective_seed",
        "objective_id": "observation-32",
        "objective_type": "observation",
        "status": "prepared",
        "observation_style": "slow",
        "procedure_name": "safe_pause_slow_resume",
        "route_role": "deviation",
        "request_id": "request-32",
        "proposal_id": "proposal-32",
        "target_designator": "ALLY-4D1ED5",
        "follow_up_status": "review_required",
        "follow_up_reason_code": "HIDDEN_EVENT_REVIEW_REQUIRED",
        "follow_up_event_type": "HIDDEN_EVENT_REVEALED",
        "follow_up_summary_en": "Hidden-event follow-up is required.",
        "follow_up_summary_ru": "Нужен follow-up по скрытому событию.",
        "follow_up_allowed_when_en": "Review the linked hidden fact before issuing the next observation objective.",
        "follow_up_allowed_when_ru": "Сначала проверьте связанный hidden fact, затем задавайте следующую observation-цель.",
    }
    app._events_store.append(
        {
            "subject": "qiki.events.v1.audit",
            "data": {
                "objective_id": "observation-32",
                "proposal_id": "proposal-32",
                "request_id": "request-32",
                "procedure_name": "safe_pause_slow_resume",
                "target_designator": "ALLY-4D1ED5",
                "route_role": "deviation",
                "event_type": "HIDDEN_EVENT_REVEALED",
                "message": "Off-route выбор раскрыл скрытую аномалию.",
            },
        }
    )

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=32)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Slow observation ready", "ru": "Медленное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SLOW_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
                "allowed_when": {
                    "en": "Confirm the prepared ORION procedure to pause the simulation and resume it at x0.25.",
                    "ru": (
                        "Подтвердите подготовленную процедуру ORION, чтобы поставить симуляцию "
                        "на паузу и вернуть её на скорости x0.25."
                    ),
                },
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Procedure prepared", "ru": "Процедура подготовлена"},
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))
    app._qiki_pending_action = {
        "action_kind": "ORION_PROCEDURE",
        "name": "safe_pause_slow_resume",
        "title_ru": "Запустить медленное наблюдение",
    }

    async def _fake_run(name: str) -> None:
        app._procedure_engine.state.procedure_name = name
        app._procedure_engine.state.status = "ok"

    async def _fake_wait(name: str, timeout_s: float) -> bool:
        return name == "safe_pause_slow_resume" and timeout_s > 0

    monkeypatch.setattr(app, "_run_procedure", _fake_run)
    monkeypatch.setattr(app, "_wait_for_procedure_completion", _fake_wait)

    app._seal_pending_decision(app._qiki_pending_action)  # M5: реальный поток пломбирует до execute
    asyncio.run(app._execute_qiki_pending_action())

    assert app._qiki_pending_action is None
    assert app._active_observation_objective is not None
    assert app._active_observation_objective["status"] == "confirmed"
    assert app._active_observation_objective["follow_up_status"] == "review_required"
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "pending"
    assert "hidden" in app._qiki_last_response.consequence.summary.en.lower()
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.allowed_when is not None
    assert "hidden fact" in app._qiki_last_response.legality.allowed_when.en.lower()
    assert messages[-1] == "QIKI execution confirmed: процедура safe_pause_slow_resume"
    assert refreshed


def test_ack_observation_review_closes_qiki_pending_follow_up(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []
    published_actions: list[dict[str, object]] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))
    async def _publish_action(payload: dict[str, object]) -> None:
        published_actions.append(payload)

    app._publish_operator_action = _publish_action  # type: ignore[method-assign]
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "orion_v",
        "subject": "qiki.events.v1.operator.objectives",
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
        "summary_ru": "Observation-цель завершена.",
        "summary_en": "Observation complete.",
        "reason_code": "OBJECTIVE_CONFIRMED",
        "follow_up_status": "review_required",
        "follow_up_reason_code": "HIDDEN_EVENT_REVIEW_REQUIRED",
        "follow_up_event_type": "HIDDEN_EVENT_REVEALED",
        "follow_up_summary_en": "Hidden-event follow-up is required.",
        "follow_up_summary_ru": "Нужен follow-up по скрытому событию.",
        "follow_up_allowed_when_en": "Review the linked hidden fact before issuing the next observation objective.",
        "follow_up_allowed_when_ru": "Сначала проверьте связанный hidden fact, затем задавайте следующую observation-цель.",
    }
    app._events_store.append(
        {
            "subject": "qiki.events.v1.audit",
            "data": {
                "proposal_id": "prop-1",
                "objective_id": "observation-123",
                "request_id": "req-1",
                "event_type": "HIDDEN_EVENT_REVEALED",
                "procedure_name": "safe_pause_slow_resume",
                "target_designator": "ALLY-4D1ED5",
                "route_role": "deviation",
                "message": "Deviation route revealed a hidden fact.",
            },
        }
    )
    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=34)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Slow observation ready", "ru": "Медленное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SLOW_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
                "allowed_when": {
                    "en": "Review the linked hidden fact before issuing the next observation objective.",
                    "ru": "Сначала проверьте связанный hidden fact, затем задавайте следующую observation-цель.",
                },
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Hidden-event follow-up is required.", "ru": "Нужен follow-up."},
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    asyncio.run(app._ack_observation_review())
    asyncio.run(
        app._on_event(
            {
                "subject": "qiki.events.v1.operator.objectives",
                "data": {
                    **app._active_observation_objective,
                    "source": "q_core_intents",
                    "reason_code": "OBJECTIVE_REVIEW_CLOSED",
                    "follow_up_status": "review_completed",
                    "follow_up_reason_code": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
                    "follow_up_event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
                    "follow_up_summary_en": (
                        "Hidden-event review is closed: the linked fact was acknowledged and one post-review "
                        "follow-up choice is now open."
                    ),
                    "follow_up_summary_ru": (
                        "Review скрытого события закрыт: связанный факт подтверждён, и теперь открыт один "
                        "post-review follow-up choice."
                    ),
                    "follow_up_allowed_when_en": (
                        "Select the post-review follow-up choice before issuing the next observation objective."
                    ),
                    "follow_up_allowed_when_ru": (
                        "Сначала выберите post-review follow-up choice, затем задавайте следующую observation-цель."
                    ),
                },
            }
        )
    )

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["follow_up_status"] == "review_completed"
    assert app._active_observation_objective["reason_code"] == "OBJECTIVE_REVIEW_CLOSED"
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "confirmed"
    assert "review is closed" in app._qiki_last_response.consequence.summary.en.lower()
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.allowed_when is not None
    assert "select the post-review follow-up choice" in app._qiki_last_response.legality.allowed_when.en.lower()
    assert published_actions[-1]["event_type"] == "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED"
    assert messages[-1] == "Review action published: waiting for canonical follow-up update"
    assert refreshed


def test_select_observation_recheck_hold_changes_qiki_next_step(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []
    published_actions: list[dict[str, object]] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))
    async def _publish_action(payload: dict[str, object]) -> None:
        published_actions.append(payload)

    app._publish_operator_action = _publish_action  # type: ignore[method-assign]
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "orion_v",
        "subject": "qiki.events.v1.operator.objectives",
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
        "summary_ru": "Closure review скрытого события подтверждён на существующем observation path.",
        "summary_en": "The hidden-event review closure is confirmed on the existing observation path.",
        "reason_code": "OBJECTIVE_REVIEW_CLOSED",
        "follow_up_status": "review_completed",
        "follow_up_reason_code": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
        "follow_up_event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
        "follow_up_summary_en": "Hidden-event review is closed and one post-review follow-up choice is open.",
        "follow_up_summary_ru": "Review скрытого события закрыт, и один post-review follow-up choice открыт.",
        "follow_up_allowed_when_en": "Select the post-review follow-up choice before issuing the next observation objective.",
        "follow_up_allowed_when_ru": "Сначала выберите post-review follow-up choice, затем задавайте следующую observation-цель.",
    }
    app._audit_store.append(
        {
            "subject": "qiki.events.v1.operator.actions",
            "data": {
                "proposal_id": "prop-1",
                "objective_id": "observation-123",
                "request_id": "req-1",
                "event_type": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
                "procedure_name": "safe_pause_slow_resume",
                "target_designator": "ALLY-4D1ED5",
                "route_role": "deviation",
                "message": "Operator reviewed the linked hidden fact.",
            },
        }
    )
    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=35)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Slow observation ready", "ru": "Медленное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "HIDDEN_EVENT_REVIEW_ACKNOWLEDGED",
                "reason": {"en": "ok", "ru": "ок"},
                "allowed_when": {
                    "en": "Select the post-review follow-up choice before issuing the next observation objective.",
                    "ru": "Сначала выберите post-review follow-up choice, затем задавайте следующую observation-цель.",
                },
            },
            "trust_signals": [],
            "consequence": {
                "status": "confirmed",
                "summary": {
                    "en": "Hidden-event review is closed and one post-review follow-up choice is open.",
                    "ru": "Review скрытого события закрыт, и один post-review follow-up choice открыт.",
                },
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    asyncio.run(app._select_observation_recheck_hold())
    asyncio.run(
        app._on_event(
            {
                "subject": "qiki.events.v1.operator.objectives",
                "data": {
                    **app._active_observation_objective,
                    "source": "q_core_intents",
                    "reason_code": "OBJECTIVE_POST_REVIEW_HOLD_SELECTED",
                    "follow_up_status": "hold_for_recheck",
                    "follow_up_reason_code": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
                    "follow_up_event_type": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
                    "follow_up_summary_en": (
                        "Post-review hold for recheck is selected: keep the same target on a cautious recheck contour."
                    ),
                    "follow_up_summary_ru": (
                        "Выбран post-review hold for recheck: удерживайте ту же цель на осторожном recheck-контуре."
                    ),
                    "follow_up_allowed_when_en": (
                        "Run a cautious safe recheck for the same target before resuming the next general observation objective."
                    ),
                    "follow_up_allowed_when_ru": (
                        "Сначала выполните осторожный safe recheck для той же цели, затем возвращайтесь к следующей общей observation-цели."
                    ),
                },
            }
        )
    )

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["follow_up_status"] == "hold_for_recheck"
    assert app._active_observation_objective["reason_code"] == "OBJECTIVE_POST_REVIEW_HOLD_SELECTED"
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "confirmed"
    assert "recheck contour" in app._qiki_last_response.consequence.summary.en.lower()
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.allowed_when is not None
    assert "safe recheck" in app._qiki_last_response.legality.allowed_when.en.lower()
    assert published_actions[-1]["event_type"] == "HIDDEN_EVENT_RECHECK_HOLD_SELECTED"
    assert published_actions[-1]["procedure_name"] == "safe_pause_slow_resume"
    assert published_actions[-1]["target_designator"] == "ALLY-4D1ED5"
    assert published_actions[-1]["route_role"] == "deviation"
    assert messages[-1] == "Post-review action published: waiting for canonical follow-up update"
    assert refreshed


def test_resume_observation_follow_up_changes_qiki_next_step(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []
    published_actions: list[dict[str, object]] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))

    async def _publish_action(payload: dict[str, object]) -> None:
        published_actions.append(payload)

    app._publish_operator_action = _publish_action  # type: ignore[method-assign]
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": "qiki.events.v1.operator.objectives",
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
        "summary_ru": "Post-review hold for recheck выбран.",
        "summary_en": "Post-review hold for recheck is selected.",
        "reason_code": "OBJECTIVE_POST_REVIEW_HOLD_SELECTED",
        "follow_up_status": "hold_for_recheck",
        "follow_up_reason_code": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
        "follow_up_event_type": "HIDDEN_EVENT_RECHECK_HOLD_SELECTED",
        "follow_up_summary_en": "Post-review hold for recheck is selected.",
        "follow_up_summary_ru": "Выбран post-review hold for recheck.",
        "follow_up_allowed_when_en": "Run a cautious safe recheck before resuming.",
        "follow_up_allowed_when_ru": "Сначала выполните осторожный safe recheck, затем возобновляйте contour.",
    }
    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=35)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Resume pending", "ru": "Возобновление ожидается"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SLOW_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
                "allowed_when": {
                    "en": "Run a cautious safe recheck before resuming.",
                    "ru": "Сначала выполните осторожный safe recheck, затем возобновляйте contour.",
                },
            },
            "trust_signals": [],
            "consequence": {
                "status": "confirmed",
                "summary": {"en": "Post-review hold for recheck is selected.", "ru": "Выбран post-review hold."},
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    asyncio.run(app._resume_observation_follow_up())
    asyncio.run(
        app._on_event(
            {
                "subject": "qiki.events.v1.operator.objectives",
                "data": {
                    **app._active_observation_objective,
                    "source": "q_core_intents",
                    "reason_code": "OBJECTIVE_RESUME_OBSERVATION_SELECTED",
                    "follow_up_status": "resume_observation",
                    "follow_up_reason_code": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
                    "follow_up_event_type": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
                    "follow_up_summary_en": (
                        "Observation resume is selected: close hold_for_recheck for ALLY-4D1ED5 and return to one "
                        "cautious safe observation step."
                    ),
                    "follow_up_summary_ru": (
                        "Выбран resume observation: hold_for_recheck закрыт для ALLY-4D1ED5 и contour возвращён "
                        "к одному cautious safe observation."
                    ),
                    "follow_up_allowed_when_en": (
                        "Issue one cautious safe observation for ALLY-4D1ED5 to resume the observation contour "
                        "on the canonical path."
                    ),
                    "follow_up_allowed_when_ru": (
                        "Теперь задайте один cautious safe observation для ALLY-4D1ED5, чтобы возобновить "
                        "observation contour на каноническом path."
                    ),
                },
            }
        )
    )

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["follow_up_status"] == "resume_observation"
    assert app._active_observation_objective["reason_code"] == "OBJECTIVE_RESUME_OBSERVATION_SELECTED"
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "confirmed"
    assert "resume is selected" in app._qiki_last_response.consequence.summary.en.lower()
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.allowed_when is not None
    assert "safe observation" in app._qiki_last_response.legality.allowed_when.en.lower()
    assert published_actions[-1]["event_type"] == "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED"
    assert messages[-1] == "Resume action published: waiting for canonical follow-up update"
    assert refreshed


def test_resumed_safe_observation_records_reconfirmed_result_on_same_objective(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    published_events: list[tuple[str, dict[str, object]]] = []

    async def _publish_operator_event(subject: str, payload: dict[str, object]) -> None:
        published_events.append((subject, payload))

    async def _run_procedure(_name: str) -> None:
        return None

    async def _wait_for_completion(_name: str, _timeout: float) -> bool:
        return True

    async def _wait_for_effect(_definition: object, _timeout: float) -> BilingualText:
        return BilingualText(en="running x1.00", ru="выполнение x1.00")

    app._publish_operator_event = _publish_operator_event  # type: ignore[method-assign]
    app._run_procedure = _run_procedure  # type: ignore[method-assign]
    app._wait_for_procedure_completion = _wait_for_completion  # type: ignore[method-assign]
    app._wait_for_procedure_effect = _wait_for_effect  # type: ignore[method-assign]
    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: None)

    app._telemetry["sim_state"] = {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": "qiki.events.v1.operator.objectives",
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
        "track_id": "track-42",
        "track_label": "ALLY-4D1ED5",
        "summary_ru": "Resume observation выбран.",
        "summary_en": "Resume observation is selected.",
        "reason_code": "OBJECTIVE_RESUME_OBSERVATION_SELECTED",
        "follow_up_status": "resume_observation",
        "follow_up_reason_code": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
        "follow_up_event_type": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
        "follow_up_summary_en": "Resume observation is selected.",
        "follow_up_summary_ru": "Выбран resume observation.",
        "follow_up_allowed_when_en": "Issue one cautious safe observation for ALLY-4D1ED5.",
        "follow_up_allowed_when_ru": "Теперь задайте один cautious safe observation для ALLY-4D1ED5.",
    }
    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=36)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Safe observation ready", "ru": "Безопасное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SAFE_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
                "allowed_when": {
                    "en": "Issue one cautious safe observation for ALLY-4D1ED5.",
                    "ru": "Теперь задайте один cautious safe observation для ALLY-4D1ED5.",
                },
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Safe observation is prepared.", "ru": "Безопасное наблюдение подготовлено."},
            },
            "proposals": [
                {
                    "proposal_id": "qiki-safe-observation-resume",
                    "title": {"en": "Run safe observation", "ru": "Запустить безопасное наблюдение"},
                    "justification": {"en": "ok", "ru": "ок"},
                    "confidence": 1.0,
                    "priority": 85,
                    "suggested_questions": [],
                    "proposed_actions": [
                        {
                            "kind": "ORION_PROCEDURE",
                            "subject": "orionv.procedure",
                            "name": "safe_pause_resume",
                            "parameters": {
                                "observation_track_id": "track-42",
                                "observation_track_label": "ALLY-4D1ED5",
                                "observation_track_range_m": 3200.0,
                                "observation_track_quality": 0.98,
                            },
                            "dry_run": False,
                        }
                    ],
                }
            ],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))

    app._seal_pending_decision(app._qiki_pending_action)  # M5: реальный поток пломбирует до execute
    asyncio.run(app._execute_qiki_pending_action())

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["objective_id"] == "observation-123"
    assert app._active_observation_objective["request_id"] == "req-1"
    assert app._active_observation_objective["reason_code"] == "OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED"
    assert app._active_observation_objective["observation_result_status"] == "reconfirmed"
    assert app._active_observation_objective["observation_result_reason_code"] == (
        "OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED"
    )
    assert not app._active_observation_objective.get("follow_up_status")
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "confirmed"
    assert "reconfirmed" in app._qiki_last_response.consequence.summary.en.lower()
    assert app._qiki_last_response.legality is not None
    assert app._qiki_last_response.legality.allowed_when is not None
    assert "next observation objective" in app._qiki_last_response.legality.allowed_when.en.lower()
    assert published_events[-1][0] == "qiki.events.v1.operator.objectives"
    assert published_events[-1][1]["objective_id"] == "observation-123"
    assert published_events[-1][1]["observation_result_status"] == "reconfirmed"
    assert messages[-1] == "QIKI execution confirmed: процедура safe_pause_resume"


def test_resumed_safe_observation_records_signature_changed_result_on_same_objective(monkeypatch) -> None:
    app = OrionVApp()
    published_events: list[tuple[str, dict[str, object]]] = []

    async def _publish_operator_event(subject: str, payload: dict[str, object]) -> None:
        published_events.append((subject, payload))

    async def _run_procedure(_name: str) -> None:
        return None

    async def _wait_for_completion(_name: str, _timeout: float) -> bool:
        return True

    async def _wait_for_effect(_definition: object, _timeout: float) -> BilingualText:
        return BilingualText(en="running x1.00", ru="выполнение x1.00")

    app._publish_operator_event = _publish_operator_event  # type: ignore[method-assign]
    app._run_procedure = _run_procedure  # type: ignore[method-assign]
    app._wait_for_procedure_completion = _wait_for_completion  # type: ignore[method-assign]
    app._wait_for_procedure_effect = _wait_for_effect  # type: ignore[method-assign]
    app._set_help_text = lambda _text: None  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: None)

    app._telemetry["sim_state"] = {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": "qiki.events.v1.operator.objectives",
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
        "track_id": "track-42",
        "track_label": "ALLY-4D1ED5",
        "summary_ru": "Resume observation выбран.",
        "summary_en": "Resume observation is selected.",
        "reason_code": "OBJECTIVE_RESUME_OBSERVATION_SELECTED",
        "follow_up_status": "resume_observation",
        "follow_up_reason_code": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
        "follow_up_event_type": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
        "follow_up_summary_en": "Resume observation is selected.",
        "follow_up_summary_ru": "Выбран resume observation.",
        "follow_up_allowed_when_en": "Issue one cautious safe observation for ALLY-4D1ED5.",
        "follow_up_allowed_when_ru": "Теперь задайте один cautious safe observation для ALLY-4D1ED5.",
    }
    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=49)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Safe observation ready", "ru": "Безопасное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SAFE_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
                "allowed_when": {
                    "en": "Issue one cautious safe observation for ALLY-4D1ED5.",
                    "ru": "Теперь задайте один cautious safe observation для ALLY-4D1ED5.",
                },
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Safe observation is prepared.", "ru": "Безопасное наблюдение подготовлено."},
            },
            "proposals": [
                {
                    "proposal_id": "qiki-safe-observation-signature-change",
                    "title": {"en": "Run safe observation", "ru": "Запустить безопасное наблюдение"},
                    "justification": {"en": "ok", "ru": "ок"},
                    "confidence": 1.0,
                    "priority": 85,
                    "suggested_questions": [],
                    "proposed_actions": [
                        {
                            "kind": "ORION_PROCEDURE",
                            "subject": "orionv.procedure",
                            "name": "safe_pause_resume",
                            "parameters": {
                                "observation_track_id": "track-42",
                                "observation_track_label": "ALLY-4D1ED5",
                                "observation_track_range_m": 3200.0,
                                "observation_track_quality": 0.98,
                            },
                            "dry_run": False,
                        }
                    ],
                }
            ],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))
    asyncio.run(
        app._on_track(
            {
                "data": {
                    "track_id": "track-42",
                    "transponder_id": "SPOOF-42",
                    "range_m": 3100.0,
                    "quality": 0.93,
                    "status": "TRACKED",
                }
            }
        )
    )
    app._seal_pending_decision(app._qiki_pending_action)  # M5: реальный поток пломбирует до execute
    asyncio.run(app._execute_qiki_pending_action())

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["observation_result_status"] == "signature_changed"
    assert app._active_observation_objective["observation_result_reason_code"] == (
        "OBJECTIVE_RESUMED_OBSERVATION_SIGNATURE_CHANGED"
    )
    assert app._active_observation_objective["track_id"] == "track-42"
    assert app._active_observation_objective["track_label"] == "SPOOF-42"
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert "signature changed" in app._qiki_last_response.consequence.summary.en.lower()
    assert published_events[-1][1]["observation_result_status"] == "signature_changed"


def test_live_observation_track_snapshot_logs_public_identity_without_format_noise(
    monkeypatch,
    caplog,
) -> None:
    app = OrionVApp()
    caplog.set_level(logging.INFO, logger="qiki.services.operator_console.orion_v.app")
    monkeypatch.setattr("qiki.services.operator_console.orion_v.app.time.time", lambda: 105.0)
    app._latest_radar_tracks["public-42"] = {
        "track_id": "public-42",
        "transponder_id": "SPOOF-42",
        "range_m": 3100.0,
        "quality": 0.93,
        "_orion_source_timestamp_unix_s": 100.0,
    }

    snapshot = app._live_observation_track_snapshot(
        {
            "objective_id": "objective-1",
            "request_id": "request-1",
            "target_designator": "ALLY-4D1ED5",
            "track_id": "track-42",
            "track_label": "ALLY-4D1ED5",
            "public_track_id": "public-42",
            "public_track_label": "ALLY-4D1ED5",
        },
        fallback_parameters={
            "track_id": "track-42",
            "track_label": "ALLY-4D1ED5",
            "public_track_id": "public-42",
            "public_track_label": "ALLY-4D1ED5",
        },
    )

    assert snapshot is not None
    assert snapshot["track_id"] == "track-42"
    assert snapshot["track_label"] == "SPOOF-42"
    record = next(
        record for record in caplog.records if record.msg.startswith("Resume live snapshot:")
    )
    message = record.getMessage()
    assert "qcore_track_id=track-42" in message
    assert "public_track_id=public-42" in message
    assert "public_label=SPOOF-42" in message
    assert "live_track_id=public-42" in message


def test_resumed_safe_observation_uses_public_track_binding_for_live_signature_change(monkeypatch) -> None:
    app = OrionVApp()
    published_events: list[tuple[str, dict[str, object]]] = []

    async def _publish_operator_event(subject: str, payload: dict[str, object]) -> None:
        published_events.append((subject, payload))

    async def _run_procedure(_name: str) -> None:
        return None

    async def _wait_for_completion(_name: str, _timeout: float) -> bool:
        return True

    async def _wait_for_effect(_definition: object, _timeout: float) -> BilingualText:
        return BilingualText(en="running x1.00", ru="выполнение x1.00")

    app._publish_operator_event = _publish_operator_event  # type: ignore[method-assign]
    app._run_procedure = _run_procedure  # type: ignore[method-assign]
    app._wait_for_procedure_completion = _wait_for_completion  # type: ignore[method-assign]
    app._wait_for_procedure_effect = _wait_for_effect  # type: ignore[method-assign]
    app._set_help_text = lambda _text: None  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: None)

    app._telemetry["sim_state"] = {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}
    app._active_observation_objective = {
        "event_schema_version": 1,
        "source": "q_core_intents",
        "subject": "qiki.events.v1.operator.objectives",
        "timestamp": "2026-03-13T00:00:00+00:00",
        "ts_epoch": 1.0,
        "kind": "observation_objective_update",
        "objective_id": "observation-bridge-123",
        "objective_type": "observation",
        "status": "confirmed",
        "observation_style": "slow",
        "procedure_name": "safe_pause_slow_resume",
        "route_role": "deviation",
        "request_id": "req-bridge-1",
        "proposal_id": "prop-bridge-1",
        "mode": "FACTORY",
        "target_designator": "ALLY-4D1ED5",
        "track_visible": True,
        "track_id": "qcore-track-42",
        "track_label": "ALLY-4D1ED5",
        "summary_ru": "Resume observation выбран.",
        "summary_en": "Resume observation is selected.",
        "reason_code": "OBJECTIVE_RESUME_OBSERVATION_SELECTED",
        "follow_up_status": "resume_observation",
        "follow_up_reason_code": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
        "follow_up_event_type": "HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED",
        "follow_up_summary_en": "Resume observation is selected.",
        "follow_up_summary_ru": "Выбран resume observation.",
        "follow_up_allowed_when_en": "Issue one cautious safe observation for ALLY-4D1ED5.",
        "follow_up_allowed_when_ru": "Теперь задайте один cautious safe observation для ALLY-4D1ED5.",
    }
    asyncio.run(
        app._on_track(
            {
                "data": {
                    "track_id": "bridge-track-77",
                    "transponder_id": "ALLY-4D1ED5",
                    "range_m": 3200.0,
                    "quality": 0.98,
                    "status": "TRACKED",
                }
            }
        )
    )
    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=50)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Safe observation ready", "ru": "Безопасное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SAFE_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
                "allowed_when": {
                    "en": "Issue one cautious safe observation for ALLY-4D1ED5.",
                    "ru": "Теперь задайте один cautious safe observation для ALLY-4D1ED5.",
                },
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Safe observation is prepared.", "ru": "Безопасное наблюдение подготовлено."},
            },
            "proposals": [
                {
                    "proposal_id": "qiki-safe-observation-bridge-signature-change",
                    "title": {"en": "Run safe observation", "ru": "Запустить безопасное наблюдение"},
                    "justification": {"en": "ok", "ru": "ок"},
                    "confidence": 1.0,
                    "priority": 85,
                    "suggested_questions": [],
                    "proposed_actions": [
                        {
                            "kind": "ORION_PROCEDURE",
                            "subject": "orionv.procedure",
                            "name": "safe_pause_resume",
                            "parameters": {
                                "observation_track_id": "qcore-track-42",
                                "observation_track_label": "ALLY-4D1ED5",
                                "observation_track_range_m": 3200.0,
                                "observation_track_quality": 0.98,
                            },
                            "dry_run": False,
                        }
                    ],
                }
            ],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))
    assert app._active_observation_objective["public_track_id"] == "bridge-track-77"
    asyncio.run(
        app._on_track(
            {
                "data": {
                    "track_id": "bridge-track-77",
                    "transponder_id": "SPOOF-42",
                    "range_m": 3100.0,
                    "quality": 0.93,
                    "status": "TRACKED",
                }
            }
        )
    )

    app._seal_pending_decision(app._qiki_pending_action)  # M5: реальный поток пломбирует до execute
    asyncio.run(app._execute_qiki_pending_action())

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["observation_result_status"] == "signature_changed"
    assert app._active_observation_objective["track_id"] == "qcore-track-42"
    assert app._active_observation_objective["track_label"] == "SPOOF-42"
    assert app._active_observation_objective["public_track_id"] == "bridge-track-77"
    assert app._active_observation_objective["public_track_label"] == "SPOOF-42"
    assert published_events[-1][1]["observation_result_status"] == "signature_changed"


def test_resume_comparison_log_keeps_qcore_and_public_identities(caplog) -> None:
    app = OrionVApp()
    caplog.set_level(logging.INFO, logger="qiki.services.operator_console.orion_v.app")

    result = app._build_resume_observation_result(
        {
            "objective_id": "objective-compare-1",
            "request_id": "request-compare-1",
            "target_designator": "ALLY-4D1ED5",
            "follow_up_status": "resume_observation",
            "track_id": "qcore-track-42",
            "track_label": "ALLY-42",
            "public_track_id": "public-track-42",
            "public_track_label": "ALLY-42",
        },
        parameters={
            "observation_track_id": "qcore-track-42",
            "observation_track_label": "SPOOF-42",
            "public_track_id": "public-track-99",
            "public_track_label": "SPOOF-42",
            "source": "live_cache",
            "label_source": "parameters",
            "source_timestamp_unix_s": 100.0,
            "freshness_s": 2.5,
        },
    )

    assert result is not None
    assert result["status"] == "signature_changed"
    record = next(record for record in caplog.records if record.msg.startswith("Resume comparison:"))
    message = record.getMessage()
    assert "objective_id=objective-compare-1" in message
    assert "request_id=request-compare-1" in message
    assert "previous_track_id=qcore-track-42" in message
    assert "previous_public_track_id=public-track-42" in message
    assert "comparison_track_id=qcore-track-42" in message
    assert "comparison_public_track_id=public-track-99" in message
    assert "comparison_label=SPOOF-42" in message
    assert "result_candidate=signature_changed" in message
    assert "fallback_reason=not_applicable" in message


def test_observation_objective_enrichment_promotes_live_public_track_to_visible_state() -> None:
    app = OrionVApp()
    app._latest_radar_tracks = {
        "bridge-track-77": {
            "track_id": "bridge-track-77",
            "transponder_id": "ALLY-4D1ED5",
            "range_m": 3100.0,
            "quality": 0.93,
            "status": "TRACKED",
        }
    }
    app._active_observation_objective = {
        "objective_id": "observation-77",
        "target_designator": "ALLY-4D1ED5",
        "track_visible": False,
        "track_label": None,
        "track_id": None,
        "public_track_id": None,
        "public_track_label": None,
    }

    app._enrich_active_observation_with_live_public_track()

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["track_visible"] is True
    assert app._active_observation_objective["public_track_id"] == "bridge-track-77"
    assert app._active_observation_objective["public_track_label"] == "ALLY-4D1ED5"
    assert app._active_observation_objective["track_label"] == "ALLY-4D1ED5"
    assert app._active_observation_objective["track_range_m"] == 3100.0
    assert app._active_observation_objective["track_quality"] == 0.93


def test_observation_objective_enrichment_preserves_pre_resume_label_for_signature_comparison() -> None:
    app = OrionVApp()
    app._latest_radar_tracks = {
        "bridge-track-77": {
            "track_id": "bridge-track-77",
            "transponder_id": "SPOOF-42",
            "range_m": 3100.0,
            "quality": 0.93,
            "status": "TRACKED",
        }
    }
    app._active_observation_objective = {
        "objective_id": "observation-77",
        "target_designator": "ALLY-4D1ED5",
        "follow_up_status": "resume_observation",
        "track_visible": True,
        "track_label": "ALLY-4D1ED5",
        "track_id": "qcore-track-42",
        "public_track_id": "bridge-track-77",
        "public_track_label": "ALLY-4D1ED5",
    }

    app._enrich_active_observation_with_live_public_track()

    assert app._active_observation_objective is not None
    assert app._active_observation_objective["track_label"] == "ALLY-4D1ED5"
    assert app._active_observation_objective["public_track_label"] == "SPOOF-42"
    assert app._active_observation_objective["track_visible"] is True


def test_execute_qiki_pending_slow_procedure_waits_for_telemetry_effect(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))
    app._telemetry = {"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}}

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=33)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Slow observation ready", "ru": "Медленное наблюдение готово"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "resource",
                "reason_code": "SLOW_OBSERVATION_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Procedure prepared", "ru": "Процедура подготовлена"},
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))
    app._qiki_pending_action = {
        "action_kind": "ORION_PROCEDURE",
        "name": "safe_pause_slow_resume",
        "title_ru": "Запустить медленное наблюдение",
    }

    async def _fake_run(name: str) -> None:
        app._procedure_engine.state.procedure_name = name
        app._procedure_engine.state.status = "ok"
        await asyncio.sleep(0.15)
        app._telemetry["sim_state"] = {"fsm_state": "RUNNING", "paused": False, "speed": 0.25}

    async def _fake_wait(name: str, timeout_s: float) -> bool:
        return name == "safe_pause_slow_resume" and timeout_s > 0

    monkeypatch.setattr(app, "_run_procedure", _fake_run)
    monkeypatch.setattr(app, "_wait_for_procedure_completion", _fake_wait)

    app._seal_pending_decision(app._qiki_pending_action)  # M5: реальный поток пломбирует до execute
    asyncio.run(app._execute_qiki_pending_action())

    assert app._qiki_pending_action is None
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "confirmed"
    assert "speed=0.25" in app._qiki_last_response.consequence.telemetry_confirmation.ru
    assert messages[-1] == "QIKI execution confirmed: процедура safe_pause_slow_resume"
    assert refreshed


def test_execute_qiki_pending_combat_entry_procedure_confirms_rcs_effect(monkeypatch) -> None:
    app = OrionVApp()
    messages: list[str] = []
    refreshed: list[bool] = []

    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: refreshed.append(cb == app._refresh_ui))
    app._telemetry = {"sim_state": {"fsm_state": "RUNNING", "paused": False, "speed": 1.0}}
    app._snapshot = {
        "propulsion": {
            "rcs": {
                "axis": "forward",
                "command_pct": 35.0,
                "time_left_s": 1.8,
            }
        }
    }

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=45)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Combat entry ready", "ru": "Вход в бой подготовлен"},
                "body": {"en": "ok", "ru": "ок"},
            },
            "legality": {
                "status": "allowed",
                "domain": "protocol",
                "reason_code": "COMBAT_ENTRY_PROCEDURE_READY",
                "reason": {"en": "ok", "ru": "ок"},
            },
            "trust_signals": [],
            "consequence": {
                "status": "pending",
                "summary": {"en": "Procedure prepared", "ru": "Процедура подготовлена"},
            },
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }
    app._qiki_pending[str(payload["data"]["request_id"])] = (0.0, "test")  # M0c: ответ только на свой запрос
    asyncio.run(app._on_qiki_response(payload))
    app._qiki_pending_action = {
        "action_kind": "ORION_PROCEDURE",
        "name": "hostile_rcs_intercept_burst",
        "title_ru": "Запустить манёвр входа в бой",
    }

    async def _fake_run(name: str) -> None:
        app._procedure_engine.state.procedure_name = name
        app._procedure_engine.state.status = "ok"

    async def _fake_wait(name: str, timeout_s: float) -> bool:
        return name == "hostile_rcs_intercept_burst" and timeout_s > 0

    monkeypatch.setattr(app, "_run_procedure", _fake_run)
    monkeypatch.setattr(app, "_wait_for_procedure_completion", _fake_wait)

    app._seal_pending_decision(app._qiki_pending_action)  # M5: реальный поток пломбирует до execute
    asyncio.run(app._execute_qiki_pending_action())

    assert app._qiki_pending_action is None
    assert app._qiki_last_response is not None
    assert app._qiki_last_response.consequence is not None
    assert app._qiki_last_response.consequence.status == "confirmed"
    assert "command_pct=35.0" in app._qiki_last_response.consequence.telemetry_confirmation.ru
    assert messages[-1] == "QIKI execution confirmed: процедура hostile_rcs_intercept_burst"
    assert refreshed
    combat_events = [
        event
        for event in app._events_store.snapshot()
        if event.get("subject") == "qiki.events.v1.operator.combat"
    ]
    assert len(combat_events) == 1
    payload = combat_events[0].get("data")
    assert isinstance(payload, dict)
    assert payload.get("event_type") == "COMBAT_ENTRY_CONFIRMED"
    assert payload.get("reason_code") == "COMBAT_EVENT_INTERCEPT_BURST_CONFIRMED"
    assert payload.get("target") == "UNBT9999"
    assert "боевой импульс входа в бой" in str(payload.get("message"))


def test_on_qiki_response_denies_unsolicited(monkeypatch) -> None:
    """M0c: непрошеный ответ на qiki.responses.qiki (нет нашего pending) отклоняется целиком."""
    app = OrionVApp()
    messages: list[str] = []
    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    monkeypatch.setattr(app, "call_later", lambda cb: None)

    payload = {
        "data": {
            "version": 1,
            "request_id": str(UUID(int=666)),
            "ok": True,
            "mode": "FACTORY",
            "reply": {
                "title": {"en": "Injected", "ru": "Инъекция"},
                "body": {"en": "spoofed response", "ru": "подложный ответ"},
            },
            "legality": None,
            "trust_signals": [],
            "consequence": None,
            "proposals": [],
            "warnings": [],
            "error": None,
        }
    }

    # pending НЕ регистрируем — это чужой publish (смок-канал №8в)
    asyncio.run(app._on_qiki_response(payload))

    assert app._qiki_last_response is None
    assert len(app._qiki_voice_ledger) == 0
    assert app._qiki_pending_action is None
    assert "[QIKI_RESP_UNSOLICITED]" in messages[-1]
