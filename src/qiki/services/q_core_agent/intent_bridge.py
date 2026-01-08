from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from hashlib import sha256
from typing import Any, Optional

import nats
from nats.errors import NoServersError, TimeoutError
from pydantic import ValidationError

from qiki.services.q_core_agent.core.agent_logger import logger
from qiki.shared.models.orion_qiki_protocol import (
    EnvironmentMode,
    EnvironmentSetV1,
    EnvironmentSnapshotV1,
    IntentV1,
    ProposalV1,
    ProposalsBatchV1,
)
from qiki.shared.nats_subjects import (
    QIKI_ENVIRONMENT_SET_V1,
    QIKI_ENVIRONMENT_V1,
    QIKI_INTENT_V1,
    QIKI_PROPOSALS_V1,
)


def build_stub_proposals(intent: IntentV1, *, environment_mode: EnvironmentMode) -> ProposalsBatchV1:
    """Deterministic proposals without OpenAI (Stage C)."""

    snapshot = intent.snapshot_min if isinstance(intent.snapshot_min, dict) else {}
    incidents = snapshot.get("incidents_top")
    has_incidents = isinstance(incidents, list) and len(incidents) > 0

    proposals: list[ProposalV1] = []
    if has_incidents:
        proposals.append(
            ProposalV1(
                proposal_id="review-incidents",
                title="Review top incidents" if environment_mode == EnvironmentMode.FACTORY else "Review incidents",
                justification=(
                    "Incidents were detected in the snapshot; review severity and acknowledge/clear as needed."
                    if environment_mode == EnvironmentMode.FACTORY
                    else "Incidents detected; review and acknowledge/clear as needed."
                ),
                priority=85 if environment_mode == EnvironmentMode.FACTORY else 90,
                confidence=0.7 if environment_mode == EnvironmentMode.FACTORY else 0.75,
            )
        )

    # In Mission mode, reduce "meta chatter" unless needed.
    if environment_mode == EnvironmentMode.FACTORY or not has_incidents:
        proposals.append(
            ProposalV1(
                proposal_id="clarify-goal",
                title="Clarify desired outcome",
                justification=(
                    f"Intent received for screen={intent.screen}. Provide target and constraints for the next step."
                    if environment_mode == EnvironmentMode.FACTORY
                    else "Provide the target and constraints for the next step."
                ),
                priority=60 if environment_mode == EnvironmentMode.FACTORY else 55,
                confidence=0.6 if environment_mode == EnvironmentMode.FACTORY else 0.65,
            )
        )

    if environment_mode == EnvironmentMode.FACTORY and len(proposals) < 3:
        proposals.append(
            ProposalV1(
                proposal_id="status-summary",
                title="Summarize current state",
                justification="Request a short status summary (vitals + active screen + selection) before executing any operation.",
                priority=50,
                confidence=0.55,
            )
        )

    return ProposalsBatchV1(
        ts=int(time.time() * 1000),
        proposals=proposals[: (2 if environment_mode == EnvironmentMode.MISSION else 3)],
        metadata={
            "source": "q_core_agent",
            "intent_ts": intent.ts,
            "screen": intent.screen,
            "environment_mode": environment_mode.value,
            "verbosity": "high" if environment_mode == EnvironmentMode.FACTORY else "low",
        },
    )


def build_invalid_intent_proposals(error: Exception) -> ProposalsBatchV1:
    """Return a single proposal describing the invalid intent (no secrets)."""

    msg = str(error)
    if len(msg) > 240:
        msg = msg[:239] + "…"

    return ProposalsBatchV1(
        ts=int(time.time() * 1000),
        proposals=[
            ProposalV1(
                proposal_id="invalid-intent",
                title="Invalid intent",
                justification=f"Intent payload failed validation: {msg}",
                priority=95,
                confidence=1.0,
            )
        ],
        metadata={"source": "q_core_agent", "error": "invalid_intent"},
    )


