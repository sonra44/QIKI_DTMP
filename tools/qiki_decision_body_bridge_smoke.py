"""M7-M9 live-proof: одобренное решение проводится к телу через ГОТОВЫЙ конвейер.

Гонит настоящий run_attach_pipeline (нового body-кода нет) через мост:
1) предусловие питания блокирует эффект — тело не тронуто;
2) при чистых предусловиях мост вызывает конвейер, модуль установлен, ступени
   ack/effect/audit проставлены;
3) JSONL-трасса жизненного цикла экспортируется.
"""

from __future__ import annotations

import json

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    ModuleAttachRequest,
    ModulePassport,
    run_attach_pipeline,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.shared.command_decision import (
    CommandIntent,
    authorize_publish,
    seal_decision,
)
from qiki.shared.decision_body_bridge import (
    bridge_decision_to_body,
    decision_trace_jsonl,
    decision_trace_record,
)

MOUNT = "F00"


def _published_decision():
    intent = CommandIntent(
        kind="NATS_COMMAND",
        subject="qiki.commands.control",
        name="attach.module",
        parameters={"module_id": "test_sensor_module_001", "mount": MOUNT},
        operator_facing_title="Установить сенсорный модуль на F00",
    )
    sealed = seal_decision(decision_id="bridge-live-1", intent=intent)
    kind, subject, name, params = sealed.sealed_command
    return authorize_publish(
        sealed, candidate_kind=kind, candidate_subject=subject, candidate_name=name, candidate_parameters=params
    ).decision


def _real_attach_runner():
    """Тонкая обёртка над ГОТОВЫМ конвейером — нового body-кода нет."""
    store = EventStore(backend="memory")
    body = BodyConfigSnapshot.skeleton()
    request = ModuleAttachRequest(
        request_id="bridge-live-attach",
        module_id="test_sensor_module_001",
        mount_point=MOUNT,
        passport=ModulePassport(
            module_id="test_sensor_module_001",
            module_class="sensor",
            mount_point=MOUNT,
            provided_capabilities=("basic_sensor_read",),
        ),
    )
    attach_decision, updated_body = run_attach_pipeline(body, request, store=store)
    attached = attach_decision.status == "attached"
    return attached, attach_decision.audit_event_id


def main() -> None:
    # 1) предусловие питания блокирует — тело не тронуто.
    called = {"n": 0}

    def _guarded_runner():
        called["n"] += 1
        return _real_attach_runner()

    blocked = bridge_decision_to_body(
        _published_decision(), power_blocked=True, thermal_blocked=False, attach_runner=_guarded_runner
    )
    assert blocked.reached_body is False and called["n"] == 0
    print("[smoke] предусловие питания OK: конвейер не вызван, тело не тронуто")

    # 2) чистые предусловия — мост вызывает РЕАЛЬНЫЙ конвейер.
    ok = bridge_decision_to_body(
        _published_decision(), power_blocked=False, thermal_blocked=False, attach_runner=_real_attach_runner
    )
    assert ok.reached_body is True, "мост не дошёл до тела"
    assert ok.decision.stages.effect.value == "ok", f"effect={ok.decision.stages.effect}"
    assert ok.decision.stages.audit.value == "ok", "audit-событие не записано"
    print(f"[smoke] мост→тело OK: модуль установлен, ступени "
          f"ack={ok.decision.stages.ack.value} effect={ok.decision.stages.effect.value} "
          f"audit={ok.decision.stages.audit.value}")

    # 3) JSONL-трасса жизненного цикла.
    trace = decision_trace_jsonl([
        decision_trace_record(blocked.decision, extra={"phase": "power_blocked"}),
        decision_trace_record(ok.decision, extra={"phase": "attached"}),
    ])
    lines = trace.splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["stages"]["effect"] == "ok"
    print("[smoke] JSONL-трасса OK: 2 записи жизненного цикла экспортированы")

    print("[smoke] M7-M9 PASS: мост протестирован против готового конвейера ИЗОЛИРОВАННО "
          "(в живой путь консоли пока не подключён), трасса есть")


if __name__ == "__main__":
    main()
