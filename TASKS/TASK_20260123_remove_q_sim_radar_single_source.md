# TASK: Remove q-sim-radar (single simulation source)

Status: done
Date: 2026-01-23

## Goal

Make `q-sim-service` the single source of world ticks + radar publishing by removing the separate `q-sim-radar` service from docker-compose.

## Rationale

Two independent tick loops (`q-sim-service` and `q-sim-radar`) create “two worlds” and break determinism (and any future active pause semantics).

## Changes

- Removed `q-sim-radar` from:
  - `docker-compose.phase1.yml`
  - `docker-compose.yml`
  - `docker-compose.minimal.yml`
- Updated architecture docs:
  - `docs/ARCHITECTURE.md`
  - `Cabinet/Reports/TRUTH_TABLE_2026-01-23.md`

## Evidence

### Compose services list (no q-sim-radar)

`docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml config --services | rg "q-sim-radar"`

Output:

```text
(no output)
```

### Stack apply

`docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build --remove-orphans`

Output (selected):

```text
Container qiki-sim-radar-phase1  Removing
Container qiki-sim-radar-phase1  Removed
```

### Radar still flows

Faststream-bridge logs show radar frames received (example lines):

```text
QIKI_RADAR_V1 | qiki.radar.v1.frames | ... - Radar frame received: frame_id=... detections=2
```

Integration test (explicitly selecting integration marker + NATS_URL):

`docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'NATS_URL=nats://nats:4222 pytest -q -m integration tests/integration/test_radar_lr_sr_topics.py'`

Output:

```text
.                                                                        [100%]
```
