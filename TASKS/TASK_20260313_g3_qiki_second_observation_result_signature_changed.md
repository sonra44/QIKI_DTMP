# TASK: G3-QIKI-009 — second minimal continuation-result on the resumed observation contour

**ID:** TASK_20260313_g3_qiki_second_observation_result_signature_changed  
**Status:** closed_with_evidence  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-13

## 2026-03-24 closure addendum

- `signature_changed` is now closed on the canonical live path.
- The blocker was closed without changing the product contour:
  - bridge publish identity now keeps event identity separate from contact identity;
  - ORION binds q-core contour identity to the public track identity used on the live path;
  - resumed observation proof uses the canonical public-track flow and the seed smoke now aligns with that same truth source.
- Closure evidence is recorded in the 2026-03-24 live/runtime passes and follow-up stabilization notes:
  - live canonical proof recorded in Sovereign Memory `STATUS` entries `3210` and `3213`;
  - seed-smoke alignment fix recorded in `STATUS` entry `3216`;
  - the remaining logging-format issue in `Resume live snapshot` is non-semantic diagnostic noise only and is handled as stabilization cleanup, not blocker work.

## Goal

После уже закрытого `G3-QIKI-008` continuation-result слой не должен оставаться одноточечным. Нужен ровно один второй минимальный truth-backed observation outcome на том же canonical contour:

`resume_observation -> safe observation -> observation_result_status=<one new minimal outcome>`

без нового mission tree, нового truth source и без generic observation-results engine.

## Chosen second outcome

- Выбран outcome: `signature_changed`
- Почему каноничен:
  он остаётся на том же active observation objective contour и использует тот же `objective_id / proposal_id / request_id`, но даёт честный новый смысловой случай для radar-truth observation gameplay: тот же resumed contact больше не просто reconfirmed, а подтверждён как тот же contour с изменившейся live signature.
- Почему минимален:
  расширяется только уже существующий `observation_result_status` block на `qiki.events.v1.operator.objectives`; не появляется новый subject, новая mission seed-ветка, новый engine или отдельная ветка follow-up.
- Почему продуктово полезен:
  оператор и QIKI получают первый честный случай, когда resumed safe observation закрывает не “всё как раньше”, а “тот же contour подтверждён, но contact signature изменилась”.

## Canonical insertion point

- Truth lives on the existing `qiki.events.v1.operator.objectives` payload:
  - existing `observation_result_status`
  - existing `observation_result_reason_code`
  - existing `observation_result_summary_en/ru`
- Reused transit path:
  - current QIKI safe-observation proposal already returns an `ORION_PROCEDURE` action
  - that action now carries one minimal refreshed track snapshot (`observation_track_id/label/range/quality`) from the same radar truth, so ORION can publish the final continuation-result back onto the canonical objective payload.
- No new truth source:
  the new outcome is still authored as an objective update on the same subject, and ORION/QIKI only project what the objective payload records.

## Minimal contract

- New allowed value:
  - `observation_result_status=signature_changed`
- New reason code:
  - `observation_result_reason_code=OBJECTIVE_RESUMED_OBSERVATION_SIGNATURE_CHANGED`
- Reused fields:
  - existing `observation_result_summary_en`
  - existing `observation_result_summary_ru`
- Reused contour identity:
  - same `objective_id`
  - same `proposal_id`
  - same `request_id`
- Reused operator-visible data:
  - existing `track_id`
  - existing `track_label`
  - existing `track_range_m`
  - existing `track_quality`
- No speculative additions:
  - no generic outcome metadata
  - no outcome registry
  - no parallel continuation subject

## Truth-backed trigger

- Minimal trigger:
  during resumed `safe observation`, if the same resumed contour returns a refreshed live track snapshot and the contact label/signature on that contour differs from the stored objective `track_label`, the continuation-result becomes `signature_changed` instead of `reconfirmed`.
- Current narrow implementation:
  - QIKI safe-observation response for a resumable contour carries the refreshed track snapshot in the proposed action parameters.
  - ORION uses that refreshed snapshot when it publishes the final `observation_objective_update`.
- Important boundary:
  current implementation uses the existing resumed contour plus refreshed track snapshot and keeps the result on the same objective payload; it does **not** introduce a general signature-analysis subsystem.

## Files changed

- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `schemas/asyncapi/qiki.events.v1.operator.objectives/v1/payload.schema.json`
- `schemas/asyncapi/qiki.events.v1.operator.objectives/v1/README.md`
- `tests/unit/test_qiki_orion_intents_service.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tools/orion_v_qiki_observation_objective_seed_smoke.py`
- `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`

## Proof status

Green:

- targeted unit:
  - QIKI safe-observation response reuses resumable track identity and can carry a changed live signature snapshot
  - ORION app records `signature_changed` on the same objective contour
  - cockpit/F1 renders `signature_changed` as operator-visible outcome text
