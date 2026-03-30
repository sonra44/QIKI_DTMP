# Worklog — hardware_profile_hash tracing (2026-01-18)

Цель круга: добавить трассируемость `hardware_profile_hash` без моков и без `v2` во всех критических местах:
BIOS → телеметрия (`qiki.telemetry`) → ORION UI.

## Изменения (по факту)

1) Shared util
- Добавлен детерминированный хэш: `src/qiki/shared/config/hardware_profile_hash.py`
  - формат: `sha256:<64hex>`
  - вход: подмножество `bot_config.json`: `hardware_profile` + `hardware_manifest`

2) BIOS (q-bios-service)
- `src/qiki/services/q_bios_service/bios_engine.py` вычисляет `hardware_profile_hash` при успешной загрузке `bot_config.json`.
- `src/qiki/shared/models/core.py`: поле `hardware_profile_hash: str | None` добавлено в `BiosStatus` (backward compatible).

3) Simulation telemetry (q_sim_service)
- `src/qiki/services/q_sim_service/service.py` вычисляет хэш из `bot_config.json` (runtime SoT) и добавляет top-level ключ `hardware_profile_hash` в payload `qiki.telemetry`.
- No-mocks: если конфиг не читается/хэш не вычисляется — ключ не добавляется.

4) ORION (Operator Console)
- `src/qiki/services/operator_console/main_orion.py` показывает `Hardware profile hash/Хэш профиля железа` в `Diagnostics` (или `N/A/—`).

## Тесты

- Добавлены unit-тесты:
  - `src/qiki/shared/config/tests/test_hardware_profile_hash.py`
  - `src/qiki/services/q_sim_service/tests/test_hardware_profile_hash.py`
  - Обновлён `src/qiki/services/q_bios_service/tests/test_bios_engine.py` (проверка хэша)

Команда (Docker-first):

```bash
docker compose -f docker-compose.phase1.yml run --rm --no-deps qiki-dev bash -lc \
  'pytest -q \
    src/qiki/shared/config/tests/test_hardware_profile_hash.py \
    src/qiki/services/q_sim_service/tests/test_hardware_profile_hash.py \
    src/qiki/services/q_bios_service/tests/test_bios_engine.py'
```

## Smoke (Docker)

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build --remove-orphans
curl -fsS http://127.0.0.1:8080/bios/status | python3 -c 'import sys,json; print(json.load(sys.stdin).get("hardware_profile_hash"))'
```

Проверка, что `qiki.telemetry` тоже содержит хэш (из `qiki-dev`):

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml exec -T qiki-dev bash -lc 'python - <<\"PY\"
import asyncio, json, nats

async def main():
    nc = await nats.connect(\"nats://qiki-nats-phase1:4222\")
    fut = asyncio.get_running_loop().create_future()
    async def cb(msg):
        fut.set_result(json.loads(msg.data.decode()))
    sub = await nc.subscribe(\"qiki.telemetry\", cb=cb)
    d = await asyncio.wait_for(fut, timeout=5.0)
    await sub.unsubscribe()
    await nc.drain()
    print(d.get(\"hardware_profile_hash\"))

asyncio.run(main())
PY'
```

## Документация

- Обновлено: `docs/design/operator_console/ORION_OS_VALIDATION_RUN_2026-01-18.md` (добавлен пункт про `hardware_profile_hash`).

