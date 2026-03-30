# TASK: Add QIKI proposal reject smoke

Status: done
Date: 2026-01-23

## Goal

Add deterministic CLI smoke for proposal rejection (pair to accept smoke) so reject is not UI-only.

## Definition of Done (DoD)

- `python tools/qiki_proposal_reject_smoke.py` prints `OK:` inside Docker.
- faststream-bridge logs show `proposal reject <proposal_id>` on `qiki.intents`.

## Evidence

Command:

`docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/qiki_proposal_reject_smoke.py`

Output:

```text
OK: rejected proposal_id=p-4f8f36c5
```

Command:

`docker compose -f docker-compose.phase1.yml logs --tail=200 faststream-bridge | sed -r 's/\x1b\[[0-9;]*m//g' | rg -n "proposal reject p-4f8f36c5"`

Output:

```text
175:qiki-faststream-bridge-phase1  | 2026-01-23 18:48:16,302 INFO     -               | qiki.intents         | 480e512b-4 - QIKI intent received: request_id=c2b1aaf2-861f-4bb1-aa26-f4921af7cafc text='proposal reject p-4f8f36c5'
```
