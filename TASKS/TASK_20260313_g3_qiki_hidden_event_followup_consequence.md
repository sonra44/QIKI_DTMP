# TASK: G3-QIKI-005 — hidden observation event requires follow-up before the next observation objective

**ID:** TASK_20260313_g3_qiki_hidden_event_followup_consequence  
**Status:** done  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-13

## Goal

Сделать первый честный consequence loop после `G3-QIKI-004`: уже существующий hidden observation event должен менять следующий живой контур поведения, а не оставаться только linked fact reveal.

## Chosen consequence

- Выбран consequence: `review_required` follow-up на existing `observation_objective_update`.
- Почему он каноничен:
  hidden event уже приходит по truth-backed audit path и относится к той же observation objective через `objective_id/proposal_id/request_id`.
- Почему он минимален:
  не нужен новый engine, новый subject или новая миссионная ветка; меняется только следующий разрешённый шаг после confirmed objective.

## Canonical insertion point

- Consequence живёт в уже существующем `qiki.events.v1.operator.objectives` update payload, который ORION V и так публикует после real procedure + telemetry confirmation.
- Hidden event truth source не меняется:
  источник hidden event остаётся `qiki.events.v1.audit`; `observation_objective_update` лишь честно отражает, что этот truth-backed факт меняет follow-up contour.

## Minimal contract

- Existing payload extended only on confirmed observation closure:
  - `follow_up_status=review_required`
  - `follow_up_reason_code=HIDDEN_EVENT_REVIEW_REQUIRED`
  - `follow_up_event_type=HIDDEN_EVENT_REVEALED`
  - `follow_up_summary_en/ru`
- Linkage rule tightened:
  hidden-event follow-up matches by `objective_id/proposal_id/request_id` first, with procedure/target only as fallback.
- QIKI follow-up effect:
  after confirmed slow/deviation route, `QikiConsequenceV1.status` stays `pending` and `legality.allowed_when` now points the operator to review the linked hidden fact before issuing the next observation objective.

## Implementation

- ORION V now derives hidden-event follow-up only from the existing linked audit fact and projects it into the existing objective update payload.
- F1 objective block now shows the follow-up constraint and changes the next-step text from “go to next objective” to “review linked hidden fact first”.
- Official route remains unchanged:
  no hidden event, no follow-up marker, QIKI consequence still ends as `confirmed`.

## Proof

- Unit proof green:
  - `tests/unit/test_orion_v_app_incidents.py`
  - `tests/unit/test_orion_v_qiki_loop.py`
  - `tests/unit/test_orion_v_cockpit.py`
- Live-like canonical proof green:
  - `QIKI_OBSERVATION_STYLE=safe` -> `ROUTE_ROLE=official` -> `OBJECTIVE_FOLLOW_UP=none` -> `FINAL_QIKI_STATUS=confirmed`
  - `QIKI_OBSERVATION_STYLE=slow` -> `ROUTE_ROLE=deviation` -> `HIDDEN_EVENT_LINE=...HIDDEN_EVENT_REVEALED...` -> `OBJECTIVE_FOLLOW_UP=review_required` -> `FINAL_QIKI_STATUS=pending`

## Closeout

- Compared to `G3-QIKI-004`, hidden event is no longer just a reveal fact.
- We now have one real consequence:
  it changes the next allowed observation step and keeps the operator on a follow-up review contour.
- Still out of scope:
  no full mission consequence tree, no generic hidden-event reaction system, no new backend engine.
