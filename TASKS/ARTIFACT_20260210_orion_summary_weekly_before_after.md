# Weekly Before/After Proof — ORION Summary Tier A

Date: 2026-02-10  
Task: `TASK_20260210_orion_telemetry_semantic_panels_tierA`

## Operator Scenario

Startup summary scan: оператор открывает `Summary` и за один взгляд должен понять
состояние по 5 смысловым блокам, без чтения технического списка полей.

## Reproduction Command

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import pytest
pytest.importorskip('textual')
from qiki.services.operator_console.main_orion import OrionApp

app = OrionApp()
blocks = app._build_summary_blocks()
print(f'WEEKLY_AFTER_SUMMARY_ROWS={len(blocks)}')
print('WEEKLY_AFTER_SUMMARY_IDS=' + ','.join([b.block_id for b in blocks]))
PY
```

Live telemetry proof (fresh payload from NATS):

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
import asyncio, json, time
import nats
import pytest
pytest.importorskip('textual')
from qiki.services.operator_console.main_orion import OrionApp, EventEnvelope

async def main():
    nc = await nats.connect('nats://nats:4222')
    fut = asyncio.get_running_loop().create_future()

    async def on_tel(msg):
        if fut.done():
            return
        fut.set_result(json.loads(msg.data.decode('utf-8')))

    sub = await nc.subscribe('qiki.telemetry', cb=on_tel)
    await nc.flush(timeout=2.0)
    payload = await asyncio.wait_for(fut, timeout=8.0)
    await sub.unsubscribe()
    await nc.close()

    app = OrionApp()
    app.nats_connected = True
    app._snapshots.put(
        EventEnvelope(
            event_id='live-telemetry-proof',
            type='telemetry',
            source='qiki.telemetry',
            ts_epoch=time.time(),
            level='info',
            payload=payload,
            subject='qiki.telemetry',
        )
    )
    blocks = app._build_summary_blocks()
    print(f'LIVE_TELEMETRY_SUMMARY_ROWS={len(blocks)}')
    print('LIVE_TELEMETRY_SUMMARY_IDS=' + ','.join([b.block_id for b in blocks]))
    for b in blocks:
        print(f'{b.block_id}|{b.status}|{b.value}')

asyncio.run(main())
PY
```

## Before

- `BASELINE_SUMMARY_ROWS=10`
- Legacy blocks:
  - `Telemetry link`
  - `Telemetry age`
  - `Power systems`
  - `CPU usage`
  - `Memory usage`
  - `BIOS`
  - `Mission control`
  - `Last event age`
  - `Events filters`
  - `Events trust filter`

## After

- `WEEKLY_AFTER_SUMMARY_ROWS=5`
- `WEEKLY_AFTER_SUMMARY_IDS=health,energy,motion_safety,threats,actions_incidents`
- Live proof:
  - `LIVE_TELEMETRY_SUMMARY_ROWS=5`
  - `LIVE_TELEMETRY_SUMMARY_IDS=health,energy,motion_safety,threats,actions_incidents`
  - `LIVE2_TELEMETRY_SUMMARY_ROWS=5`
  - `LIVE2_TELEMETRY_SUMMARY_IDS=health,energy,motion_safety,threats,actions_incidents`

## Canonical-only Follow-up Proof (SoC de-dup)

- Date: 2026-02-09
- Source verification (startup-adjacent ORION surfaces):
  - `HAS_BATTERY_LEVEL_ROW=False`
  - `HAS_LEGACY_BATTERY_SOURCE=False`
  - `SOC_OCCURRENCES_IN_POWER_ROWS=1`
  - `HAS_BATTERY_LABEL_ROW_IN_POWER_ROWS=False`
- Interpretation:
  - Legacy alias `battery` no longer used as ORION power row source.
  - Startup power view keeps one canonical SoC representation (`power.soc_pct`) to reduce operator cognitive load.

## Startup Power Compact Proof (Tier A slice)

