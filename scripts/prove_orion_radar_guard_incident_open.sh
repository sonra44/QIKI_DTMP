#!/usr/bin/env bash
set -euo pipefail

# P0 proof: Radar guard alert -> ORION IncidentStore -> audit event kind=incident_open.
# - No TUI scraping.
# - No new subjects/versions.
#
# Usage:
#   cd QIKI_DTMP
#   bash scripts/prove_orion_radar_guard_incident_open.sh

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PHASE1=(-f docker-compose.phase1.yml -f docker-compose.operator.yml)

restore_default_stack() {
  echo "[prove] restore: default stack (guard events disabled)"
  docker compose "${PHASE1[@]}" down
  env -u RADAR_GUARD_EVENTS_ENABLED -u RADAR_SR_THRESHOLD_M docker compose "${PHASE1[@]}" up -d --build
}

trap 'restore_default_stack' EXIT

echo "[prove] step 0: clean start"
docker compose "${PHASE1[@]}" down

echo "[prove] step 1: bring up stack with guard events enabled (deterministic SR threshold)"
RADAR_GUARD_EVENTS_ENABLED=1 RADAR_SR_THRESHOLD_M=100 docker compose "${PHASE1[@]}" up -d --build

echo "[prove] step 2: wait for services (informational)"
docker compose "${PHASE1[@]}" ps
sleep 2.0

echo "[prove] step 3: assert ORION emits audit incident_open for UNKNOWN_CONTACT_CLOSE"
docker compose "${PHASE1[@]}" exec -T qiki-dev env NATS_URL="nats://nats:4222" python - <<'PY'
import asyncio
import json
import os
from uuid import uuid4

import nats

from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.nats_subjects import COMMANDS_CONTROL, OPERATOR_ACTIONS, RADAR_GUARD_ALERTS, RESPONSES_CONTROL


async def main() -> None:
    nc = await nats.connect(servers=[os.environ.get("NATS_URL", "nats://nats:4222")], connect_timeout=2)
    fut_incident: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
    fut_guard: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
    fut_ack: asyncio.Future[dict] = asyncio.get_running_loop().create_future()

    async def incident_handler(msg) -> None:
        if fut_incident.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        if payload.get("category") != "audit":
            return
        if payload.get("kind") != "incident_open":
            return
        if payload.get("rule_id") != "UNKNOWN_CONTACT_CLOSE":
            return
        fut_incident.set_result(payload)

    async def guard_handler(msg) -> None:
        if fut_guard.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        if payload.get("category") != "radar":
            return
        if payload.get("kind") != "guard_alert":
            return
        if payload.get("rule_id") != "UNKNOWN_CONTACT_CLOSE":
            return
        fut_guard.set_result(payload)

    request_id = str(uuid4())

    async def ack_handler(msg) -> None:
        if fut_ack.done():
            return
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        rid = payload.get("request_id") or payload.get("requestId")
        if str(rid) != request_id:
            return
        fut_ack.set_result(payload)

    sub_incident = await nc.subscribe(OPERATOR_ACTIONS, cb=incident_handler)
    sub_guard = await nc.subscribe(RADAR_GUARD_ALERTS, cb=guard_handler)
    sub_ack = await nc.subscribe(RESPONSES_CONTROL, cb=ack_handler)
    try:
        # Ensure subscriptions are registered before we start simulation (avoid race).
        await nc.flush(timeout=2.0)

        # Start simulation only after subscriptions are active.
        meta = MessageMetadata(message_id=request_id, message_type="control_command", source="prove", destination="q_sim_service")
        cmd = CommandMessage(command_name="sim.start", parameters={"speed": 1.0}, metadata=meta)
        await nc.publish(COMMANDS_CONTROL, json.dumps(cmd.model_dump(mode="json")).encode("utf-8"))
        await nc.flush(timeout=2.0)

        try:
            ack = await asyncio.wait_for(fut_ack, timeout=6.0)
            print("ACK", json.dumps(ack, ensure_ascii=False))
        except asyncio.TimeoutError:
            print("WARN: no sim.start ACK observed on qiki.responses.control (continuing)")

        # Evidence: we prefer to see a guard alert first (pipeline proof), then the incident_open audit.
        try:
            guard = await asyncio.wait_for(fut_guard, timeout=20.0)
            print("GUARD", json.dumps(guard, ensure_ascii=False))
        except asyncio.TimeoutError:
            print("WARN: no UNKNOWN_CONTACT_CLOSE guard_alert observed (incident may still open via other event timing)")

        payload = await asyncio.wait_for(fut_incident, timeout=30.0)
        print("OK", json.dumps(payload, ensure_ascii=False))
    finally:
        await sub_incident.unsubscribe()
        await sub_guard.unsubscribe()
        await sub_ack.unsubscribe()
        await nc.drain()
        await nc.close()


asyncio.run(main())
PY

echo "[prove] OK"
