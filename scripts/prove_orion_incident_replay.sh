#!/usr/bin/env bash
set -euo pipefail

# P0 proof: ORION incident-level reproduction via record/replay (no v2/no duplicates).
#
# Flow:
# 1) Start Phase1 stack (ORION V + NATS).
# 2) Build deterministic replay JSONL with one incident-like event payload.
# 3) Stop q-sim-service (eliminate live events).
# 4) Restart operator-console (reset IncidentStore).
# 5) Replay the JSONL into canonical subjects and assert ORION emits audit event kind=incident_open.
# 6) Restore default stack (no fixture bot_config).
#
# Usage:
#   cd QIKI_DTMP
#   bash scripts/prove_orion_incident_replay.sh
#
# Optional env flags:
#   PROVE_BUILD=1            # force compose rebuild before run (default 0)
#   PROVE_RESTORE_DEFAULT=1  # restore default stack via trap on exit (default 0)

cd "$(dirname "${BASH_SOURCE[0]}")/.."
PHASE1=(-f docker-compose.phase1.yml -f docker-compose.operator.yml)
PROVE_BUILD="${PROVE_BUILD:-0}"
PROVE_RESTORE_DEFAULT="${PROVE_RESTORE_DEFAULT:-0}"

CAPTURE_PATH_IN_CONTAINER="/workspace/tests/integration/.orion_incident_replay_capture.jsonl"

up_cmd=(-d)
if [[ "${PROVE_BUILD}" == "1" ]]; then
  up_cmd+=(--build)
fi

compose_up_retry() {
  local attempt
  for attempt in 1 2 3; do
    if docker compose "${PHASE1[@]}" up "${up_cmd[@]}"; then
      return 0
    fi
    echo "[prove] compose up failed on attempt ${attempt}/3, retrying..." >&2
    docker compose "${PHASE1[@]}" down --remove-orphans >/dev/null 2>&1 || true
    sleep 2
  done
  return 1
}

restore_default_stack() {
  echo "[prove] restore: default stack (no fixture BOT_CONFIG_PATH)"
  docker compose "${PHASE1[@]}" down --remove-orphans >/dev/null 2>&1 || true
  env -u BOT_CONFIG_PATH -u QIKI_BOT_CONFIG_PATH \
    compose_up_retry
}

if [[ "${PROVE_RESTORE_DEFAULT}" == "1" ]]; then
  trap 'restore_default_stack' EXIT
fi

echo "[prove] step 0: clean start"
docker compose "${PHASE1[@]}" down --remove-orphans >/dev/null 2>&1 || true

echo "[prove] step 1: bring up Phase1 stack"
compose_up_retry

echo "[prove] step 2: build deterministic incident replay JSONL (qiki-dev: ${CAPTURE_PATH_IN_CONTAINER})"
docker compose "${PHASE1[@]}" run --no-deps --rm -T -e CAPTURE_PATH="${CAPTURE_PATH_IN_CONTAINER}" qiki-dev python - <<'PY'
import os
import json
from pathlib import Path

from qiki.shared.nats_subjects import EVENTS_AUDIT

OUT = os.environ.get("CAPTURE_PATH", "/workspace/tests/integration/.orion_incident_replay_capture.jsonl")
payload = {
    "incident_id": "TEMP_CORE_TRIP|sensor|thermal|core",
    "rule_id": "TEMP_CORE_TRIP",
    "severity": "C",
    "description": "core thermal trip replay proof",
    "ts_unix_ms": 1772725000000,
}
line = {
    "schema_version": 1,
    "type": "event",
    "ts_epoch": 1772725000.0,
    "subject": EVENTS_AUDIT,
    "data": payload,
}
Path(OUT).write_text(json.dumps(line, ensure_ascii=False) + "\n", encoding="utf-8")
print({"path": OUT, "subject": EVENTS_AUDIT, "incident_id": payload["incident_id"]})
PY

echo "[prove] step 3: stop q-sim-service (remove live event source)"
docker compose "${PHASE1[@]}" stop q-sim-service

echo "[prove] step 4: restart operator-console (reset incidents store)"
docker compose "${PHASE1[@]}" restart operator-console

echo "[prove] step 4.5: wait a moment for ORION init (no-mocks; no TUI scraping)"
sleep 2.0
ORION_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' qiki-operator-console)"
echo "[prove] ORION container IP: ${ORION_IP}"

echo "[prove] step 5: replay capture + assert ORION emits incident_open audit event"
docker compose "${PHASE1[@]}" run --no-deps --rm -T -e ORION_IP="${ORION_IP}" -e CAPTURE_PATH="${CAPTURE_PATH_IN_CONTAINER}" qiki-dev python - <<'PY'
import asyncio
import json
import os

import nats

from qiki.shared.nats_subjects import OPERATOR_INCIDENTS
from qiki.shared.record_replay import replay_jsonl

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
CAPTURE = os.environ.get("CAPTURE_PATH", "/tmp/orion_incident_replay_capture.jsonl")

TARGET_RULE = "TEMP_CORE_TRIP"


async def main() -> None:
    nc = await nats.connect(servers=[NATS_URL], connect_timeout=2)
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[dict] = loop.create_future()
    seen_any = 0
    replay_seen = 0

    async def handler(msg) -> None:
        nonlocal seen_any
        try:
            payload = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        seen_any += 1
        if payload.get("kind") != "incident_open":
            return
        if payload.get("rule_id") != TARGET_RULE:
            return
        if not fut.done():
            fut.set_result(payload)

    await nc.subscribe(OPERATOR_INCIDENTS, cb=handler)

    replay_result = await replay_jsonl(
        nats_url=NATS_URL,
        input_path=CAPTURE,
        # Use event timestamps from payload for determinism (ORION uses payload.ts_epoch when present).
        speed=50.0,
        no_timing=True,
        subject_prefix=None,
    )
    print(f"[prove] replay_jsonl result: {replay_result}")
    print(f"[prove] replay trigger messages observed by proof subscriber: {replay_seen}")

    try:
        payload = await asyncio.wait_for(fut, timeout=8.0)
        print("[prove] OK: received incident_open audit event:")
        print(json.dumps(payload, ensure_ascii=False))
    except TimeoutError:
        raise SystemExit(
            f"[prove] FAIL: did not receive incident_open audit event; "
            f"saw_any={seen_any}, replay_seen={replay_seen}"
        )

    await nc.drain()
    await nc.close()

asyncio.run(main())
PY

if [[ "${PROVE_RESTORE_DEFAULT}" == "1" ]]; then
  echo "[prove] done: proof succeeded (stack will be restored to default via trap)"
else
  echo "[prove] done: proof succeeded (stack left as-is; set PROVE_RESTORE_DEFAULT=1 for auto-restore)"
fi
