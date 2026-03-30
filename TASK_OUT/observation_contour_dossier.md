# Observation Contour Dossier

Current baseline note:
- This dossier reflects the post-closure baseline after the 2026-03-24 canonical live proof and follow-up seed-smoke alignment fix.
- `signature_changed` is closed with evidence on the canonical `docker-compose.phase1.yml` + `docker-compose.operator.yml` path.
- Earlier proof-stage wording for this contour is historical only and must not be read as the current blocker state.

## 1. End-to-end contour map

### Supported official path

`operator -> ORION command/input -> qiki.intents -> q-core-intents -> qiki.responses.qiki + qiki.events.v1.operator.objectives(seed, route_role=official) -> ORION procedure execution -> qiki.events.v1.operator.objectives(confirmed, no follow-up) -> ORION/QIKI projection`

- `safe observation` starts on `qiki.intents`.
- `q-core-intents` classifies it as `official` via `safe_pause_resume`.
- ORION executes the prepared procedure and publishes the confirmed objective update.
- No `review_required`, `hold_for_recheck`, `resume_observation`, or continuation-result branch is attached on the official path.

### Supported deviation path

`operator -> ORION command/input -> qiki.intents -> q-core-intents -> qiki.responses.qiki + qiki.events.v1.operator.objectives(seed, route_role=deviation, follow_up_status=review_required) + qiki.events.v1.audit(HIDDEN_EVENT_REVEALED) -> ORION procedure execution -> qiki.events.v1.operator.objectives(confirmed, review_required) -> operator review action -> qiki.events.v1.operator.actions -> q-core-intents -> qiki.events.v1.operator.objectives(review_completed) -> operator follow-up hold -> qiki.events.v1.operator.actions -> q-core-intents -> qiki.events.v1.operator.objectives(hold_for_recheck) -> operator resume observation -> qiki.events.v1.operator.actions -> q-core-intents -> qiki.events.v1.operator.objectives(resume_observation) -> operator safe observation on same target -> qiki.intents -> q-core-intents -> qiki.responses.qiki(resumable safe proposal, no new seed) -> ORION procedure execution + live track snapshot -> qiki.events.v1.operator.objectives(confirmed, observation_result_status=reconfirmed|signature_changed) -> ORION/QIKI projection`

- `slow observation` is the supported deviation-entry step.
- `review_required`, `hold_for_recheck`, and `resume_observation` are not free-standing services; they are states carried on `qiki.events.v1.operator.objectives`.
- `reconfirmed` and `signature_changed` are continuation-results authored by ORION on the same objective payload after resumed `safe observation`.

## 2. Step-by-step transitions

| Step | Who initiates | Subject / event in | Decision service | Transition field(s) | Who publishes next step | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `safe observation` initial official seed | Operator via ORION input | `qiki.intents` text starts with `safe observation` | `q-core-intents` handler | `procedure_name=safe_pause_resume`, `observation_style=safe`, `route_role=official` | `q-core-intents` publishes `qiki.responses.qiki` and `qiki.events.v1.operator.objectives` seed | Supported |
| `slow observation` deviation seed | Operator via ORION input | `qiki.intents` text starts with `slow observation` | `q-core-intents` handler | `procedure_name=safe_pause_slow_resume`, `observation_style=slow`, `route_role=deviation`, `follow_up_status=review_required` | `q-core-intents` publishes `qiki.responses.qiki`, objective seed, and `qiki.events.v1.audit` hidden-event | Supported |
| `review_required` | Derived from deviation objective + hidden-event reveal | Existing objective payload plus `HIDDEN_EVENT_REVEALED` audit fact | `q-core-intents` for seed, then ORION preserves it on confirmed update | `follow_up_status=review_required`, `follow_up_event_type=HIDDEN_EVENT_REVEALED`, `follow_up_reason_code=HIDDEN_EVENT_REVIEW_REQUIRED` | ORION publishes confirmed `qiki.events.v1.operator.objectives`; ORION also updates its local QIKI projection to pending/review-first | Supported |
| `review_completed` bridge | Operator action `review confirm` in ORION | `qiki.events.v1.operator.actions` with `event_type=HIDDEN_EVENT_REVIEW_ACKNOWLEDGED` | `q-core-intents` `operator_actions_handler` | Action `event_type` mapped to `follow_up_status=review_completed`, `reason_code=OBJECTIVE_REVIEW_CLOSED` | `q-core-intents` publishes `qiki.events.v1.operator.objectives` update | Supported |
| `hold_for_recheck` | Operator action `follow-up hold` in ORION | `qiki.events.v1.operator.actions` with `event_type=HIDDEN_EVENT_RECHECK_HOLD_SELECTED` | `q-core-intents` `operator_actions_handler` | Action `event_type` mapped to `follow_up_status=hold_for_recheck`, `reason_code=OBJECTIVE_POST_REVIEW_HOLD_SELECTED` | `q-core-intents` publishes `qiki.events.v1.operator.objectives` update | Supported |
| `resume_observation` | Operator action `resume observation` in ORION | `qiki.events.v1.operator.actions` with `event_type=HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED` | `q-core-intents` `operator_actions_handler` | Action `event_type` mapped to `follow_up_status=resume_observation`, `reason_code=OBJECTIVE_RESUME_OBSERVATION_SELECTED` | `q-core-intents` publishes `qiki.events.v1.operator.objectives` update | Supported |
| Resumed `safe observation` proposal | Operator via ORION input after `resume_observation` | `qiki.intents` text starts with `safe observation` | `q-core-intents` handler | Existing objective lookup by `follow_up_status=resume_observation` + matching target; refreshed track snapshot attached to proposed action | `q-core-intents` publishes `qiki.responses.qiki` only; ORION then runs procedure | Supported |
| `reconfirmed` | ORION after resumed safe procedure succeeds | ORION local procedure completion + live radar snapshot | ORION `OrionVApp` | `follow_up_status=resume_observation` and no same-track label change | ORION publishes `qiki.events.v1.operator.objectives` with `observation_result_status=reconfirmed` | Supported |
| `signature_changed` | ORION after resumed safe procedure succeeds | ORION local procedure completion + live radar snapshot | ORION `OrionVApp` | Same `track_id`, different non-empty `track_label` versus stored objective label | ORION publishes `qiki.events.v1.operator.objectives` with `observation_result_status=signature_changed` | Closed with evidence |

