"""P3 (ADR-0019 §3): параметры пломбы доезжают до тела; отказы — через конвейер.

RED-тест первым: контракт «пломба == дошедшее до ModuleAttachRequest».
До P3 runner игнорировал параметры (ставил константный сенсор@F06) — эти тесты
обязаны это ловить.
"""

from __future__ import annotations

from uuid import uuid4

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    get_body_structure_interactive_controller,
    reset_body_structure_interactive_state,
)
from qiki.shared.command_decision import authorize_publish


def _sealed_app(parameters: dict) -> OrionVApp:
    app = OrionVApp()
    app._set_help_text = lambda *a, **k: None  # type: ignore
    action = {
        "action_kind": "BODY_ATTACH",
        "title_ru": "Установка",
        "subject": "orionv.body",
        "name": "attach.module",
        "parameters": parameters,
        "dry_run": False,
    }
    app._seal_pending_decision(action)
    sealed = app._decision_store.get(app._pending_decision_id)
    kind, subject, name, params = sealed.sealed_command
    app._decision_store.put(
        authorize_publish(
            sealed, candidate_kind=kind, candidate_subject=subject,
            candidate_name=name, candidate_parameters=params,
        ).decision
    )
    return app


def _params(module_id="comm_antenna_module_001", mount="F03", module_class="antenna", **extra) -> dict:
    params = {
        "module_id": module_id,
        "mount": mount,
        "module_class": module_class,
        "provided_capabilities": ["comms_relay_extend"],
        "quantity": 1,
        "passport_damaged": False,
    }
    params.update(extra)
    return params


def setup_function() -> None:
    reset_body_structure_interactive_state()


def teardown_function() -> None:
    reset_body_structure_interactive_state()


def test_red_sealed_params_reach_body() -> None:
    """КОНТРАКТ: тело получает ровно то, что запломбировано (не константы)."""
    app = _sealed_app(_params())
    attached, audit_event_id = app._body_attach_runner()
    assert attached is True and audit_event_id
    body = get_body_structure_interactive_controller().snapshot().body
    installed = [str(m.get("module_id")) for m in body.modules]
    assert installed == ["comm_antenna_module_001"], installed
    assert body.face_occupancy.get("F03") != "free"
    assert body.face_occupancy.get("F06") == "free"  # константный путь НЕ сработал


def test_occupied_mount_refused_via_pipeline_with_own_audit() -> None:
    """Занятость — через конвейер (без already_attached-шортката, без stale audit)."""
    first = _sealed_app(_params())
    assert first._body_attach_runner()[0] is True
    first_audit = get_body_structure_interactive_controller().snapshot().decision.audit_event_id

    second = _sealed_app(_params(module_id="test_sensor_module_001", module_class="sensor",
                                 provided_capabilities=["basic_sensor_read"]))
    attached, audit_event_id = second._body_attach_runner()
    assert attached is False
    assert audit_event_id and audit_event_id != first_audit  # СВОЁ событие отказа
    body = get_body_structure_interactive_controller().snapshot().body
    assert len(body.modules) == 1  # второй модуль не встал


def test_forbidden_class_refused_via_pipeline() -> None:
    app = _sealed_app(_params(module_id="rcs_cluster_module_001", module_class="rcs-cluster",
                              provided_capabilities=["rcs_aux_thrust"], mount="F02"))
    attached, audit_event_id = app._body_attach_runner()
    assert attached is False and audit_event_id
    assert get_body_structure_interactive_controller().snapshot().body.modules == ()


def test_damaged_passport_refused_canonically() -> None:
    """passport_damaged -> паспорт не собирается -> канонный отказ конвейера."""
    app = _sealed_app(_params(module_id="salvage_sensor_damaged_001", module_class="sensor",
                              provided_capabilities=[], passport_damaged=True, mount="F01"))
    attached, audit_event_id = app._body_attach_runner()
    assert attached is False and audit_event_id
    assert get_body_structure_interactive_controller().snapshot().body.modules == ()


def test_no_decision_no_body_touch() -> None:
    app = OrionVApp()
    app._set_help_text = lambda *a, **k: None  # type: ignore
    attached, audit_event_id = app._body_attach_runner()
    assert attached is False and audit_event_id == ""
    assert get_body_structure_interactive_controller().snapshot().body.modules == ()
