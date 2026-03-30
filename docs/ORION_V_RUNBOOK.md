# ORION V Runbook

## Scope

Production-style operational runbook for ORION V as the canonical operator console.

Current baseline note:
- This runbook is operational guidance for the current canonical stack: `docker-compose.phase1.yml` + `docker-compose.operator.yml`.
- ORION V is the supported operator path on that stack.
- Follow-up work in this slice is hardening/regression/cleanup, not blocker recovery.

## Start

```bash
docker compose \
  -f docker-compose.phase1.yml \
  -f docker-compose.operator.yml \
  up -d --build
```

## Restart

```bash
docker compose \
  -f docker-compose.phase1.yml \
  -f docker-compose.operator.yml \
  restart operator-console
```

## Live Operator Session

Canonical interactive ORION V path under `tmux`:

```bash
./scripts/run_orion_v_live.sh
```

Operator rule:
- use a fresh interactive TTY for live ORION V checks
- do not use `docker attach qiki-operator-console` as the standard operator path under `tmux`
- helper script source of truth remains `docker exec -it qiki-operator-console python main_orion_v.py`
- `docker-compose.operator.yml` is the canonical supported ORION V overlay
- `docker-compose.operator_orionv.yml` remains transitional/non-canonical and should be used only when an older proof explicitly asks for it

Reason:
- `docker attach` was proven to produce a degraded fullscreen path in tmux (`alternate_on=0`, `mouse_any=0`)
- observed symptoms on 2026-03-06: dirty redraw, repeated headers, cursor instability, and unreliable mouse behavior
- fresh `docker exec -it ... python main_orion_v.py` restored correct fullscreen behavior (`alternate_on=1`, `mouse_any=1`)

## Health Checks

1) Phase1 services:

```bash
docker compose -f docker-compose.phase1.yml ps
```

2) NATS:

```bash
curl -s http://localhost:8222/healthz
```

3) ORION V logs:

```bash
docker logs --tail=120 qiki-operator-console
```

Expected:
- NATS state in header (`Связь установлена/Переподключение/Связь отсутствует`)
- F1/F2/F3/F4/F6/F7 commands responsive
- no crash loop in logs

## Minimal Regression Entry

For the current post-closure resumed-observation slice, the canonical minimal regression entry is:

```bash
bash scripts/run_minimal_regression_pack.sh
```

Use it when changes touch the current canonical slice around:
- resumed observation / `signature_changed`
- ORION procedure loading for that slice
- resumed-path observability fields for contour/q-core/public-track identity
- BIOS support-tier contract surface
- registrar contract sanity included in the pack

Boundary:
- this is the default minimal regression entry for the slice;
- it is not a replacement for broader cutover validation or task-specific acceptance evidence;
- it is not a historical blocker-proof replay command.
- failure severity for this pack is mapped in [TASK_OUT/regression_failure_severity_map.md](/home/sonra44/QIKI_DTMP/TASK_OUT/regression_failure_severity_map.md); a red step is not automatically a reopened P0.

Required success markers are enforced by the wrapper itself, including:
- resumed smoke: `INITIAL_TARGET_SOURCE=orion_live_radar_cache`, `RESUME_ACTION=resume_observation`, `CONTINUATION_RESULT=signature_changed`, `FINAL_QIKI_STATUS=confirmed`
- BIOS smoke: `OK: received bios status on qiki.events.v1.bios_status`

## Rollback (legacy ORION, isolated)

```bash
docker compose \
  -f docker-compose.phase1.yml \
  -f docker-compose.operator.yml \
  -f docker-compose.operator_legacy.yml \
  --profile legacy \
  up -d --build operator-console
```

Use `docker-compose.operator_legacy.yml --profile legacy` only for rollback mode.
Legacy runtime is not for production use.

## Pilot Cutover

Cutover (minimal downtime):

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
```

Pilot acceptance:
- `F1/F2/F3/F4/F6/F7` level navigation works.
- Incident workflow: `ack` and `clear` produce audit trail.
- Procedure workflow: `proc list`, `proc run <name>`, `proc status`.
- Replay safety: banner visible and control disabled in replay.
- Readiness note: this runbook is not a substitute for task-specific acceptance evidence; use the canonical board and current task dossiers for scope-specific readiness claims.
- Canonical audit subjects:
  - operator actions: `qiki.events.v1.operator.actions`
  - incident lifecycle (`incident_open/ack/clear`): `qiki.events.v1.operator.incidents`

Rollback:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_legacy.yml --profile legacy up -d --build operator-console
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps
```

## Pilot Smoke Scenario

1) Cold boot:

```bash
docker compose \
  -f docker-compose.phase1.yml \
  -f docker-compose.operator.yml \
  down -v

docker compose \
  -f docker-compose.phase1.yml \
  -f docker-compose.operator.yml \
  up -d --build
```

2) NATS connect:
- start a fresh ORION V TTY session and verify header `Connected`.

3) Raise incident (example):

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, nats
async def main():
    nc = await nats.connect("nats://nats:4222")
    payload = {"incident_id":"pilot-inc-1","severity":"C","description":"pilot smoke"}
    await nc.publish("qiki.events.v1.audit", json.dumps(payload).encode())
    await nc.flush()
    await nc.close()
asyncio.run(main())
PY
```

Expected: Level-0 overlay shows active C/A incident.

4) Ack:
- in ORION V: `ack pilot-inc-1` then confirm `Yes`.

Expected: incident becomes acknowledged, audit event is published.
Audit subjects:
- `qiki.events.v1.operator.incidents`
- `qiki.events.v1.operator.actions`

5) Procedure run:
- `proc list`
- `proc run safe_pause_resume`
- `proc status`

Expected: sequential steps complete with ACKs from `qiki.responses.control`.
Audit subjects:
- `qiki.events.v1.operator.procedures`
- `qiki.events.v1.operator.actions`

## Notes

- Режим анализа истории опционален и работает в ограниченном режиме (`replay on 900`).
- In replay mode, incident `ack/clear` and procedure control are disabled by design.
- Decode/control ошибки в ORION теперь логируются с контекстом (component/action/subject/payload-size), silent-drop в критичных ветках исключён.
- При росте ошибок декодирования/контрольных исключений проверяйте `F7` и audit/операторские логи контейнера.
- F7 Состояние системы показывает runtime-метрики:
  `Событий в секунду`, `Глубина очереди`, `Задержка процедуры`, `Время подтверждения`, CPU/память, активные подписки.
