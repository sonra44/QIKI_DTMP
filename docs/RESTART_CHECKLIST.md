# RESTART CHECKLIST (Phase 1, Radar v1)

## 1) Остановка
- `docker compose -f docker-compose.phase1.yml down`

## 2) Подъём Phase 1
- `docker compose -f docker-compose.phase1.yml up -d --build`
- `docker compose -f docker-compose.phase1.yml ps`
- `curl -sf http://localhost:8222/healthz` — ожидаем `{ "status": "ok" }`
- `docker compose -f docker-compose.phase1.yml logs --tail=20 q-sim-service` — gRPC сервер поднят
- `docker compose -f docker-compose.phase1.yml logs --tail=20 q-core-intents` — QIKI intent listener поднят и подписан на `qiki.intents`
- NOTE: симуляция стартует в `STOPPED` (кадры радара публикуются только после `sim.start`).

## 2.0) BIOS HTTP semantics check
- `curl -sf http://127.0.0.1:8080/healthz` — только liveness HTTP процесса `q-bios-service`; не читать как readiness `q-sim-service`, NATS или свежести BIOS payload.
- `curl -sf http://127.0.0.1:8080/bios/status` — фактическая support-tier surface для BIOS snapshot.
- Canonical interpretation:
  - `healthz` = process liveness only
  - `/bios/status` = cached payload surface
  - dependency readiness и payload freshness проверяются через `/bios/status`, smoke, логи и зависимые сервисы, а не через один `healthz`.
- Cached freshness semantics:
  - при `BIOS_PUBLISH_ENABLED=1` HTTP snapshot обычно обновляется publisher loop; freshness bounded следующей publish-итерацией (`BIOS_PUBLISH_INTERVAL_SEC`, default `5s`);
  - при disabled publish HTTP snapshot может стать sticky до `POST /bios/reload` или до другой recompute path.

## 2.1) Подъём ORION V overlay
```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps operator-console
```

- Canonical runtime overlay for ORION V is `docker-compose.operator.yml`.
- `docker-compose.operator_orionv.yml` is transitional/non-canonical and not required for the supported launch path.

## 2.2) Live ORION V session (canonical under tmux)
```bash
./scripts/run_orion_v_live.sh
```

- Для живой интерактивной проверки ORION V под `tmux` использовать именно fresh TTY через `./scripts/run_orion_v_live.sh`.
- Внутри скрипта source of truth остаётся `docker exec -it qiki-operator-console python main_orion_v.py`.
- Не использовать `docker attach qiki-operator-console` как стандартный live-path: 2026-03-06 этот путь дал грязную перерисовку, повторяющиеся шапки, скачки курсора и нестабильный mouse/fullscreen режим.

## 2.3) System mode (JetStream edge event)
```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev env NATS_URL="nats://nats:4222" \
  python tools/system_mode_smoke.py --persisted-only
```

## 2.4) Запуск симуляции (чтобы пошли радарные кадры)
```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, uuid, nats
from qiki.shared.models.core import CommandMessage, MessageMetadata
from qiki.shared.nats_subjects import COMMANDS_CONTROL, RESPONSES_CONTROL

async def main():
    nc = await nats.connect('nats://nats:4222')
    fut = asyncio.get_running_loop().create_future()
    req_id = str(uuid.uuid4())

    async def handler(msg):
        try:
            payload = json.loads(msg.data.decode('utf-8'))
        except Exception:
            return
        rid = payload.get('request_id') or payload.get('requestId')
        if str(rid) == req_id and not fut.done():
            fut.set_result(payload)

    await nc.subscribe(RESPONSES_CONTROL, cb=handler)
    cmd = CommandMessage(
        command_name='sim.start',
        parameters={'speed': 1.0},
        metadata=MessageMetadata(message_id=req_id, message_type='control_command', source='checklist', destination='q_sim_service'),
    )
    await nc.publish(COMMANDS_CONTROL, json.dumps(cmd.model_dump(mode='json')).encode('utf-8'))
    await nc.flush(timeout=2.0)
    payload = await asyncio.wait_for(fut, timeout=6.0)
    print(payload)
    await nc.close()

asyncio.run(main())
PY
```

## 2.5) Радарный пайплайн (JetStream)
- `docker compose -f docker-compose.phase1.yml logs --tail=50 faststream-bridge | rg -n \"Radar frame received\"` — кадры доходят через JetStream

## 3) gRPC health-check
```bash
docker compose -f docker-compose.phase1.yml exec -T q-sim-service python - <<'PY'
import grpc
from generated.q_sim_api_pb2_grpc import QSimAPIServiceStub
from generated.q_sim_api_pb2 import HealthCheckRequest
channel = grpc.insecure_channel('localhost:50051')
stub = QSimAPIServiceStub(channel)
print(stub.HealthCheck(HealthCheckRequest(), timeout=3.0))
PY
```

## 4) Радарный пайплайн (JetStream)
```bash
./scripts/run_integration_tests_docker.sh tests/integration/test_radar_flow.py tests/integration/test_radar_tracks_flow.py
```

```bash
./scripts/run_integration_tests_docker.sh tests/integration/test_radar_lr_sr_topics.py
```

## 5) FastStream / NATS раунд-трип (управляющие топики)
```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, uuid, nats

async def main():
    nc = await nats.connect('nats://nats:4222')
    fut = asyncio.get_running_loop().create_future()

    async def handler(msg):
        fut.set_result(msg)

    await nc.subscribe('qiki.responses.control', cb=handler)
    payload = {
        'command_name': 'PING',
        'parameters': {'echo': 'hello'},
        'metadata': {'message_id': str(uuid.uuid4()), 'source': 'checklist'},
    }
    await nc.publish('qiki.commands.control', json.dumps(payload).encode())
    msg = await asyncio.wait_for(fut, timeout=5.0)
    print(msg.data.decode())
    await nc.close()

asyncio.run(main())
PY
```

## 6) Полный тестовый прогоn
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests`

## 6.1) ORION V SAFE MODE smoke (F2/F3 text contract)
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_safe_mode_smoke.py`
- Ожидаемый маркер: `OK: orion_v_safe_mode_smoke`

## 7) Остановка
- `docker compose -f docker-compose.phase1.yml down`
