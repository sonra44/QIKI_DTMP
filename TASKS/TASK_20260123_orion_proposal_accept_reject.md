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

Command:

`docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps`

Output:

```text
NAME                            IMAGE                         COMMAND                  SERVICE             CREATED        STATUS                  PORTS
qiki-bios-phase1                qiki_dtmp-q-bios-service      "python -m qiki.serv…"   q-bios-service      6 hours ago    Up 6 hours (healthy)    127.0.0.1:8080->8080/tcp
qiki-dev-phase1                 qiki_dtmp-qiki-dev            "python -m qiki.serv…"   qiki-dev            7 hours ago    Up 7 hours
qiki-faststream-bridge-phase1   qiki_dtmp-faststream-bridge   "faststream run qiki…"   faststream-bridge   6 hours ago    Up 6 hours
qiki-grafana-phase1             grafana/grafana:10.4.2        "/run.sh"                grafana             15 hours ago   Up 15 hours             0.0.0.0:3000->3000/tcp, :::3000->3000/tcp
qiki-loki-phase1                grafana/loki:2.9.0            "/usr/bin/loki -conf…"   loki                15 hours ago   Up 15 hours             0.0.0.0:3100->3100/tcp, :::3100->3100/tcp
qiki-nats-phase1                qiki_dtmp-nats                "docker-entrypoint.s…"   nats                15 hours ago   Up 15 hours (healthy)   0.0.0.0:4222->4222/tcp, :::4222->4222/tcp, 0.0.0.0:8222->8222/tcp, :::8222->8222/tcp, 6222/tcp
qiki-operator-console           qiki_dtmp-operator-console    "python main_orion.py"   operator-console    6 hours ago    Up 6 hours (healthy)
qiki-promtail-phase1            grafana/promtail:latest       "/usr/bin/promtail -…"   promtail            15 hours ago   Up 15 hours
qiki-registrar-phase1           qiki_dtmp-registrar           "python src/qiki/ser…"   registrar           7 hours ago    Up 7 hours              8000/tcp
qiki-sim-phase1                 qiki_dtmp-q-sim-service       "python -m qiki.serv…"   q-sim-service       6 hours ago    Up 6 hours (healthy)
qiki-sim-radar-phase1           qiki_dtmp-q-sim-radar         "python -m qiki.serv…"   q-sim-radar         7 hours ago    Up 7 hours
```

### Tests

Command:

`docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_proposal_actions.py`

Output:

```text
..                                                                       [100%]
```

### Smoke (proposal accept via NATS)

Command:

`docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/qiki_proposal_accept_smoke.py`

Output:

```text
OK: accepted proposal_id=p-6df77679
```

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

Command:

`docker compose -f docker-compose.phase1.yml logs --since 2026-01-23T18:16:40 faststream-bridge | sed -r 's/\\x1b\\[[0-9;]*m//g' | rg -n "qiki\\.intents|proposal (accept|reject)"`

Output (selected lines):

```text
113:qiki-faststream-bridge-phase1  | 2026-01-23 18:16:58,644 INFO     -               | qiki.intents         | d7d990b4-a - QIKI intent received: request_id=32c1b37d-a85a-4bad-ab02-a590cfa372b9 text='proposal accept p-9bbdce20'
530:qiki-faststream-bridge-phase1  | 2026-01-23 18:18:07,650 INFO     -               | qiki.intents         | 2407cdcf-6 - QIKI intent received: request_id=ae3272fb-9b18-48a3-bfea-7007613109ab text='proposal reject p-8be6ca7d'
3899:qiki-faststream-bridge-phase1  | 2026-01-23 18:27:29,699 INFO     -               | qiki.intents         | a440c0ce-b - QIKI intent received: request_id=be43c738-9401-43e7-a073-20fc04dd20d6 text='proposal accept p-6df77679'
```