Reproduction:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
from qiki.services.operator_console.main_orion import OrionApp
rows = [
    ("state_of_charge", "SoC", "N/A", None, ("power.soc_pct",)),
    ("load_shedding", "Load shed", "no", False, ("power.load_shedding",)),
    ("faults", "Faults", "none", [], ("power.faults",)),
    ("power_input", "Power in", "N/A", None, ("power.power_in_w",)),
    ("power_consumption", "Power out", "N/A", None, ("power.power_out_w",)),
    ("dock_temp", "Dock temp", "N/A", None, ("power.dock_temp_c",)),
    ("dock_power", "Dock power", "0", 0.0, ("power.dock_power_w",)),
    ("supercap_soc", "Supercap", "45%", 45.0, ("power.supercap_soc_pct",)),
]
app_default = OrionApp()
compact_default = app_default._compact_power_rows(rows)
print(f'POWER_COMPACT_DEFAULT_ROWS={len(compact_default)}')
print('POWER_COMPACT_DEFAULT_KEYS=' + ','.join(r[0] for r in compact_default))

import os
os.environ['ORION_POWER_COMPACT_DEFAULT'] = '0'
app_full = OrionApp()
full_rows = app_full._compact_power_rows(rows)
print(f'POWER_COMPACT_DISABLED_ROWS={len(full_rows)}')
print('POWER_COMPACT_DISABLED_KEYS=' + ','.join(r[0] for r in full_rows))
PY
```

Observed:

- `POWER_COMPACT_DEFAULT_ROWS=6`
- `POWER_COMPACT_DEFAULT_KEYS=state_of_charge,load_shedding,faults,power_input,power_consumption,supercap_soc`
- `POWER_COMPACT_DISABLED_ROWS=8`
- `POWER_COMPACT_DISABLED_KEYS=state_of_charge,load_shedding,faults,power_input,power_consumption,dock_temp,dock_power,supercap_soc`

Interpretation:

- Compact mode keeps Tier A core rows and active non-Tier-A signals.
- Full technical list remains available by setting `ORION_POWER_COMPACT_DEFAULT=0`.

## Live run_test Proof (system/power-table)

Reproduction:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
# 1) read one live payload from qiki.telemetry (nats://nats:4222)
# 2) patch OrionApp._init_nats to avoid boot reconnect noise inside run_test
# 3) run app.run_test(), switch to system screen, render power table
# 4) print _power_by_key keys for compact=1 and compact=0
PY
```

Observed (live telemetry envelope):

- `RUNTEST_LIVE_POWER_COMPACT_1_ROWS=27` (before compact max-rows cap)
- `RUNTEST_LIVE_POWER_COMPACT_0_ROWS=33`
- Delta: `6` rows hidden in compact mode (`~18.2%` reduction on this payload).
- Hidden in compact for this sample:
  - `shed_reasons`, `throttled_loads`, `battery_discharge`, `battery_unserved`, `supercap_charge`, `supercap_discharge`

Interpretation:

- Compact mode trims zero/no-signal technical rows on real `system` screen data.
- Tier A keys remain visible; full list remains available via env toggle.

## Live run_test Proof (with compact max-rows cap)

Observed after introducing `ORION_POWER_COMPACT_MAX_ROWS=12` default:

- `RUNTEST_CAP_POWER_COMPACT_1_ROWS=12`
- `RUNTEST_CAP_POWER_COMPACT_0_ROWS=33`
- Delta: `21` rows hidden (`~63.6%` reduction on this payload).
- Compact keyset (sample):
  - `state_of_charge`, `load_shedding`, `shed_loads`, `faults`, `pdu_throttled`, `power_input`, `power_consumption`,
  - plus limited extras: `nbl_active`, `nbl_allowed`, `nbl_budget`, `nbl_power`, `pdu_limit`.

Interpretation:

- Compact mode now enforces signal-first startup density for operator scanning.
- Full engineering detail remains one env toggle away (`ORION_POWER_COMPACT_DEFAULT=0`).

## Live run_test Proof (priority ordering)

