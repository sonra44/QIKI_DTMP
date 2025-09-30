# RESTART CHECKLIST (Phase 1, Radar v1)

## 1) Остановка
- `docker compose -f docker-compose.phase1.yml down`

## 2) Подъём Phase 1
- `docker compose -f docker-compose.phase1.yml up -d --build`
- `docker compose -f docker-compose.phase1.yml ps`
- `curl -sf http://localhost:8222/healthz` — ожидаем `{ "status": "ok" }`
- `docker logs q-sim-phase1 | tail -n 20` — gRPC сервер поднят
- `docker logs qiki-sim-radar-phase1 | tail -n 20` — публикация кадров в JetStream

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
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/integration/test_radar_flow.py tests/integration/test_radar_tracks_flow.py
```

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/integration/test_radar_lr_sr_topics.py
```

## 5) FastStream / NATS раунд-трип (управляющие топики)
```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, uuid, nats

async def main():
    nc = await nats.connect('nats://qiki-nats-phase1:4222')
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

## 7) Остановка
- `docker compose -f docker-compose.phase1.yml down`
