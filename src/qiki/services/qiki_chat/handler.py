from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatRequestV1,
    QikiChatResponseV1,
    QikiErrorV1,
    QikiMode,
    QikiProposalV1,
    QikiProposedActionV1,
    QikiReplyV1,
)
from qiki.shared.nats_subjects import COMMANDS_CONTROL


_PROPOSAL_CONFIDENCE_DEFAULT = 1.0
_PROPOSAL_PRIORITY_DEFAULT = 70


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def handle_chat_request(request: QikiChatRequestV1, *, current_mode: QikiMode) -> QikiChatResponseV1:
    mode = current_mode

    # Decisions are handled upstream (faststream bridge executes actions). Here we
    # only acknowledge the operator decision deterministically.
    if request.decision is not None:
        pid = str(request.decision.proposal_id)
        if request.decision.decision == "ACCEPT":
            return QikiChatResponseV1(
                request_id=request.request_id,
                ok=True,
                mode=mode,
                reply=QikiReplyV1(
                    title=BilingualText(en="Accepted", ru="Принято"),
                    body=BilingualText(
                        en=f"Operator accepted proposal {pid}.",
                        ru=f"Оператор принял предложение {pid}.",
                    ),
                ),
                proposals=[],
                warnings=[],
                error=None,
            )
        return QikiChatResponseV1(
            request_id=request.request_id,
            ok=True,
            mode=mode,
            reply=QikiReplyV1(
                title=BilingualText(en="Rejected", ru="Отклонено"),
                body=BilingualText(
                    en=f"Operator rejected proposal {pid}.",
                    ru=f"Оператор отклонил предложение {pid}.",
                ),
            ),
            proposals=[],
            warnings=[],
            error=None,
        )

    text = (request.input.text or "").strip()
    low = text.lower()

    proposed_actions: list[QikiProposedActionV1] = []
    title = BilingualText(en="No actionable intent", ru="Нет исполнимого намерения")
    justification = BilingualText(
        en="Intent does not match a supported control command.",
        ru="Намерение не соответствует поддерживаемой команде управления.",
    )

    if low in {"dock.on", "power.dock.on"}:
        title = BilingualText(en="Enable dock power", ru="Включить питание дока")
        justification = BilingualText(en="Operator requested dock power on.", ru="Оператор запросил питание дока.")
        proposed_actions = [
            QikiProposedActionV1(
                subject=COMMANDS_CONTROL,
                name="power.dock.on",
                parameters={},
                dry_run=False,
            )
        ]
    elif low in {"dock.off", "power.dock.off"}:
        title = BilingualText(en="Disable dock power", ru="Выключить питание дока")
        justification = BilingualText(en="Operator requested dock power off.", ru="Оператор отключил питание дока.")
        proposed_actions = [
            QikiProposedActionV1(
                subject=COMMANDS_CONTROL,
                name="power.dock.off",
                parameters={},
                dry_run=False,
            )
        ]
    elif low.startswith("dock.engage"):
        # Example: "dock.engage" or "dock.engage A".
        parts = text.split()
        port = parts[1].strip() if len(parts) > 1 else ""
        params = {"port": port} if port else {}
        title = BilingualText(en="Engage docking", ru="Включить стыковку")
        justification = BilingualText(en="Operator requested docking engage.", ru="Оператор запросил стыковку.")
        proposed_actions = [
            QikiProposedActionV1(
                subject=COMMANDS_CONTROL,
                name="sim.dock.engage",
                parameters=params,
                dry_run=False,
            )
        ]
    elif low.startswith("dock.release"):
        title = BilingualText(en="Release docking", ru="Отпустить стыковку")
        justification = BilingualText(en="Operator requested docking release.", ru="Оператор отпустил стыковку.")
        proposed_actions = [
            QikiProposedActionV1(
                subject=COMMANDS_CONTROL,
                name="sim.dock.release",
                parameters={},
                dry_run=False,
            )
        ]

    proposals: list[QikiProposalV1] = []
    if proposed_actions:
        proposal_id = f"p-{request.request_id.hex[:8]}"
        proposals = [
            QikiProposalV1(
                proposal_id=proposal_id,
                title=title,
                justification=justification,
                confidence=_PROPOSAL_CONFIDENCE_DEFAULT,
                priority=_PROPOSAL_PRIORITY_DEFAULT,
                suggested_questions=[],
                proposed_actions=proposed_actions,
            )
        ]

    reply_title = (
        BilingualText(en="OK", ru="ОК") if proposals else BilingualText(en="No proposals", ru="Нет предложений")
    )
    reply = QikiReplyV1(
        title=reply_title,
        body=BilingualText(
            en=f"mode={mode.value} proposals={len(proposals)} ts={_now_iso()}",
            ru=(
                f"режим={('ЗАВОД' if mode == QikiMode.FACTORY else 'МИССИЯ')} "
                f"предложений={len(proposals)} время={_now_iso()}"
            ),
        ),
    )

    warnings: list[BilingualText] = []

    return QikiChatResponseV1(
        request_id=request.request_id,
        ok=True,
        mode=mode,
        reply=reply,
        proposals=proposals,
        warnings=warnings,
        error=None,
    )


def build_invalid_request_response_model(raw_request_id: str | None, *, current_mode: QikiMode) -> QikiChatResponseV1:
    # Best-effort: keep deterministic shape even if request_id is missing.
    # For transport-level JSON, we must include a UUID value; generate one.
    request_id = uuid4()
    if raw_request_id:
        try:
            request_id = UUID(str(raw_request_id))
        except Exception:
            request_id = uuid4()
    response = QikiChatResponseV1(
        request_id=request_id,
        ok=False,
        mode=current_mode,
        reply=None,
        proposals=[],
        warnings=[BilingualText(en="INVALID REQUEST", ru="НЕВЕРНЫЙ ЗАПРОС")],
        error=QikiErrorV1(
            code="INVALID_REQUEST",
            message=BilingualText(
                en="Request JSON does not match QikiChatRequest.v1",
                ru="JSON запроса не соответствует QikiChatRequest.v1",
            ),
        ),
    )
    return response


def build_invalid_request_response(raw_request_id: str | None) -> bytes:
    return (
        build_invalid_request_response_model(raw_request_id, current_mode=QikiMode.FACTORY)
        .model_dump_json()
        .encode("utf-8")
    )