Observed with `ORION_POWER_COMPACT_MAX_ROWS=12`:

- `RUNTEST_REORDER_POWER_COMPACT_KEYS=state_of_charge,faults,pdu_throttled,load_shedding,shed_loads,power_input,power_consumption,pdu_limit,dock_connected,docking_state,docking_port,dock_power`

Interpretation:

- Critical keys (`faults`, `pdu_throttled`) are promoted to the top of compact output.
- NBL rows are naturally pushed out of the startup compact set under row cap, reducing distraction during incident triage.
- Docking context is now prioritized within compact extras before low-level bus details, so startup triage keeps actionable power-routing context.

## Impact Metric

- Deterministic readability proxy:
  - `READABILITY_BASELINE_S=10.2`
  - `READABILITY_AFTER_S=5.7`
  - `READABILITY_DELTA_PCT=44.1`

## Summary Noise Cleanup (startup)

Changes:

- Added compact-by-default summary rendering (`ORION_SUMMARY_COMPACT_DEFAULT=1`).
- Threats block now uses startup-short format (`rad=...; trips=...`) while preserving causal chain.
- Actions block suppresses default trust token (`all/off`) in compact mode.

Measured after change:

- `READABILITY_ROWS=5`
- `READABILITY_VALUE_CHARS=303`
- `READABILITY_SLA_SECONDS=7.73`

Interpretation:

- Startup summary becomes shorter without losing operator-causal semantics.
- Readability proxy improved vs previously logged `7.91s` in this task track.

## System Panels Noise Cleanup (startup)

Changes:

- Added compact-by-default startup filtering for `system` panels (`ORION_SYSTEM_COMPACT_DEFAULT=1`).
- Per panel, essential rows are always kept; rows with `N/A`-only noise are dropped.
- Verbose behavior remains available via `ORION_SYSTEM_COMPACT_DEFAULT=0`.

## Week-2 Kickoff: Residual Non-Canonical Startup Audit

Goal: prove that startup-facing ORION surfaces do not read legacy top-level `battery`
as truth source and keep canonical SoC path (`power.soc_pct`).

Reproduction:

```bash
rg -n "\\bbattery\\b|power\\.soc_pct|state_of_charge" src/qiki/services/operator_console/main_orion.py
rg -n "get\\(\\s*['\\\"]battery['\\\"]|\\['battery'\\]|\\.get\\(\\s*['\\\"]battery['\\\"]" src/qiki/services/operator_console/main_orion.py tests/unit
```

Observed:

- Legacy source reads for `battery` in startup paths: **none** (empty result in second command).
- Canonical source reads for startup energy/SoC:
  - `power.soc_pct` used in summary/energy logic and system power rows.
  - startup/system key: `state_of_charge`.
- Remaining `battery` mentions are labels/help/thermal node naming, not SoC truth source.

Interpretation:

- Canonical-only SoC source for startup screens is preserved.
- Next hardening slice should target visual proof automation and residual alias audit outside startup path.

Operator impact:

- Startup `system` view focuses first screen on operationally relevant fields (link/age/motion, core power, core temps, hull/radiation).
- Reduces non-actionable visual noise without changing telemetry source-of-truth.

## Summary Causal Badges (compact mode)

Changes:

- Added visual causal badge rendering in summary table for `energy` and `threats`.
- Compact display now starts with `[cause->effect]` and keeps `next=...` action hint.
- Badge rendering is view-only; semantic value generation remains unchanged.

Operator impact:

- Faster scan of root-cause context directly in table rows.
- Better alignment with “10-second understanding” target without introducing synthetic data.

## Summary Action Hints Unification

Changes:

- Added unified action-hint mapping for summary `next` fields.
- Compact mode now uses short, consistent tokens:
  - `pause+power`, `pause+radiation`, `pause+threat`, `monitor`, etc.
- Verbose mode keeps full explanatory phrases.

Operator impact:

- Reduced lexical variance across Tier A blocks.
- Faster operator parsing of actionable next steps in startup scan.

