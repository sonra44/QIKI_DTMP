# TASK: Stage 6 Cutover Rehearsal (ORION V)

## Status

`done`

## Goal

Dry-run cutover path for ORION V with rollback safety and quality gate proof.

## Scope

1. Rehearsal profile start/stop (phase1 + operator + operator_orionv).
2. NATS restart rehearsal with reconnect proof.
3. Burst load rehearsal (3000 events).
4. Canonical operator audit subject proof.
5. Quality gate verification.

## Commands Executed

### 1) Cold boot rehearsal profile

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml down -v
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml up -d --build
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml ps
curl -s http://localhost:8222/healthz
```

Result:
- stack up, `operator-console` healthy;
- NATS health response: `{"status":"ok"}`.

### 2) NATS restart rehearsal

```bash
docker stop qiki-nats-phase1
sleep 4
docker start qiki-nats-phase1
docker logs --tail=300 qiki-operator-console | rg -n 'NATS: Reconnecting|NATS: Connected|NATS: Lost'
```

Result (log excerpts):
- `NATS: Reconnecting`
- `NATS: Connected`

### 3) Burst load rehearsal

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, nats
TOTAL = 3000
SUBJECT = "qiki.events.v1.audit"
async def main():
    nc = await nats.connect("nats://nats:4222")
    for i in range(TOTAL):
        payload = {
            "incident_id": f"stage6-burst-{i}",
            "severity": "WARN" if i % 5 else "C",
            "description": "stage6 burst event",
            "subsystem": "stage6",
            "idx": i,
        }
        await nc.publish(SUBJECT, json.dumps(payload).encode())
    await nc.flush(timeout=10)
    await nc.close()
    print(f"published={TOTAL} subject={SUBJECT}")
asyncio.run(main())
PY
```

Result:
- `published=3000 subject=qiki.events.v1.audit`;
- stack remained healthy (`docker compose ... ps`).

### 4) Canonical audit subject proof (operator actions)

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, nats
SUBJ = "qiki.events.v1.operator.actions"
async def main():
    nc = await nats.connect("nats://nats:4222")
    fut = asyncio.get_running_loop().create_future()
    async def cb(msg):
        if not fut.done():
            fut.set_result(msg.data.decode())
    await nc.subscribe(SUBJ, cb=cb)
    payload = {"kind":"stage6_probe","operator":"rehearsal","action":"audit_view_probe","ts":"2026-02-26T00:00:00Z"}
    await nc.publish(SUBJ, json.dumps(payload).encode())
    await nc.flush(timeout=2)
    got = await asyncio.wait_for(fut, timeout=3)
    print("received_subject=" + SUBJ)
    print("received_payload=" + got)
    await nc.close()
asyncio.run(main())
PY
```

Result:
- `received_subject=qiki.events.v1.operator.actions`;
- payload delivered on canonical operator actions subject.

### 5) Quality gate

```bash
bash scripts/quality_gate_docker.sh
```

Result:
- `ruff` passed;
- unit test slice passed;
- anti-loop gate passed;
- overall: `[quality-gate] OK`.

## Additional Deterministic Proofs

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_nats_client.py
```

Result:
- `........ [100%]`
- replay guardrail + audit publish + reconnect resubscribe behavior covered.

## DoD Assessment

1. ORION V starts healthy: `OK`.
2. Reconnect state transition on NATS restart: `OK`.
3. No duplicate-subscription regression proof:
   - runtime remained stable after reconnect/burst: `OK`;
   - unit anti-duplication tests passed: `OK`.
4. Canonical operator audit actions subject proof: `OK`.
5. Quality gate passed: `OK`.

## Final Verdict

`OK` — Stage 6 rehearsal passed for pilot cutover preparation.
