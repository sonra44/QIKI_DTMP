# TASK (2026-02-02): Prove radar guard -> ORION incident_open (no TUI scraping)

## Goal

Make the end-to-end operator loop provable:

`radar guard alert (NATS)` → `ORION IncidentStore` → `audit event kind=incident_open`

Constraints:
- no new subjects/versions
- no TUI scraping
- Docker-first

## Preconditions

- Stack uses Phase1 + operator overlay.
- Guard alert publishing is edge-triggered (anti-flap) on the producer.
- Incident rules include radar guard rule IDs.

## Proof script

- Script: `scripts/prove_orion_radar_guard_incident_open.sh`

What it does:
1) Restarts the stack with:
   - `RADAR_GUARD_EVENTS_ENABLED=1`
   - `RADAR_SR_THRESHOLD_M=100` (forces close SR contact so `UNKNOWN_CONTACT_CLOSE` triggers deterministically)
2) Subscribes to `OPERATOR_ACTIONS` and waits for:
   - `category=audit`, `kind=incident_open`, `rule_id=UNKNOWN_CONTACT_CLOSE`
3) Restores the default stack (guard events disabled) on exit.

## Done when

- The script prints `OK { ... "kind":"incident_open", "rule_id":"UNKNOWN_CONTACT_CLOSE", ... }` and exits 0.