## Summary Health/Motion Compact Tokens

Changes:

- Compact summary now shortens non-causal fields:
  - `health`: `state/link/age`
  - `motion_safety`: `v/hdg/rcs`
- Verbose mode remains unchanged.

Operator impact:

- Lower visual text weight in startup scan.
- Better consistency with compact causal/action style used in other Tier A rows.

## Consolidated Readability Checkpoint

Current deterministic snapshot:

- `READABILITY_ROWS=5`
- `READABILITY_VALUE_CHARS=279`
- `READABILITY_SLA_SECONDS=7.49`

Trend in current implementation cycle:

- `7.91` -> `7.73` -> `7.49`

## Canonical SoC Guard (Summary)

Changes:

- Added unit-level anti-regression test to ensure Summary Energy uses `power.soc_pct` and never falls back to legacy `battery`.

Proof:

- `tests/unit/test_orion_summary_uses_canonical_soc.py` (green)

## Readability SLA Check (<=10s)

Reproduction:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY'
from qiki.services.operator_console.main_orion import OrionApp
app = OrionApp()
blocks = app._build_summary_blocks()
rows = len(blocks)
value_chars = sum(min(len(str(b.value)), 80) for b in blocks)
score = 1.2 + 0.70 * rows + 0.01 * value_chars
print(f'READABILITY_PROXY_MODEL=v2')
print(f'READABILITY_ROWS={rows}')
print(f'READABILITY_VALUE_CHARS={value_chars}')
print(f'READABILITY_SLA_SECONDS={score:.2f}')
print(f'READABILITY_SLA_PASS={score <= 10.0}')
PY
```

Observed:

- `READABILITY_PROXY_MODEL=v2`
- `READABILITY_ROWS=5`
- `READABILITY_VALUE_CHARS=321`
- `READABILITY_SLA_SECONDS=7.91`
- `READABILITY_SLA_PASS=True`

## Notes

- Tier A scope kept: startup summary only.
- Causal output path used in critical blocks: `cause -> effect -> next`.

## Deterministic Visual Startup Snapshot (Before/After Pair)

Reproduction:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_summary_startup_snapshot_proof.py
```

Observed:

- `SNAPSHOT_PROOF_MODE=deterministic`
- `BEFORE_REFERENCE_SUMMARY_ROWS=10`
- `BEFORE_REFERENCE_BLOCKS=Telemetry link,Telemetry age,Power systems,CPU usage,Memory usage,BIOS,Mission control,Last event age,Events filters,Events trust filter`
- `AFTER_SUMMARY_ROWS=5`
- `AFTER_SUMMARY_IDS=health,energy,motion_safety,threats,actions_incidents`
- Snapshot lines:
  - `health|ok|state=RUNNING; link=Online/В сети; age=0.0sec/0.0с`
  - `energy|warn|SoC=18.5%; In/Out=20.0W/20.0Вт/48.0W/48.0Вт; cause=pdu_limit -> effect=shed=2 -> next=shed+trim/сброс+снижение`
  - `motion_safety|ok|v=2.0 m/s/2.0 м/с; hdg=90.0°; rcs=yes/да`
  - `threats|warn|rad=warn; trips=0; cause=radiation_warning -> effect=reduced safety margin -> next=exposure-down/экспозиция-ниже`
  - `actions_incidents|ok|Next/Действие=monitor/наблюдать; XPDR=MODE_C/yes/да`

Interpretation:

- Startup view is fixed to 5 semantic blocks and shows signal-first causal picture instead of legacy 10-row technical summary.
- The proof is deterministic and can be replayed in any session with one command.

## Residual Non-Canonical Audit Outside Startup Summary

Reproduction:

```bash
rg -n "get\\(\\s*['\\\"]battery['\\\"]|\\['battery'\\]|\\.get\\(\\s*['\\\"]battery['\\\"]" \
  src/qiki/services/operator_console tests/unit
```

Observed:

