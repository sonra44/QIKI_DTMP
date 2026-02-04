# TASK: Fix persisted system_mode (JetStream) so ORION Mode is not N/A

**Date:** 2026-02-04  
**Status:** done  

## Goal

Ensure `qiki.events.v1.system_mode` is actually **persisted** in JetStream stream `QIKI_EVENTS_V1`,
so ORION can hydrate and display `Mode/Режим` deterministically (no-mocks).

## Problem (facts)

- ORION header showed `Mode/Режим N/A/—` even though the system was operating in `FACTORY`.
- Persisted-only smoke failed:
  - `python tools/system_mode_smoke.py --persisted-only` → `BAD: no persisted system_mode event in JetStream`
- Direct JetStream lookup failed:
  - `js.get_last_msg(QIKI_EVENTS_V1, qiki.events.v1.system_mode)` → `no message found`

## Root cause

`faststream-bridge` attempted to publish `qiki.events.v1.system_mode` via FastStream with `stream=...`,
but this did not reliably persist a message in JetStream for ORION boot hydration.

## Fix

- `src/qiki/services/faststream_bridge/app.py` now publishes system_mode **directly** via `nats-py` JetStream
  (`js.publish(...)`), with fallback to core-NATS publish.
- Added unit test:
  - `src/qiki/services/faststream_bridge/tests/test_system_mode_persisted_publish.py`

## Evidence

### Unit test (Docker-first)

```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev pytest -q \
  src/qiki/services/faststream_bridge/tests/test_system_mode_persisted_publish.py
```

### Runtime proof (Docker-first)

Rebuild + restart faststream-bridge (publishes initial mode at boot):

```bash
docker compose -f docker-compose.phase1.yml up -d --build faststream-bridge
```

Persisted-only smoke now passes:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev env NATS_URL="nats://nats:4222" \
  python tools/system_mode_smoke.py --persisted-only
```

Expected:
- `OK: persisted system_mode in JetStream: mode=FACTORY ...`

### ORION live proof (tmux)

After the fix and faststream-bridge restart, ORION header shows:
- `Mode/Режим FACTORY` instead of `N/A/—`.

