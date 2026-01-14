#!/usr/bin/env bash
# Smoke tests for "virtual hardware" signals (MCQPU CPU/RAM) + BIOS MVP + NATS wiring.
#
# Policy: no-mocks — these checks assert real (simulation-truth) values or explicit N/A paths.
#
# Usage:
#   scripts/smoke_virtual_hardware.sh
#   KEEP_STACK=1 scripts/smoke_virtual_hardware.sh
set -euo pipefail

KEEP_STACK="${KEEP_STACK:-0}"

if command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  DC="docker compose"
fi

cd "$(dirname "$0")/.."

cleanup() {
  if [ "${KEEP_STACK}" = "1" ]; then
    echo "ℹ️  KEEP_STACK=1 -> leaving containers running"
    return
  fi
  echo "🧹 Bringing stack down..."
  ${DC} -f docker-compose.phase1.yml -f docker-compose.operator.yml down >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "🐳 Bringing up stack (phase1 + operator overlay)..."
${DC} -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build nats q-sim-service q-bios-service operator-console

echo "⏱  Waiting for health (max ~40s)..."
for i in $(seq 1 40); do
  if ${DC} -f docker-compose.phase1.yml -f docker-compose.operator.yml ps | grep -q "qiki-bios-phase1.*healthy" \
    && ${DC} -f docker-compose.phase1.yml -f docker-compose.operator.yml ps | grep -q "qiki-nats-phase1.*healthy" \
    && ${DC} -f docker-compose.phase1.yml -f docker-compose.operator.yml ps | grep -q "qiki-sim-phase1.*healthy" \
    && ${DC} -f docker-compose.phase1.yml -f docker-compose.operator.yml ps | grep -q "qiki-operator-console.*healthy"; then
    break
  fi
  sleep 1
done

echo "🔍 BIOS HTTP endpoints..."
curl -fsS http://localhost:8080/healthz >/dev/null
BIOS_STATUS_JSON="$(curl -fsS http://localhost:8080/bios/status)"
${DC} -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY' <<<"${BIOS_STATUS_JSON}"
import json, sys
data = json.load(sys.stdin)
assert isinstance(data, dict)
assert data.get("source") == "q-bios-service"
assert data.get("subject") == "qiki.events.v1.bios_status"
assert isinstance(data.get("post_results"), list)
assert isinstance(data.get("all_systems_go"), bool)
print("✅ BIOS status OK:", "all_systems_go=", data["all_systems_go"], "post_results=", len(data["post_results"]))
PY

echo "🔍 NATS: telemetry contains MCQPU cpu_usage/memory_usage (non-null, 0..100)..."
${DC} -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json
import nats

async def main():
  nc = await nats.connect("nats://nats:4222")
  fut = asyncio.get_running_loop().create_future()

  async def cb(msg):
    try:
      data = json.loads(msg.data.decode())
    except Exception as e:
      fut.set_exception(e)
      return
    fut.set_result(data)

  await nc.subscribe("qiki.telemetry", cb=cb)
  try:
    data = await asyncio.wait_for(fut, timeout=5.0)
  finally:
    await nc.drain()

  cpu = data.get("cpu_usage")
  mem = data.get("memory_usage")
  assert cpu is not None, "cpu_usage is None (telemetry missing MCQPU values)"
  assert mem is not None, "memory_usage is None (telemetry missing MCQPU values)"
  cpu = float(cpu); mem = float(mem)
  assert 0.0 <= cpu <= 100.0, f"cpu_usage out of range: {cpu}"
  assert 0.0 <= mem <= 100.0, f"memory_usage out of range: {mem}"
  print("✅ Telemetry MCQPU OK:", "cpu_usage=", cpu, "memory_usage=", mem)

asyncio.run(main())
PY

echo "🔍 NATS: BIOS publishes qiki.events.v1.bios_status (trigger via HTTP)..."
${DC} -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json
from urllib.request import urlopen
import nats

async def main():
  nc = await nats.connect("nats://nats:4222")
  fut = asyncio.get_running_loop().create_future()

  async def cb(msg):
    data = json.loads(msg.data.decode())
    fut.set_result(data)

  await nc.subscribe("qiki.events.v1.bios_status", cb=cb)

  # Trigger at least one publish (avoids waiting for interval).
  urlopen("http://q-bios-service:8080/bios/status", timeout=3).read()

  try:
    data = await asyncio.wait_for(fut, timeout=10.0)
  finally:
    await nc.drain()

  assert data.get("subject") == "qiki.events.v1.bios_status"
  assert isinstance(data.get("all_systems_go"), bool)
  print("✅ BIOS event OK:", "all_systems_go=", data["all_systems_go"])

asyncio.run(main())
PY

echo "✅ Smoke OK (virtual MCQPU + BIOS + NATS + operator-console running)"
