1. Где selection был слабым

`q_core_agent/qiki_orion_intents_service.py` в resumed path сначала пытался использовать `preferred_track_id`, но при miss сразу мог перейти к `_find_target_track(... target_designator ...)`. Это делало contour continuity недоказуемой: если живой contour уже существовал, resumed flow всё равно мог silently переизбрать другой runtime object по designator. Дополнительно safe-response терял `observation_track_id`, когда live contour временно не находился.

2. Какие изменения внесены

Добавлен явный contour snapshot extraction из resumable objective.
`_select_target_track_for_resume(...)` теперь принимает флаг `allow_designator_fallback` и различает contour-first path от designator fallback.
`_build_safe_observation_response(...)` теперь строит action parameters из live match поверх contour snapshot и сохраняет contour-bound `observation_track_id`, даже если live match отсутствует.
`_refresh_agent_snapshot_until_target_track(...)` теперь использует тот же contour-first priority и логирует reason/fallback policy явно.

3. Новый priority order

1. `direct_contour_match`: есть contour-bound `track_id`, и live runtime track с этим id найден.
2. `contour_miss`: contour-bound `track_id` есть, но live runtime track с этим id не найден; fallback не разрешается silently.
3. `fallback_by_designator`: применяется только если contour-bound `track_id` реально отсутствует.
4. `no_match`: нет contour match и нет допустимого designator match.

4. Когда fallback теперь допустим

Fallback по `target_designator` допустим только если resumable contour не даёт usable contour-bound runtime identity, то есть `track_id`/`observation_track_id` отсутствует. Если contour identity уже есть, resumed selection не имеет права переизбрать цель по designator без явного `contour_miss` в диагностике.

5. Какие тесты покрывают fix

`tests/unit/test_qiki_orion_intents_service.py`
- `test_select_target_track_for_resume_prefers_runtime_track_id_over_mutated_label`
- `test_select_target_track_for_resume_does_not_fallback_when_contour_identity_exists`
- `test_select_target_track_for_resume_uses_designator_only_when_contour_identity_missing`
- `test_build_safe_observation_response_keeps_contour_snapshot_when_live_match_is_missing`
- `test_build_safe_observation_response_reuses_resumable_track_identity_for_signature_change`

`tests/unit/test_orion_v_qiki_loop.py`
- `test_resumed_safe_observation_records_signature_changed_result_on_same_objective`

6. Как это влияет на resumed contour semantics

Resumed observation снова трактуется как продолжение уже существующего contour, а не как новый target lookup. `signature_changed` теперь остаётся проверяемым на том же runtime contour: label/signature может измениться, но contour-bound identity не проигрывает designator fallback без явной причины.
