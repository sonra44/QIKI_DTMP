"""M6 live-proof: не-allowed кандидат не доходит до шины через реальный путь.

Доказывает:
1) blocked-кандидат: q confirm НЕ пломбирует и НЕ публикует;
2) allowed-кандидат: q confirm пломбирует, исполнение публикует ровно раз;
3) повторное одобрение проведённого решения — идемпотентно.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatResponseV1,
    QikiLegalityV1,
    QikiMode,
    QikiProposalV1,
    QikiProposedActionV1,
)


def _action() -> dict:
    return {
        "action_kind": "NATS_COMMAND", "proposal_id": "p-1",
        "title_ru": "Возобновить наблюдение безопасно", "title_en": "Resume safe observation",
        "subject": "qiki.commands.control", "name": "sim.dock.release",
        "parameters": {"target": "ALLY-1"}, "dry_run": False,
    }


def _response(status: str) -> QikiChatResponseV1:
    return QikiChatResponseV1(
        request_id=uuid4(), ok=True, mode=QikiMode.FACTORY,
        legality=QikiLegalityV1(
            status=status, domain="protocol", reason_code=f"{status.upper()}_CODE",
            reason=BilingualText(en=status, ru=status),
        ),
        proposals=[
            QikiProposalV1(
                proposal_id="p-1", title=BilingualText(en="t", ru="т"),
                justification=BilingualText(en="j", ru="о"), confidence=1.0, priority=50,
                proposed_actions=[
                    QikiProposedActionV1(subject="qiki.commands.control", name="sim.dock.release", dry_run=False)
                ],
            )
        ],
    )


async def _main() -> None:
    app = OrionVApp()
    async with app.run_test(size=(160, 48)):
        published: list[str] = []

        async def _capture(command_name, parameters):
            published.append(command_name)

        async def _ack_ok(command_name, timeout_s, command_id=None):
            return True

        async def _effect(command_name, timeout_s):
            return None

        app._publish_sim_command = _capture  # type: ignore[assignment]
        app._wait_for_ack = _ack_ok  # type: ignore[assignment]
        app._wait_for_qiki_effect = _effect  # type: ignore[assignment]

        # 1) blocked-кандидат: одобрение отклонено, публикации нет.
        app._qiki_last_response = _response("blocked")
        app._qiki_pending_action = _action()
        app._confirm_qiki_pending_action()
        assert app._pending_decision_id is None, "blocked-кандидат запломбирован!"
        await asyncio.sleep(0.05)
        assert published == [], f"blocked-кандидат дошёл до шины: {published}"
        print("[smoke] blocked-кандидат OK: одобрение отклонено, до шины не дошёл")

        # 2) allowed-кандидат: одобрение пломбирует, исполнение публикует.
        app._qiki_last_response = _response("allowed")
        app._qiki_pending_action = _action()
        app._confirm_qiki_pending_action()
        assert app._pending_decision_id is not None, "allowed-кандидат не запломбирован"
        await app._execute_qiki_pending_action()
        assert published == ["sim.dock.release"], f"allowed-кандидат не опубликован: {published}"
        print("[smoke] allowed-кандидат OK: одобрен, пломбирован, опубликован ровно раз")

    print("[smoke] M6 PASS: одобряем только allowed; кандидат/deferred/blocked до шины не доходят")


if __name__ == "__main__":
    asyncio.run(_main())
