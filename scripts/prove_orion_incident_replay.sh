#!/usr/bin/env bash
set -euo pipefail

# P0 proof: ORION incident-level reproduction via record/replay (no v2/no duplicates).
#
# Flow:
# 1) Start Phase1 with deterministic TEMP_CORE_TRIP fixture (sim-truth).
# 2) Capture the last thermal TRIP edge event from JetStream and write it to JSONL (in qiki-dev container).
# 3) Stop q-sim-service (eliminate live events).
# 4) Restart operator-console (reset IncidentStore).
# 5) Replay the JSONL into canonical subjects and assert ORION emits audit event kind=incident_open.
# 6) Restore default stack (no fixture bot_config).
#
# Usage:
#   cd QIKI_DTMP
#   bash scripts/prove_orion_incident_replay.sh

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PHASE1=(-f docker-compose.phase1.yml -f docker-compose.operator.yml)

CAPTURE_PATH_IN_CONTAINER="/tmp/orion_incident_replay_capture.jsonl"

restore_default_stack() {
  echo "[prove] restore: default stack (no fixture BOT_CONFIG_PATH)"
  docker compose "${PHASE1[@]}" down
  env -u BOT_CONFIG_PATH -u QIKI_BOT_CONFIG_PATH \
    docker compose "${PHASE1[@]}" up -d --build
}

trap 'restore_default_stack' EXIT

echo "[prove] step 0: clean start"
docker compose "${PHASE1[@]}" down

echo "[prove] step 1: bring up fixture stack (TEMP_CORE_TRIP)"
BOT_CONFIG_PATH=/workspace/tests/fixtures/bot_config_temp_core_trip.json \
  docker compose "${PHASE1[@]}" up -d --build

echo "[prove] step 2: capture last thermal TRIP edge event from JetStream into JSONL (qiki-dev: ${CAPTURE_PATH_IN_CONTAINER})"
docker compose "${PHASE1[@]}" exec -T -e CAPTURE_PATH="${CAPTURE_PATH_IN_CONTAINER}" qiki-dev python - <<'PY'
import asyncio
import os
import json
from pathlib import Path
import nats

from qiki.shared.nats_subjects import EVENTS_STREAM_NAME, SIM_SENSOR_THERMAL_TRIP

OUT = os.environ.get("CAPTURE_PATH", "/tmp/orion_incident_replay_capture.jsonl")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

async def main() -> None:
    nc = await nats.connect(servers=[NATS_URL], connect_timeout=2)
    js = nc.jetstream()
    payload = None
    # Thermal TRIP is an edge event; fetch it from JetStream deterministically.
    for _ in range(30):
        try:
            msg = await js.get_last_msg(EVENTS_STREAM_NAME, SIM_SENSOR_THERMAL_TRIP)
        except Exception:
            await asyncio.sleep(0.2)
            continue
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except Exception:
            await asyncio.sleep(0.2)
            continue
        if isinstance(data, dict) and int(data.get("tripped", 0)) == 1 and str(data.get("subject")) == "core":
            payload = data
            break
        await asyncio.sleep(0.2)

    await nc.drain()
    await nc.close()

    if not isinstance(payload, dict):
        raise SystemExit("[prove] No core thermal TRIP edge event found in JetStream; fixture may not be active")

    ts_epoch = float(payload.get("ts_epoch") or 0.0) if isinstance(payload.get("ts_epoch"), (int, float)) else None
    if not ts_epoch:
        import time

        ts_epoch = time.time()

    line = {
        "schema_version": 1,
        "type": "event",
        "ts_epoch": float(ts_epoch),
        "subject": SIM_SENSOR_THERMAL_TRIP,
        "data": payload,
    }
    Path(OUT).write_text(json.dumps(line, ensure_ascii=False) + "\n", encoding="utf-8")
    print({"path": OUT, "subject": SIM_SENSOR_THERMAL_TRIP, "ts_epoch": ts_epoch, "tripped": payload.get("tripped")})

asyncio.run(main())
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
docker compose "${PHASE1[@]}" exec -T -e ORION_IP="${ORION_IP}" -e CAPTURE_PATH="${CAPTURE_PATH_IN_CONTAINER}" qiki-dev python - <<'PY'
import asyncio
import json
import os
import urllib.request