Notes:

- `review_completed` is a necessary bridge state even though it was not listed in the requested headline steps; without it the supported path cannot reach `hold_for_recheck`.
- On the resumed path, `q-core-intents` does not mint a new objective seed. The continuation stays on the same `objective_id / proposal_id / request_id`.

## 3. Subjects and payload fields

### Subjects

- `qiki.intents`
  - ORION publishes operator text intents here.
- `qiki.responses.qiki`
  - `q-core-intents` publishes prepared QIKI reply/proposal here.
- `qiki.events.v1.operator.objectives`
  - Canonical observation contour state lives here.
- `qiki.events.v1.operator.actions`
  - Operator review/hold/resume feedback lives here.
- `qiki.events.v1.audit`
  - Deviation-only hidden-event reveal lives here as `HIDDEN_EVENT_REVEALED`.

### Identity and routing fields

- `objective_id`
  - Seeded as `observation-{request_id}` and reused across the whole contour.
- `request_id`
  - Original QIKI request identity.
- `proposal_id`
  - Proposal identity tied to the prepared procedure.
- `objective_type=observation`
  - Filters which objective events participate in this contour.
- `procedure_name`
  - `safe_pause_resume` for official safe path, `safe_pause_slow_resume` for deviation entry.
- `observation_style`
  - `safe` or `slow`.
- `route_role`
  - `official` or `deviation`; this is the key split between the no-follow-up path and the review contour.
- `target_designator`
  - Human target key used to match resumable contour requests.

### Follow-up fields

- `follow_up_status`
  - Supported states in code: `review_required`, `review_completed`, `hold_for_recheck`, `resume_observation`.
- `follow_up_reason_code`
  - Encodes why the follow-up state changed.
- `follow_up_event_type`
  - Carries the canonical event bridge such as `HIDDEN_EVENT_REVEALED`, `HIDDEN_EVENT_REVIEW_ACKNOWLEDGED`, `HIDDEN_EVENT_RECHECK_HOLD_SELECTED`, `HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED`.
- `follow_up_summary_en/ru`
  - Human-readable state projection.
- `follow_up_allowed_when_en/ru`
  - QIKI next-step language that ORION reuses for consequence/legality projection.

### Continuation-result fields

- `observation_result_status`
  - Schema-supported values: `reconfirmed`, `signature_changed`.
- `observation_result_reason_code`
  - `OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED` or `OBJECTIVE_RESUMED_OBSERVATION_SIGNATURE_CHANGED`.
- `observation_result_summary_en/ru`
  - Final contour closeout text reused by ORION/QIKI projection.

### Live-track fields

- `track_id`
  - Stable contact identity used for same-contour matching.
- `track_label`
  - Compared pre/post resume to decide `reconfirmed` vs `signature_changed`.
- `track_range_m`
  - Carried through the objective payload.
- `track_quality`
  - Carried through the objective payload.
- `track_visible`
  - Set at seed time from world snapshot visibility.

## 4. Service owners per transition

### `q-core-intents`

- Owns command classification for `safe observation` and `slow observation`.
- Owns initial objective seeding on `qiki.events.v1.operator.objectives`.
- Owns the route split by `route_role`.
- Owns the follow-up state machine driven from `qiki.events.v1.operator.actions` into `review_completed`, `hold_for_recheck`, and `resume_observation`.
- Owns publishing `HIDDEN_EVENT_REVEALED` on `qiki.events.v1.audit`.

### ORION

- Owns operator command entry and gating.
- Owns operator feedback publication on `qiki.events.v1.operator.actions`.
- Owns procedure execution and procedure success/failure confirmation.
- Owns the resumed continuation-result decision for `reconfirmed` vs `signature_changed`.
- Owns projection of objective follow-up/result back into the visible QIKI consequence text.