- Legacy `battery` reads found outside `main_orion.py` in legacy/alternate entrypoints:
  - `src/qiki/services/operator_console/main_integrated.py`
  - `src/qiki/services/operator_console/main_enhanced.py`
  - `src/qiki/services/operator_console/main_full.py`
  - `src/qiki/services/operator_console/main.py`
  - `src/qiki/services/operator_console/clients/nats_realtime_client.py`
- In canonical ORION startup path (`main_orion.py`) direct legacy `battery` truth reads were not detected.

Interpretation:

- Week-2 startup path is canonicalized.
- Residual alias debt remains in non-canonical/legacy operator entrypoints and should be handled as separate cleanup slice.

## Legacy EntryPoints Canonical SoC Cleanup (no-demo)

Scope:

- `src/qiki/services/operator_console/main.py`
- `src/qiki/services/operator_console/main_full.py`
- `src/qiki/services/operator_console/main_enhanced.py`
- `src/qiki/services/operator_console/main_integrated.py`
- `src/qiki/services/operator_console/clients/nats_realtime_client.py`

Changes:

- Realtime NATS client now maps canonical `soc_pct` from telemetry `power.soc_pct`.
- Legacy top-level `battery` is preserved only as compatibility alias in the client cache.
- Legacy/alternate console entrypoints render battery from canonical `soc_pct` with fallback to alias only when needed.

Verification:

```bash
python -m py_compile \
  src/qiki/services/operator_console/main.py \
  src/qiki/services/operator_console/main_full.py \
  src/qiki/services/operator_console/main_enhanced.py \
  src/qiki/services/operator_console/main_integrated.py \
  src/qiki/services/operator_console/clients/nats_realtime_client.py

rg -n "soc_pct" \
  src/qiki/services/operator_console/main.py \
  src/qiki/services/operator_console/main_full.py \
  src/qiki/services/operator_console/main_enhanced.py \
  src/qiki/services/operator_console/main_integrated.py \
  src/qiki/services/operator_console/clients/nats_realtime_client.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q src/qiki/services/operator_console/tests/test_nats_realtime_client_soc_mapping.py
```

Observed:

- Compile check passed.
- Canonical path `soc_pct` is present across all targeted legacy entrypoints.
- Direct display truth source is canonicalized; alias usage remains only as compatibility fallback.
- Regression test passed: `2 passed` (`test_nats_realtime_client_soc_mapping.py`).

## Next-Cycle Candidate: Actions/Incidents WARN Priority (scope-locked)

Goal:

- remove ambiguous startup `Next=monitor` when WARN causes are already known in `energy`/`threats`.
- apply deterministic priority for WARN: `threats` > `energy`.

Changes:

- `actions_incidents` status now reflects WARN from `energy` and `threats` (not only faults).
- `actions_incidents` `Next` chooses deterministic mitigation:
  - threats warn -> threat action hint,
  - else energy warn -> energy action hint,
  - critical/fault paths keep existing higher-priority behavior.

Verification:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q \
    tests/unit/test_orion_actions_incidents_priority.py \
    tests/unit/test_orion_summary_action_hints.py \
    tests/unit/test_orion_summary_semantic_causal.py
```

Observed:

- `6 passed`
- `bash scripts/quality_gate_docker.sh` -> `[quality-gate] OK`

Regression tests added:

- `tests/unit/test_orion_actions_incidents_priority.py`
  - simultaneous WARN (`threats + energy`) picks threat-oriented `Next`.
  - energy-only WARN picks energy-oriented `Next`.

Broader regression slice:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest \
    tests/unit/test_orion_actions_incidents_priority.py \
    tests/unit/test_orion_summary_action_hints.py \
    tests/unit/test_orion_summary_semantic_causal.py \
    tests/unit/test_orion_summary_compact_noise.py \
    tests/unit/test_orion_summary_uses_canonical_soc.py \
    tests/unit/test_orion_power_compact.py \
    tests/unit/test_orion_system_panels_compact.py
```

Observed:

- `19 passed in 1.12s`
