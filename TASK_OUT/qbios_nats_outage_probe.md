# q_bios_service NATS Outage Probe

Date: 2026-03-25

## Goal

Capture narrow evidence for `q_bios_service` behavior during a temporary NATS outage, without changing subjects, HTTP API, or runtime contracts.

## Probe shape

Helper added:
- [tools/qbios_nats_outage_probe.sh](/home/sonra44/QIKI_DTMP/tools/qbios_nats_outage_probe.sh)

What it does:
1. captures baseline `GET /healthz` and `GET /bios/status`
2. stops only `nats` for a short window
3. probes BIOS HTTP during the outage
4. restarts `nats`
5. waits for the first recovered BIOS event with `tools/bios_status_smoke.py`
6. captures `q-bios-service` logs since outage start

This is intentionally a narrow operational probe, not a general chaos framework.

## Evidence run

Command used:

```bash
NATS_OUTAGE_SEC=6 RECOVERY_TIMEOUT_SEC=20 bash tools/qbios_nats_outage_probe.sh
```

Artifacts from the run:
- `/tmp/qbios-nats-outage-probe.8Zy91Z/baseline_bios_status.json`
- `/tmp/qbios-nats-outage-probe.8Zy91Z/outage_healthz.txt`
- `/tmp/qbios-nats-outage-probe.8Zy91Z/outage_bios_status.json`
- `/tmp/qbios-nats-outage-probe.8Zy91Z/outage_late_bios_status.json`
- `/tmp/qbios-nats-outage-probe.8Zy91Z/recovery_bios_smoke.log`
- `/tmp/qbios-nats-outage-probe.8Zy91Z/qbios_since_outage.log`

## Measured behavior

### 1. HTTP during outage

Observed:
- `/healthz` stayed available during the outage and returned `{"ok": true}`.
- `/bios/status` also stayed available during the outage.

Measured timestamps:
- baseline `/bios/status` timestamp:
  - `2026-03-25T00:27:06.868969Z`
- early outage `/bios/status` timestamp:
  - `2026-03-25T00:27:06.868969Z`
- later outage `/bios/status` timestamp:
  - `2026-03-25T00:27:11.877115Z`

Interpretation:
- immediately after NATS loss, HTTP served the already-cached snapshot;
- during the continued outage window, the cached HTTP payload refreshed again even though NATS distribution was unavailable.

This matches the current service shape:
- `_last_payload` is updated by the publisher loop before the NATS publish attempt;
- NATS outage degrades event distribution, not local HTTP availability.

### 2. Publish recovery timing

Observed:
- after `nats` was restarted, BIOS event recovery succeeded;
- `tools/bios_status_smoke.py` received a valid event payload again.

Measured recovery wait:
- `5.106s`

Interpretation:
- recovery landed at about one publish interval after NATS came back;
- this is consistent with current canonical timing expectations because `BIOS_PUBLISH_INTERVAL_SEC` is `5s` by default and the exact reconnect timing remains library-shaped.

### 3. Log markers during outage/recovery

Observed in `q_bios_service` log capture:
- library-level NATS client errors were visible:
  - `nats: encountered error`
  - `nats.errors.UnexpectedEOF: nats: unexpected EOF`
  - `ConnectionRefusedError: [Errno 111] Connect call failed ('172.18.0.2', 4222)`
  - `socket.gaierror: [Errno -2] Name or service not known`

Observed in this short run:
- explicit service-level markers
  - `NATS publish failed (...)`
  - `NATS publish recovered (...)`
  were not emitted in the captured window.

Interpretation:
- the outage is still diagnostically visible because the underlying NATS client logs errors loudly;
- exact app-level warning/recovery marker appearance is timing-window dependent and should be treated as library/runtime-shaped rather than a strict contract in a very short outage run.

## What counts as normal

### Normal degradation

For the current canonical service, normal degradation under temporary NATS loss is:
- `/healthz` remains up;
- `/bios/status` remains readable;
- BIOS payload contract stays unchanged;
- NATS event distribution becomes unavailable;
- logs may show NATS client connection/reconnect errors.

This does **not** require:
- HTTP failure;
- subject/API changes;
- BIOS payload shape changes.

### Normal recovery

For the current canonical service, normal recovery is:
- after NATS returns, BIOS event publishing resumes on the same subject:
  - `qiki.events.v1.bios_status`
- first recovered event usually appears within about one publisher interval, plus reconnect jitter.

Operational expectation from this run:
- treat roughly `<= 1 publish interval + reconnect jitter` as normal;
- in the measured run, recovery was `5.106s`.

## Contracts unchanged

No runtime contracts were changed:
- same HTTP endpoints
- same BIOS event subject
- same BIOS payload fields
- no redesign of outage handling

## Done check

- there is measurable evidence for HTTP behavior during outage;
- there is a measured recovery time for event publishing after NATS returns;
- normal degradation and normal recovery are now explicitly described;
- subjects and contracts remain unchanged.