### Operator actions stream

- Is the feedback bus from ORION back to `q-core-intents`.
- Carries the decisive `event_type` values that advance the contour after `review_required`.

### Operator objectives stream

- Is the single supported state carrier for the observation contour.
- Receives authored updates from both `q-core-intents` and ORION.
- Is what ORION uses as the canonical state snapshot for the active observation objective.

### q-sim / live radar truth

- Does not author the contour states directly.
- Supplies the live track snapshot that both seeds the objective and resolves the resumed continuation-result.

## 5. Confirmed by tests / confirmed by code / unresolved

### Confirmed by tests

- Unit-tested:
  - `safe observation` command classification and proposal building.
  - `slow observation` command classification and deviation seed building.
  - Deviation seed embeds `review_required`.
  - `review confirm` advances to `review_completed`.
  - `follow-up hold` advances to `hold_for_recheck`.
  - `resume observation` advances to `resume_observation`.
  - ORION blocks new observation commands while `hold_for_recheck` is still open.
  - Resumed `safe observation` can close as `reconfirmed`.
  - Resumed `safe observation` can close as `signature_changed` in unit harness conditions.
  - Cockpit/F1 projection exists for `review_required`, `review_completed`, `hold_for_recheck`, `resume_observation`, `reconfirmed`, and `signature_changed`.
- Test files carrying this proof:
  - `tests/unit/test_qiki_orion_intents_service.py`
  - `tests/unit/test_orion_v_qiki_loop.py`
  - `tests/unit/test_orion_v_app_incidents.py`
  - `tests/unit/test_orion_v_cockpit.py`

### Confirmed by code

- `q-core-intents` keeps an in-memory `latest_observation_objectives` map keyed by observation identity and uses it to translate operator actions back into objective updates.
- Resumed `safe observation` intentionally does not create a new objective seed when a matching `resume_observation` objective already exists.
- ORION computes continuation-result locally after procedure completion and then publishes the final objective update itself.
- Schema and README under `schemas/asyncapi/qiki.events.v1.operator.objectives/v1/` support `observation_result_status` values `reconfirmed` and `signature_changed`.

### Confirmed by tests gap

- No `tests/integration/**` pytest coverage was found for these named contour states.
- The stronger runtime evidence outside unit tests exists as task-documented live-like smoke, not as pytest integration tests.

### Current baseline

- `signature_changed` is code-supported, unit-supported, and closed with live-path evidence on the current canonical stack.
- The blocker is no longer procedure loading, generic resumed contour health, or seed-smoke instability.
- Remaining work for this contour is hardening/regression/cleanup only; do not reopen contour or ownership redesign without fresh regression evidence.

## 6. Где именно contour зависит от live truth

- `q-core-intents` refreshes the world snapshot before building both `slow observation` and `safe observation` responses.
- Objective seeds carry live track facts at creation time:
  - `track_visible`
  - `track_id`
  - `track_label`
  - `track_range_m`
  - `track_quality`
- The resumed path depends on live truth twice:
  - `q-core-intents` tries to refresh until the target track is available and reuses the resumable objective identity.
  - ORION resolves the final continuation-result through `_live_observation_track_snapshot`.
- `reconfirmed` is effectively the fallback when the resumed contour does not prove the stronger label-change condition.
- `signature_changed` depends on one exact live predicate:
  - stored objective `track_id` matches live `track_id`
  - stored objective `track_label` is non-empty
  - live `track_label` is non-empty
  - stored and live labels differ
- Because ORION falls back to previous label if live label is empty, silent/off-style transponder changes do not honestly satisfy `signature_changed`.

## 7. Что уже supported, а что historical

### Already supported

- Official path:
  - `safe observation -> confirmed objective`
  - no deviation-only follow-up branch
- Deviation path:
  - `slow observation -> review_required`
  - `review confirm -> review_completed`
  - `follow-up hold -> hold_for_recheck`
  - `resume observation -> resume_observation`
  - resumed `safe observation -> observation_result_status=reconfirmed`
- Supported means:
  - code path exists end-to-end,
  - unit tests cover the transitions,
  - the contour stays on the same `objective_id / proposal_id / request_id`,
  - no UI-only fork is required to understand the flow.

### Closed with evidence

- `resume_observation -> safe observation -> observation_result_status=signature_changed`
- Closure baseline:
  - the contract exists in code and schema,
  - unit tests cover it,
  - ORION projection exists,
  - the canonical live stack now has closure evidence on the same resumed contour.

### Historical note

- Earlier proof-stage wording for `signature_changed` belongs to the pre-closure investigation slice and is retained only as historical context in dedicated investigation artifacts.

### Practical tasking implication

- Point tasks for this contour should treat `qiki.events.v1.operator.objectives` as the canonical state carrier.
- Follow-up tasks must separate:
  - contour state ownership and event routing, which are already supported,
  - future regressions, which must be proven with fresh evidence before any contour/ownership redesign is reopened.
