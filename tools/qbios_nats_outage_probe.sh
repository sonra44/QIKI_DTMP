#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE=(-f "$PROJECT_ROOT/docker-compose.phase1.yml")
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/qbios-nats-outage-probe.XXXXXX")"

NATS_OUTAGE_SEC="${NATS_OUTAGE_SEC:-6}"
RECOVERY_TIMEOUT_SEC="${RECOVERY_TIMEOUT_SEC:-20}"
BIOS_HTTP_BASE="${BIOS_HTTP_BASE:-http://127.0.0.1:8080}"

cleanup() {
  docker compose "${COMPOSE[@]}" up -d nats >/dev/null 2>&1 || true
}
trap cleanup EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing command: $1" >&2; exit 1; }
}

extract_timestamp() {
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("timestamp",""))'
}

print_json_field() {
  local field="$1"
  python3 -c "import json,sys; print(json.load(sys.stdin).get('$field',''))"
}

require_cmd docker
require_cmd curl
require_cmd python3

echo "[probe] logs: $LOG_DIR"
echo "[probe] stack: docker-compose.phase1.yml"
echo "[probe] outage seconds: $NATS_OUTAGE_SEC"
echo "[probe] recovery timeout seconds: $RECOVERY_TIMEOUT_SEC"

docker compose "${COMPOSE[@]}" ps q-bios-service nats qiki-dev

BASELINE_HEALTH="$(curl -fsS "$BIOS_HTTP_BASE/healthz")"
BASELINE_STATUS_PATH="$LOG_DIR/baseline_bios_status.json"
curl -fsS "$BIOS_HTTP_BASE/bios/status" >"$BASELINE_STATUS_PATH"
BASELINE_TS="$(extract_timestamp <"$BASELINE_STATUS_PATH")"
BASELINE_ASG="$(print_json_field all_systems_go <"$BASELINE_STATUS_PATH")"

echo "[probe] baseline healthz: $BASELINE_HEALTH"
echo "[probe] baseline bios timestamp: $BASELINE_TS"
echo "[probe] baseline all_systems_go: $BASELINE_ASG"

START_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "[probe] stopping nats at $START_TS"
docker compose "${COMPOSE[@]}" stop nats >/dev/null

sleep 1

OUTAGE_HEALTH_PATH="$LOG_DIR/outage_healthz.txt"
OUTAGE_STATUS_PATH="$LOG_DIR/outage_bios_status.json"
curl -fsS "$BIOS_HTTP_BASE/healthz" >"$OUTAGE_HEALTH_PATH"
curl -fsS "$BIOS_HTTP_BASE/bios/status" >"$OUTAGE_STATUS_PATH"
OUTAGE_TS="$(extract_timestamp <"$OUTAGE_STATUS_PATH")"
OUTAGE_ASG="$(print_json_field all_systems_go <"$OUTAGE_STATUS_PATH")"

echo "[probe] outage healthz: $(cat "$OUTAGE_HEALTH_PATH")"
echo "[probe] outage bios timestamp: $OUTAGE_TS"
echo "[probe] outage all_systems_go: $OUTAGE_ASG"

sleep "$NATS_OUTAGE_SEC"

OUTAGE_LATE_STATUS_PATH="$LOG_DIR/outage_late_bios_status.json"
curl -fsS "$BIOS_HTTP_BASE/bios/status" >"$OUTAGE_LATE_STATUS_PATH"
OUTAGE_LATE_TS="$(extract_timestamp <"$OUTAGE_LATE_STATUS_PATH")"
OUTAGE_LATE_ASG="$(print_json_field all_systems_go <"$OUTAGE_LATE_STATUS_PATH")"

echo "[probe] outage-late bios timestamp: $OUTAGE_LATE_TS"
echo "[probe] outage-late all_systems_go: $OUTAGE_LATE_ASG"

echo "[probe] starting nats"
docker compose "${COMPOSE[@]}" up -d nats >/dev/null

RECOVERY_START_EPOCH="$(python3 - <<'PY'
import time
print(time.time())
PY
)"

RECOVERY_SMOKE_LOG="$LOG_DIR/recovery_bios_smoke.log"
if docker compose "${COMPOSE[@]}" exec -T qiki-dev env \
  NATS_URL="nats://nats:4222" \
  BIOS_STATUS_SMOKE_TIMEOUT_SEC="$RECOVERY_TIMEOUT_SEC" \
  python tools/bios_status_smoke.py >"$RECOVERY_SMOKE_LOG" 2>&1; then
  RECOVERY_RESULT="ok"
else
  RECOVERY_RESULT="failed"
fi

RECOVERY_END_EPOCH="$(python3 - <<'PY'
import time
print(time.time())
PY
)"

RECOVERY_DELTA="$(python3 - <<PY
start = float("$RECOVERY_START_EPOCH")
end = float("$RECOVERY_END_EPOCH")
print(f"{end-start:.3f}")
PY
)"

docker compose "${COMPOSE[@]}" logs --since "$START_TS" q-bios-service >"$LOG_DIR/qbios_since_outage.log" 2>&1 || true

echo "[probe] recovery result: $RECOVERY_RESULT"
echo "[probe] recovery wait seconds: $RECOVERY_DELTA"
echo "[probe] recovery smoke output:"
cat "$RECOVERY_SMOKE_LOG"

echo "[probe] q_bios_service markers since outage:"
grep -E "NATS publish failed|NATS publish recovered|BIOS compute failed|nats: encountered error|UnexpectedEOF|Connect call failed|Name or service not known" "$LOG_DIR/qbios_since_outage.log" || true

echo "[probe] artifacts:"
printf '  %s\n' \
  "$BASELINE_STATUS_PATH" \
  "$OUTAGE_HEALTH_PATH" \
  "$OUTAGE_STATUS_PATH" \
  "$OUTAGE_LATE_STATUS_PATH" \
  "$RECOVERY_SMOKE_LOG" \
  "$LOG_DIR/qbios_since_outage.log"
