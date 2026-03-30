# TASK: G3-QIKI-006 — truth-backed review action closure loop for hidden observation event

**ID:** TASK_20260313_g3_qiki_review_action_closure_loop  
**Status:** done  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-13

## Goal

Замкнуть минимальный `G3` review loop после `G3-QIKI-005`: hidden observation event уже переводит objective в `review_required`, теперь нужен один каноничный truth-backed review action, который закрывает follow-up на существующем objective/QIKI/ORION path.

## Chosen review action

- Выбран action: операторское подтверждение review linked hidden fact через существующий ORION command path, команда `review confirm`.
- Почему он каноничен:
  review относится к уже активной observation objective и привязан к тем же `objective_id / proposal_id / request_id`, что и hidden event.
- Почему он минимален:
  не нужен новый mission engine, новый truth source, новая ветка UI или generic review framework; используется уже существующий operator action/audit/objective update path.

## Canonical insertion point

- Review action живёт в существующем ORION operator action path.
- Closure truth публикуется поверх уже существующих subjects:
  - `qiki.events.v1.operator.actions` для review acknowledgment;
  - `qiki.events.v1.operator.objectives` для follow-up state transition.
- Hidden event source не меняется:
  `HIDDEN_EVENT_REVEALED` по-прежнему приходит из существующего `qiki.events.v1.audit`.

## Minimal review closure contract

- Preconditions:
  - active `observation_objective_update.status=confirmed`
  - active `follow_up_status=review_required`
  - linked fact `event_type=HIDDEN_EVENT_REVEALED`
- Review action:
  - operator issues `review confirm`
  - ORION publishes one action event with:
    - `event_type=HIDDEN_EVENT_REVIEW_ACKNOWLEDGED`
    - `reason_code=HIDDEN_EVENT_REVIEW_ACKNOWLEDGED`
    - identity fields `objective_id / proposal_id / request_id`
- Follow-up transition:
  - `follow_up_status: review_required -> review_completed`
  - objective update `reason_code=OBJECTIVE_REVIEW_CLOSED`
- ORION/QIKI effect:
  - ORION F1 shows review closure instead of an open constraint
  - `QikiConsequenceV1.status: pending -> confirmed`
  - `legality.allowed_when` changes from “review first” to “next observation objective may proceed”

## Implementation

- `OrionVApp` now derives follow-up state from two linked truths on the existing path:
  - reveal fact => `review_required`
  - review ack fact => `review_completed`
- Added one operator review action handler:
  `action_ack_observation_review()` / `_ack_observation_review()`.
- Existing cockpit rendering now distinguishes:
  - open review constraint
  - closed review contour
- Existing observation smoke now proves the whole loop for deviation path.

## Files changed

- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `tests/unit/test_orion_v_app_incidents.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tools/orion_v_qiki_observation_objective_seed_smoke.py`

## Proof

- Unit proof green:
  - `tests/unit/test_orion_v_app_incidents.py`
  - `tests/unit/test_orion_v_qiki_loop.py`
  - `tests/unit/test_orion_v_cockpit.py`
- Live-like canonical proof green:
  - `QIKI_OBSERVATION_STYLE=slow`
  - `ROUTE_ROLE=deviation`
  - `HIDDEN_EVENT_LINE=...HIDDEN_EVENT_REVEALED...`
  - `OBJECTIVE_FOLLOW_UP=review_required`
  - `REVIEW_ACTION=review_confirm`
  - `OBJECTIVE_FOLLOW_UP_AFTER_REVIEW=review_completed`
  - `PRE_REVIEW_QIKI_STATUS=pending`
  - `FINAL_QIKI_STATUS=confirmed`

## Closeout

- Compared to `G3-QIKI-005`, `review_required` is no longer a dead-end.
- We now have one real closure loop:
  hidden event reveal -> review required -> one review acknowledgment -> review completed -> QIKI/ORION closure.
- Still out of scope:
  no generic review engine, no branching consequence tree, no backend-wide review framework, no new mission system.
