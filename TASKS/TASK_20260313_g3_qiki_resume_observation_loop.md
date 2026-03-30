# TASK: G3-QIKI-008 — truth-backed resume observation loop after `hold_for_recheck`

**ID:** TASK_20260313_g3_qiki_resume_observation_loop  
**Status:** done  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-13

## Goal

После `G3-QIKI-007` state `hold_for_recheck` больше не должен оставаться тупиковой паузой. Нужен один минимальный truth-backed resume action, который живёт на текущем canonical path, закрывает `hold_for_recheck`, возвращает observation contour к одному разрешённому следующему шагу и формально закрывается одним continuation-result на том же objective contour.

## Chosen resume action

- Выбран action: `resume observation`.
- Почему каноничен:
  он живёт на том же active observation objective, использует те же `objective_id / proposal_id / request_id`, что deviation route, hidden event, review closure и `hold_for_recheck`, и публикуется по существующему operator action path.
- Почему минимален:
  добавляется ровно один операторский action, один follow-up transition и один следующий разрешённый observation step на том же path; без mission engine, generic hold/resume framework и без нового truth source.
- Какой contour открывает:
  после `hold_for_recheck` следующий честный шаг становится `resume_observation`, после чего для той же цели снова разрешён один cautious `safe observation`.
- Какой result честно закрывает:
  этот cautious continuation не открывает новую mission/objective ветку, а закрывается на том же payload как
  `observation_result_status=reconfirmed`.

## Canonical insertion point

- Resume action живёт в существующем ORION operator command path.
- Truth остаётся на тех же subjects:
  - `qiki.events.v1.operator.actions` для operator resume action;
  - `qiki.events.v1.operator.objectives` для follow-up state transition.
- Hidden-event source не меняется:
  `HIDDEN_EVENT_REVEALED` остаётся на существующем `qiki.events.v1.audit`.

## Minimal resume contract

- Preconditions:
  - active `observation_objective_update.status=confirmed`
  - active `follow_up_status=hold_for_recheck`
- Resume action:
  - operator issues `resume observation`
  - ORION publishes one action event with:
    - `event_type=HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED`
    - `reason_code=HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED`
    - same `objective_id / proposal_id / request_id`
- Follow-up transition:
  - `follow_up_status: hold_for_recheck -> resume_observation`
  - objective update `reason_code=OBJECTIVE_RESUME_OBSERVATION_SELECTED`
- ORION / QIKI effect:
  - ORION F1 shows that `hold_for_recheck` is no longer terminal and that one cautious `safe observation` is now the next allowed step
  - QIKI `allowed_when` changes from “safe recheck before resuming” to “issue one cautious safe observation for the same target”
  - ORION blocks new observation commands while `hold_for_recheck` is still open, so the resume action is not decorative
- Continuation-result closure:
  - after that one cautious `safe observation`, the same `observation_objective_update` payload records:
    - `observation_result_status=reconfirmed`
    - `observation_result_reason_code=OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED`
    - `observation_result_summary_en/ru`
  - `follow_up_status` is cleared because the same contour is now closed by a truth-backed result, not moved into a new branch

## Implementation

- `q_core_intents` now derives one additional truth-backed follow-up state from the existing operator action path:
  - `HIDDEN_EVENT_RESUME_OBSERVATION_SELECTED` => `follow_up_status=resume_observation`
- `OrionVApp` now exposes one new operator command on the same command path:
  - `action_resume_observation_follow_up()`
  - `_resume_observation_follow_up()`
  - command aliases `resume observation` / `resume_observation`
- Existing QIKI follow-up block now reflects the changed next step through the same legality/consequence payload.
- Existing ORION F1 objective block now shows:
  - `hold_for_recheck`
  - `resume_observation`
  - the next cautious `safe observation` step for the same target
  - the resulting `reconfirmed` continuation outcome once that step is completed
- Existing ORION command path now refuses new observation commands while `hold_for_recheck` is still active, which makes the resume action a real gate instead of UI-only text.
- Existing objective schema/README stay on the same truth source and already describe the same narrow result contract:
  - `schemas/asyncapi/qiki.events.v1.operator.objectives/v1/payload.schema.json`
  - `schemas/asyncapi/qiki.events.v1.operator.objectives/v1/README.md`

## Files changed

- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `tests/unit/test_qiki_orion_intents_service.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tools/orion_v_qiki_observation_objective_seed_smoke.py`
- `TASKS/TASK_20260313_g3_qiki_resume_observation_loop.md`
- `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`

## Proof target

- deviation path still reveals the same hidden event
- review loop still reaches `review_completed`
- post-review choice still reaches `hold_for_recheck`
- `resume observation` is operator-triggered on the same path
- `follow_up_status` changes to `resume_observation`
- ORION V shows the resumed next step
- QIKI next-step language changes accordingly
- the next allowed observation step (`safe observation` on the same target) can be issued after resume
- that resumed cautious observation closes on the same `objective_id / proposal_id / request_id`
- the closure is recorded as `observation_result_status=reconfirmed`, not as a new seed or new mission branch

## Proof and impact

- Relevant unit tests:
  - `tests/unit/test_qiki_orion_intents_service.py` proves the same-contour follow-up transition to `resume_observation`
  - `tests/unit/test_orion_v_qiki_loop.py` proves both the operator resume step and `resume_observation -> safe observation -> observation_result_status=reconfirmed` on the same objective
  - `tests/unit/test_orion_v_cockpit.py` proves ORION F1 text for both `resume_observation` and the final `reconfirmed` outcome
- Relevant smoke:
  - `tools/orion_v_qiki_observation_objective_seed_smoke.py`
  - official path proves `route_role=official` with objective confirmation and no deviation-only hidden-event / continuation-result branch
  - deviation path proves `route_role=deviation`, `HIDDEN_EVENT_REVEALED -> review_required -> review_confirm -> review_completed -> hold_for_recheck -> resume_observation -> safe observation -> CONTINUATION_RESULT=reconfirmed`
  - the smoke prints the continued `OBJECTIVE_ID`, `REQUEST_ID` and `ROUTE_ROLE`, which proves the result stays on the same contour and does not create a new seed
- Impact:
  - no new `Impact Metric` was applied for this closeout slice
  - reason: this narrow slice closes the already-existing continuation contour on the same truth path and does not add a new manual join / route-choice dimension beyond the earlier recorded G3 metrics

## Closeout

- Compared to `G3-QIKI-007`, `hold_for_recheck` is no longer the semantic dead-end of the loop.
- We now have one minimal resume loop:
  `HIDDEN_EVENT_REVEALED -> review_required -> review_confirm -> review_completed -> hold_for_recheck -> resume_observation -> safe observation -> observation_result_status=reconfirmed`
- This continuation-result remains on the same active observation objective contour; it does not create a new mission, a new objective seed, or a generic observation-results engine.
- Still out of scope:
  no generic hold/resume framework, no generic observation-results framework, no automatic re-execution, no multiple resume branches, no new truth source.
