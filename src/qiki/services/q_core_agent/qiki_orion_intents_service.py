from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from qiki.services.q_core_agent.core.agent import QCoreAgent
from qiki.services.q_core_agent.core.agent_logger import logger, setup_logging
from qiki.services.q_core_agent.core.grpc_data_provider import GrpcDataProvider
from qiki.services.q_core_agent.core.tick_orchestrator import TickOrchestrator
from qiki.shared.config_models import QCoreAgentConfig, load_config
from qiki.shared.models.core import Proposal
from qiki.shared.models.qiki_chat import (
    BilingualText,
    QikiChatRequestV1,
    QikiChatResponseV1,
    QikiErrorV1,
    QikiMode,
    QikiProposalV1,
    QikiReplyV1,
)
from qiki.shared.nats_subjects import QIKI_INTENTS, QIKI_RESPONSES


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _proposal_to_qiki(p: Proposal) -> QikiProposalV1:
    title = BilingualText(en=f"{p.type.name}", ru=f"{p.type.name}")
    justification = BilingualText(en=p.justification, ru=p.justification)
    # QIKI chat schema expects priority 0..100.
    priority = int(max(0, min(100, round(float(p.priority) * 100))))
    confidence = float(max(0.0, min(1.0, float(p.confidence))))
    return QikiProposalV1(
        proposal_id=str(p.proposal_id),
        title=title,
        justification=justification,
        confidence=confidence,
        priority=priority,
        suggested_questions=[],
        proposed_actions=[],
    )


def _build_invalid_request_response(*, raw_request_id: str | None, mode: QikiMode) -> QikiChatResponseV1:
    request_id = uuid4()
    if raw_request_id:
        try:
            request_id = UUID(str(raw_request_id))
        except Exception:  # noqa: BLE001
            request_id = uuid4()

    return QikiChatResponseV1(
        request_id=request_id,
        ok=False,
        mode=mode,
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


async def _run_tick_loop(*, agent: QCoreAgent, orchestrator: TickOrchestrator, data_provider: GrpcDataProvider) -> None:
    tick_s = float(agent.config.tick_interval)
    while True:
        await orchestrator.run_tick_async(data_provider)
        await asyncio.sleep(tick_s)


async def _run_orion_intents_loop(*, agent: QCoreAgent) -> None:
    try:
        import nats
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"nats import failed: {exc}") from exc

    nats_url = os.getenv("NATS_URL", "nats://nats:4222")
    intents_subject = os.getenv("QIKI_INTENTS_SUBJECT", QIKI_INTENTS)
    responses_subject = os.getenv("QIKI_RESPONSES_SUBJECT", QIKI_RESPONSES)
    mode = QikiMode(os.getenv("QIKI_MODE", QikiMode.FACTORY.value))

    nc = await nats.connect(
        servers=[nats_url],
        connect_timeout=3,
        allow_reconnect=True,
        max_reconnect_attempts=-1,
    )
    logger.info("QIKI intents listener connected: %s", nats_url)

    async def handler(msg) -> None:
        payload: Any
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return

        raw_req_id = payload.get("request_id") or payload.get("requestId")
        try:
            req = QikiChatRequestV1.model_validate(payload)
        except Exception:
            resp = _build_invalid_request_response(raw_request_id=str(raw_req_id) if raw_req_id else None, mode=mode)
            await nc.publish(responses_subject, resp.model_dump_json(ensure_ascii=False).encode("utf-8"))
            return

        # Ensure the agent context is reasonably fresh at the time we answer.
        proposals = list(agent.context.proposals or [])
        top = [_proposal_to_qiki(p) for p in proposals[:3]]

        reply = QikiReplyV1(
            title=BilingualText(en="QIKI", ru="QIKI"),
            body=BilingualText(
                en=f"mode={mode.value} proposals={len(top)} ts={_now_iso()}",
                ru=(
                    f"режим={('ЗАВОД' if mode == QikiMode.FACTORY else 'МИССИЯ')} "
                    f"предложений={len(top)} время={_now_iso()}"
                ),
            ),
        )
        resp = QikiChatResponseV1(
            request_id=req.request_id,
            ok=True,
            mode=mode,
            reply=reply,
            proposals=top,
            warnings=[],
            error=None,
        )
        await nc.publish(responses_subject, resp.model_dump_json(ensure_ascii=False).encode("utf-8"))

    await nc.subscribe(intents_subject, cb=handler)
    logger.info("Subscribed QIKI intents: %s -> %s", intents_subject, responses_subject)

    while True:
        await asyncio.sleep(3600)


async def main_async() -> None:
    log_config_path = os.path.join(os.path.dirname(__file__), "config", "logging.yaml")
    setup_logging(default_path=log_config_path)

    config_path = Path(__file__).with_name("config.yaml")
    config = load_config(config_path, QCoreAgentConfig)
    agent = QCoreAgent(config)
    data_provider = GrpcDataProvider(config.grpc_server_address)
    orchestrator = TickOrchestrator(agent, config, state_store=None)

    await asyncio.gather(
        _run_tick_loop(agent=agent, orchestrator=orchestrator, data_provider=data_provider),
        _run_orion_intents_loop(agent=agent),
    )


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
