# RESTART CHECKLIST (Phase 1)

1) Остановка
- docker compose -f docker-compose.phase1.yml down

2) Подъём
- docker compose -f docker-compose.phase1.yml up -d --build
- docker compose -f docker-compose.phase1.yml ps
- curl -sf http://localhost:8222/healthz  # ожидаем {"status":"ok"}

3) gRPC проверка
- docker compose -f docker-compose.phase1.yml exec -T q-sim-service python - <<'PY'
import grpc
from generated.q_sim_api_pb2_grpc import QSimAPIStub
from google.protobuf.empty_pb2 import Empty
ch=grpc.insecure_channel('localhost:50051'); print(QSimAPIStub(ch).HealthCheck(Empty(), timeout=3.0))
PY

4) FastStream / NATS быстрый раунд-трип
- docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, uuid, nats
async def main():
  nc=await nats.connect('nats://qiki-nats-phase1:4222')
  fut=asyncio.get_running_loop().create_future()
  async def h(m): fut.set_result(m)
  await nc.subscribe('qiki.responses.control', cb=h)
  payload={'command_name':'PING','parameters':{'echo':'hello'},'metadata':{'message_id':str(uuid.uuid4()),'source':'checklist'}}
  await nc.publish('qiki.commands.control', json.dumps(payload).encode())
  m=await asyncio.wait_for(fut,5.0); print(m.data.decode()); await nc.close()
asyncio.run(main())
PY

5) Тесты
- docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests
