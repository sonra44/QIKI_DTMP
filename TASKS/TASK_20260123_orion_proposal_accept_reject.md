# TASK: ORION proposal accept/reject workflow (no auto-actions)

Status: done
Date: 2026-01-23

## Goal

Make ORION able to deterministically accept/reject a selected QIKI proposal (no auto-actions) and publish a follow-up intent referencing `proposal_id`.

## Definition of Done (DoD)

- ORION renders proposals and auto-selects the first one.
- Operator can accept (`v`) / reject (`b`) from the ORION UI with a confirmation dialog.
- ORION publishes to `qiki.intents` with `proposal_id` and decision.
- Docker tests + smoke pass.

## Evidence (commands + outputs)

### Stack health

`docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps`

- `operator-console` is up/healthy
- `nats` is up/healthy
- `faststream-bridge` is up

### Tests

`docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests`

- PASS

### Smoke (proposal accept via NATS)

`docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/qiki_proposal_accept_smoke.py`

- `OK: accepted proposal_id=p-...`

### ORION UI flow (end-to-end)

Attach to ORION:

- `docker attach qiki-operator-console` (detach: `Ctrl+P` then `Ctrl+Q`)

On QIKI screen:

1) Submit QIKI intent: `q: dock.on` (from command input)
2) Accept selected proposal: press `v` then `y` (ConfirmDialog)
3) Generate a new proposal: `q: dock.on`
4) Reject selected proposal: press `b` then `y` (ConfirmDialog)

ORION Output/Вывод shows:

- `QIKI: Accepted/Принято (ok/ок=yes/да, proposals/предложений=0, request/запрос=32c1b37d-a85a-4bad-ab02-a590cfa372b9)`
- `QIKI: Rejected/Отклонено (ok/ок=yes/да, proposals/предложений=0, request/запрос=ae3272fb-9b18-48a3-bfea-7007613109ab)`

### faststream-bridge logs (NATS receipt)

`docker compose -f docker-compose.phase1.yml logs --since 2026-01-23T18:16:40 faststream-bridge | rg -n "qiki\\.intents|proposal (accept|reject)"`

- `QIKI intent received: request_id=32c1b37d-a85a-4bad-ab02-a590cfa372b9 text='proposal accept p-9bbdce20'`
- `QIKI intent received: request_id=ae3272fb-9b18-48a3-bfea-7007613109ab text='proposal reject p-8be6ca7d'`
