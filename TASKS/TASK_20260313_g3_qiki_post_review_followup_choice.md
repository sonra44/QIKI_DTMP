# TASK: G3-QIKI-007 — truth-backed post-review follow-up choice on the existing observation contour

**ID:** TASK_20260313_g3_qiki_post_review_followup_choice  
**Status:** done  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-13

## Goal

После `G3-QIKI-006` review closure больше не должен быть просто снятием блокировки. Нужен один минимальный post-review choice, который живёт на текущем canonical path и меняет следующий observation contour без нового truth source и без branching framework.

## Chosen post-review choice

- Выбран choice: `hold for recheck`.
- Почему каноничен:
  он живёт на той же active observation objective, относится к тому же linked hidden fact и использует тот же `objective_id / proposal_id / request_id`, что deviation route, hidden event и review closure.
- Почему минимален:
  добавляется ровно один post-review operator action и один новый truth-backed follow-up state на существующем `observation_objective_update`; без mission tree, без generic choice engine, без нового UI-контура.
- Какой contour меняет:
  после `review_completed` следующий шаг теперь не “идти куда угодно дальше”, а перейти в осторожный `recheck` contour для той же observation target.

## Canonical insertion point

- Choice живёт в существующем ORION operator action path.
- Truth остаётся на тех же subjects:
  - `qiki.events.v1.operator.actions` для operator post-review action;
  - `qiki.events.v1.operator.objectives` для follow-up state transition.
- Hidden event source не меняется:
  `HIDDEN_EVENT_REVEALED` остаётся на существующем `qiki.events.v1.audit`.

## Minimal choice contract

- Preconditions:
  - active `observation_objective_update.status=confirmed`
  - active `follow_up_status=review_completed`
  - linked review ack `event_type=HIDDEN_EVENT_REVIEW_ACKNOWLEDGED`
- Post-review choice:
  - operator issues `follow-up hold`
  - ORION publishes one action event with:
    - `event_type=HIDDEN_EVENT_RECHECK_HOLD_SELECTED`
    - `reason_code=HIDDEN_EVENT_RECHECK_HOLD_SELECTED`
    - same `objective_id / proposal_id / request_id`
- Follow-up transition:
  - `follow_up_status: review_completed -> hold_for_recheck`
  - objective update `reason_code=OBJECTIVE_POST_REVIEW_HOLD_SELECTED`
- ORION / QIKI effect:
  - ORION F1 shows that review closure opened one post-review choice
  - after choice, ORION F1 shows `hold_for_recheck` as the next real contour
  - QIKI `allowed_when` changes from “select the post-review choice” to “run a cautious safe recheck for the same target”

## Implementation

- `OrionVApp` now derives three truth-backed follow-up states from linked canonical facts:
  - reveal fact => `review_required`
  - review ack => `review_completed`
  - post-review hold action => `hold_for_recheck`
- Added one new operator follow-up action on the existing command path:
  - `action_select_observation_recheck_hold()`
  - `_select_observation_recheck_hold()`
  - command alias `follow-up hold`
- Existing QIKI block now reflects the changed next step through the same legality/consequence payload rather than UI-only text.
- Existing cockpit objective block now shows:
  - open review requirement
  - review closure with one opened post-review choice
  - selected `hold_for_recheck` contour

## Files changed

- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `tests/unit/test_orion_v_app_incidents.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tools/orion_v_qiki_observation_objective_seed_smoke.py`

## Proof target

- deviation path still reveals the same hidden event
- review loop still reaches `review_completed`
- post-review choice `hold_for_recheck` is operator-triggered on the same path
- `follow_up_status` changes to `hold_for_recheck`
- ORION V shows the opened choice and the selected cautious contour
- QIKI next step changes to safe recheck language

## Closeout

- Compared to `G3-QIKI-006`, review closure is no longer the last semantic step.
- We now have one minimal post-review choice loop:
  `HIDDEN_EVENT_REVEALED -> review_required -> review_confirm -> review_completed -> hold_for_recheck`
- Still out of scope:
  no generic follow-up framework, no multi-branch mission tree, no automatic recheck execution, no new truth source.
