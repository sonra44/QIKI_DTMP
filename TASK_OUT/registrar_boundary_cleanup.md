# registrar boundary cleanup

Date: 2026-03-24 UTC

## Scope

Small cleanup around `registrar` only:
- service role / labels / comments
- docs drift around intake / audit trail wording
- minimal audit fan-in/fan-out verification

No subject changes, no ownership changes, no runtime architecture rewrite.

## Boundary statement

`registrar` is an **audit/support layer**.

It:
- subscribes to selected radar/event streams
- appends registrar-local audit evidence
- republishes registrar-owned normalized audit copies

It is **not**:
- owner of runtime truth
- owner of intent/control
- exclusive source of record for project events
- exclusive writer of `qiki.events.v1.audit`

## What the service actually reads

From `src/qiki/services/registrar/main.py`:
- `qiki.radar.v1.frames`
  - handler: `handle_radar_frame()`
  - consumes `frame_id`, `sensor_id`, `detections`
- `qiki.events.v1.>`
  - handler: `handle_system_events()`
  - wraps incoming payloads as registrar `SYSTEM_EVENT` audit records

No HTTP intake API exists in current runtime code.

## What the service actually writes / republishes

From `src/qiki/services/registrar/core/service.py` and `src/qiki/services/registrar/main.py`:
- local append-only file
  - `/var/log/qiki/registrar.log`
- registrar-local logger output
- republished audit copies on:
  - `qiki.events.v1.audit`

Important boundary:
- local append/file ownership belongs to registrar
- shared event ownership does **not** transfer to registrar just because registrar wraps or republishes an audit copy

## Drift found

1. `src/qiki/services/registrar/main.py`
   - module docstring described registrar as a broad “Black Box recorder” without explicit boundary against truth/control ownership
2. `src/qiki/services/registrar/core/service.py`
   - comments suggested future shared-audit publishing/database responsibility inside the local sink class, which blurred the actual split between local append and FastStream fan-out
3. `docs/stage0_actual_plan.md`
   - said registrar has an “API приёма событий”, but current runtime has subject subscriptions only
4. `docs/0_step.md`
   - implied singleton / single-writer / rotating-file semantics that are not proven by current code

## Changes made

### Code / comments

- `src/qiki/services/registrar/main.py`
  - clarified module role as audit/support fan-in/fan-out
  - explicitly stated: not runtime-truth owner, not intent/control owner, not exclusive source of record
  - clarified `_make_audit_record()` and `_publish_audit()` semantics
  - clarified startup and subscriber handler docstrings

- `src/qiki/services/registrar/core/service.py`
  - narrowed class/module descriptions to registrar-local append/log concerns only
  - removed misleading comment that mixed local sink concerns with shared audit publishing responsibility

### Docs

- `docs/stage0_actual_plan.md`
  - replaced “API приёма событий” wording with subject-subscription based audit/support wording

- `docs/0_step.md`
  - replaced singleton / rotating / single-writer wording with actual current boundary:
    - reads selected subjects
    - writes local append-only log
    - republishes registrar-owned audit copies
    - not truth owner, not intent/control owner, not sole audit writer

## Minimal verification

### Tests added

- `src/qiki/services/registrar/tests/test_main_contract.py`
  - verifies radar fan-in:
    - incoming radar frame triggers `register_sensor_event(...)`
  - verifies audit fan-out:
    - handler emits normalized registrar audit record with `event_type=RADAR_FRAME_RECEIVED`
  - verifies self-generated audit recursion guard:
    - registrar `SYSTEM_EVENT` payload is skipped and not re-audited

### Docker test evidence

- Command:
  - `docker compose -f /home/sonra44/QIKI_DTMP/docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/registrar/tests`
- Result:
  - `............                                                             [100%]`

## Done check

- registrar role is described unambiguously as audit/support
- docs/comments no longer imply truth ownership or exclusive source-of-record semantics
- minimal audit behavior is confirmed by narrow Docker tests for fan-in/fan-out and recursion guard