import nats

from qiki.shared.nats_subjects import OPERATOR_ACTIONS
from qiki.shared.nats_subjects import SIM_SENSOR_THERMAL_TRIP
from qiki.shared.record_replay import replay_jsonl

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
CAPTURE = os.environ.get("CAPTURE_PATH", "/tmp/orion_incident_replay_capture.jsonl")

TARGET_RULE = "TEMP_CORE_TRIP"

CONNZ_URL = os.environ.get("NATS_MONITOR_URL", "http://nats:8222/connz?subs=1")
ORION_IP = os.environ.get("ORION_IP", "").strip()


def _load_connz() -> dict:
    with urllib.request.urlopen(CONNZ_URL, timeout=2.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _find_orion_connection(connz: dict) -> dict | None:
    if ORION_IP:
        for c in connz.get("connections", []) or []:
            if str(c.get("ip") or "") == ORION_IP:
                return c
        return None

    required = {"qiki.telemetry", "qiki.responses.control", "qiki.responses.qiki", "qiki.events.v1.>"}
    for c in connz.get("connections", []) or []:
        subs = set(c.get("subscriptions_list") or [])
        if required.issubset(subs):
            return c
    return None


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

    await nc.subscribe(OPERATOR_ACTIONS, cb=handler)

    async def on_trigger(_msg) -> None:
        nonlocal replay_seen
        replay_seen += 1

    await nc.subscribe(SIM_SENSOR_THERMAL_TRIP, cb=on_trigger)

    # Baseline: confirm ORION connection exists in NATS monitoring and capture in/out counters.
    await asyncio.sleep(1.0)
    connz0 = _load_connz()
    orion0 = _find_orion_connection(connz0)
    if not orion0:
        raise SystemExit(
            f"[prove] ORION NATS connection not found via connz (ORION_IP={ORION_IP or 'auto'}); cannot continue deterministically"
        )
    in0 = int(orion0.get("in_msgs") or 0)
    out0 = int(orion0.get("out_msgs") or 0)
    cid = orion0.get("cid")
    subs0 = list(orion0.get("subscriptions_list") or [])
    print(
        f"[prove] ORION connz baseline: cid={cid} ip={orion0.get('ip')} in_msgs={in0} out_msgs={out0} subs={len(subs0)}"
    )
    print(f"[prove] ORION subs: {subs0}")
    if "qiki.events.v1.>" not in subs0:
        raise SystemExit("[prove] ORION is not subscribed to qiki.events.v1.> (cannot ingest replay events)")

    replay_result = await replay_jsonl(
        nats_url=NATS_URL,
        input_path=CAPTURE,
        # Use event timestamps from payload for determinism (ORION uses payload.ts_epoch when present).
        speed=50.0,
        no_timing=True,
        subject_prefix=None,
    )
    print(f"[prove] replay_jsonl result: {replay_result}")

    # Post-replay counters: did ORION actually receive messages?
    await asyncio.sleep(0.5)
    connz1 = _load_connz()
    orion1 = _find_orion_connection(connz1)
    if not orion1:
        raise SystemExit("[prove] ORION NATS connection disappeared after replay")
    in1 = int(orion1.get("in_msgs") or 0)
    out1 = int(orion1.get("out_msgs") or 0)
    print(f"[prove] ORION connz after replay: cid={orion1.get('cid')} in_msgs={in1} out_msgs={out1}")
    print(f"[prove] ORION deltas: in_msgs={in1 - in0} out_msgs={out1 - out0}")
    print(f"[prove] replay trigger messages observed by proof subscriber: {replay_seen}")

    try:
        payload = await asyncio.wait_for(fut, timeout=8.0)
        print("[prove] OK: received incident_open audit event:")
        print(json.dumps(payload, ensure_ascii=False))
    except TimeoutError:
        raise SystemExit(
            f"[prove] FAIL: did not receive incident_open audit event; saw_any={seen_any}, "
            f"orion_in_delta={in1 - in0}, orion_out_delta={out1 - out0}, replay_seen={replay_seen}"
        )

    await nc.drain()
    await nc.close()

asyncio.run(main())
PY

echo "[prove] done: proof succeeded (stack will be restored to default via trap)"