- live-like Docker smoke:
  - `official -> confirmed` still green
  - `deviation -> review_required -> review_confirm -> review_completed -> hold_for_recheck -> resume_observation -> safe observation -> observation_result_status=reconfirmed` still green on the same contour
- live ORION V launch:
  - fresh tmux session `orionlive_g3_signature` started through `./scripts/run_orion_v_live.sh`
  - F1 live bridge connected to the current stack and observed the canonical contour traffic

Historical 2026-03-13 blocker state (closed on 2026-03-24):

- full live runtime replay for `signature_changed`
  - proof-harness instability on the ORION smoke side is now fixed: the smoke uses an isolated tracks subscription instead of colliding with the live operator-console durable, waits for full ORION subscriptions, and proves a QIKI request/response roundtrip before the scenario starts
  - attempted narrow forcing path remains `sim.xpdr.mode=SPOOF` before resumed safe observation
  - fresh 2026-03-13 runtime diagnosis after harness stabilization narrowed the remaining blocker further: on the current canonical stack, the resumed contour target `ALLY-62FD23` keeps the same `track_id` and still keeps label `ALLY-*` in live `q_core` radar truth even after acknowledged `sim.xpdr.mode=SPOOF`
  - the smoke now fails early and explicitly with `signature_changed precondition failed: resumed contour track_id=<...> kept label ALLY-62FD23 after sim.xpdr.mode=SPOOF`
  - this means the unresolved gap is no longer “proof harness unstable”, but “the current live trigger does not produce a same-contour label flip on the chosen canonical observation target”, so `signature_changed` cannot yet be proven honestly on this runtime path
- this historical state is superseded by the 2026-03-24 canonical live proof and follow-up seed-smoke alignment fix

## Current verdict

- The second outcome is implemented honestly in code and objective contract terms.
- ORION V and QIKI both project it from the same canonical payload.
- `reconfirmed` remains working.
- `signature_changed` is now closed with live-path evidence; the remaining work moved to regression/hardening/cleanup, not blocker investigation.

## 2026-03-13 canonical runtime-trigger investigation

### What was checked

- Canon/task/bootstrap context for `G3-QIKI-009`, `resume_observation`, `qiki_orion_intents_service.py`, `orion_v/app.py`, `tools/orion_v_qiki_observation_objective_seed_smoke.py`, `SIMULATION_CONTROL_CONTRACT.md`, `REAL_DATA_MATRIX.md`, and the active board entry.
- Fresh Docker proof runs on the current canonical stack:
  - `python tools/orion_v_qiki_observation_objective_seed_smoke.py`
  - `QIKI_OBSERVATION_STYLE=slow QIKI_RESUME_XPDR_MODE=SPOOF python tools/orion_v_qiki_observation_objective_seed_smoke.py`
- Direct live probe through `qiki.commands.control` + `qiki.telemetry` + `q_core` world snapshot to separate:
  - command ACK truth,
  - telemetry truth,
  - same-contour radar-track truth used by resumed observation.

### Runtime findings

- `sim.xpdr.mode` is a real live command on the canonical stack.
  - `ACK ON True applied`
  - `ACK SPOOF True applied`
- Telemetry truth changes honestly:
  - `XPDR {'mode': 'ON', 'active': True, 'allowed': True, 'id': 'ALLY-62FD23'}`
  - `XPDR {'mode': 'SPOOF', 'active': True, 'allowed': True, 'id': 'SPOOF-E863B4'}`
- The resumed observation contour still does **not** get a same-track label flip from that command on the current live path.
  - Fresh deterministic smoke still stops with:
    `signature_changed precondition failed: resumed contour track_id=<...> kept label <...> after sim.xpdr.mode=SPOOF`
  - A direct `q_core` probe after `sim.xpdr.mode=ON` still failed to find any non-spoof public designator in the live world snapshot before resumed observation.
  - The live snapshot kept exposing spoof-labelled SR tracks while accumulating new track ids, so the command changed telemetry truth but did not produce a proved same-contour `track_label` transition for the resumed target.

### Canonical interpretation

- For the current implementation, `signature_changed` requires:
  - same `track_id`
  - different non-empty `track_label`
- On the current stack, the only existing runtime mutation point that can produce a different non-empty transponder label is `sim.xpdr.mode=SPOOF`.
- `sim.xpdr.mode=OFF` / `SILENT` are not valid substitutes for this outcome on the current contract:
  - they remove the live transponder id instead of replacing it with a new non-empty signature;
  - ORION falls back to the previous label when the live label is empty, so they do not honestly satisfy the `signature_changed` condition.
- Existing range/quality/reacquisition effects are real runtime phenomena, but they do not currently map to `signature_changed` on the same contour without redefining the outcome.

### Historical verdict after trigger search (2026-03-13; superseded on 2026-03-24)

- On 2026-03-13, no proved canonical runtime trigger had yet been demonstrated for `signature_changed` on the same resumed observation contour.
- That historical verdict is superseded by the 2026-03-24 closure work and live proof on the canonical stack.