async def serve_intents(servers: list[str], *, install_signal_handlers: bool = False) -> None:
    """Subscribe to intent subject and publish stub proposals back."""

    try:
        nc = await nats.connect(
            servers=servers,
            connect_timeout=5,
            reconnect_time_wait=1,
            max_reconnect_attempts=-1,
        )
    except (NoServersError, TimeoutError) as exc:
        raise RuntimeError(f"Failed to connect to NATS ({servers}): {exc}") from exc

    env_raw = (os.getenv("QCORE_ENVIRONMENT_MODE") or "FACTORY").strip().upper()
    current_mode = EnvironmentMode.MISSION if env_raw == "MISSION" else EnvironmentMode.FACTORY

    async def publish_environment_mode(mode: EnvironmentMode, *, reason: str) -> None:
        snapshot = EnvironmentSnapshotV1(
            ts=int(time.time() * 1000),
            environment_mode=mode,
            source="q_core_agent",
        )
        payload = snapshot.model_dump()
        try:
            await nc.publish(QIKI_ENVIRONMENT_V1, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            logger.info("Environment published: %s=%s (%s)", QIKI_ENVIRONMENT_V1, mode.value, reason)
        except Exception as exc:
            logger.error("Failed to publish environment snapshot: %s", exc)

    async def on_env_set(msg) -> None:
        nonlocal current_mode
        try:
            payload = json.loads(msg.data.decode("utf-8"))
            req = EnvironmentSetV1.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            logger.warning("Invalid environment set request ignored: %s", exc)
            return

        if req.environment_mode != current_mode:
            current_mode = req.environment_mode
            await publish_environment_mode(current_mode, reason="set_request")

    async def on_intent(msg) -> None:
        nonlocal current_mode
        try:
            payload = json.loads(msg.data.decode("utf-8"))
            intent = IntentV1.model_validate(payload)
            if intent.environment_mode != current_mode:
                current_mode = intent.environment_mode
                await publish_environment_mode(current_mode, reason="intent_hint")
            batch = build_stub_proposals(intent, environment_mode=current_mode)
        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            batch = build_invalid_intent_proposals(exc)
            intent = None  # type: ignore[assignment]

        batch_payload = batch.model_dump()
        canonical = json.dumps(batch_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        digest = sha256(canonical).hexdigest()[:8]
        try:
            await nc.publish(QIKI_PROPOSALS_V1, json.dumps(batch_payload, ensure_ascii=False).encode("utf-8"))
            if intent is not None:
                logger.info(
                    "Proposals published: subject=%s hash=%s intent_ts=%s",
                    QIKI_PROPOSALS_V1,
                    digest,
                    getattr(intent, "ts", None),
                )
            else:
                logger.warning("Invalid intent handled: published proposals hash=%s", digest)
        except Exception as exc:
            logger.error("Failed to publish proposals: %s", exc)

    await nc.subscribe(QIKI_ENVIRONMENT_SET_V1, cb=on_env_set)
    await nc.subscribe(QIKI_INTENT_V1, cb=on_intent)
    await publish_environment_mode(current_mode, reason="startup")
    logger.info("Intent bridge online: subscribe=%s publish=%s", QIKI_INTENT_V1, QIKI_PROPOSALS_V1)

    if not install_signal_handlers:
        await asyncio.Event().wait()
        return

    # Not used in current integration; keep for standalone runs.
    stop_event = asyncio.Event()
    await stop_event.wait()


def start_intent_bridge_in_thread(nats_url: Optional[str] = None) -> threading.Thread:
    url = (nats_url or os.getenv("NATS_URL") or "").strip()
    servers = [url] if url else ["nats://qiki-nats-phase1:4222", "nats://localhost:4222"]

    def _runner() -> None:
        try:
            asyncio.run(serve_intents(servers, install_signal_handlers=False))
        except Exception as exc:
            logger.error("Intent bridge crashed: %s", exc)

    t = threading.Thread(target=_runner, name="qcore-intent-bridge", daemon=True)
    t.start()
    return t
