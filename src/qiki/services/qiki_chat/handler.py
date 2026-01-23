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
    QikiReplyV1,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def handle_chat_request(request: QikiChatRequestV1) -> QikiChatResponseV1:
    mode = QikiMode.FACTORY
    proposals = [
        QikiProposalV1(
            proposal_id="p-001",
            title=BilingualText(en="Headless QIKI online", ru="Headless QIKI в сети"),
            justification=BilingualText(
                en="MVP request/reply channel is working; actions are disabled.",
                ru="MVP канал request/reply работает; действия отключены.",
            ),
            confidence=1.0,
            priority=50,
            suggested_questions=[
                BilingualText(
                    en="Explain ORION vs QIKI roles",
                    ru="Объясни роли ORION и QIKI",
                ),
                BilingualText(
                    en="What is the next implementation step?",
                    ru="Какой следующий шаг внедрения?",
                ),
            ],
            proposed_actions=[],
        )
    ]

    reply = QikiReplyV1(
        title=BilingualText(en="OK", ru="ОК"),
        body=BilingualText(
            en=(
                "I am running in FACTORY mode. I can answer questions and return "
                "structured proposals. Actions are disabled in this MVP."
            ),
            ru=(
                "Я запущена в режиме ЗАВОД. Я могу отвечать на вопросы и возвращать "
                "структурированные предложения. Действия отключены в этом MVP."
            ),
        ),
    )

    warnings = [
        BilingualText(en="ACTIONS DISABLED", ru="ДЕЙСТВИЯ ОТКЛЮЧЕНЫ"),
        BilingualText(en=f"ts={_now_iso()}", ru=f"время={_now_iso()}"),
    ]

    _ = request  # reserved for future: context-driven proposals
    return QikiChatResponseV1(
        request_id=request.request_id,
        ok=True,
        mode=mode,
        reply=reply,
        proposals=proposals,
        warnings=warnings,
        error=None,
    )


def build_invalid_request_response_model(raw_request_id: str | None) -> QikiChatResponseV1:
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
        mode=QikiMode.FACTORY,
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
    return build_invalid_request_response_model(raw_request_id).model_dump_json().encode("utf-8")
