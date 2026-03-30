1. Где identity и signature были смешаны

В `src/qiki/services/q_core_agent/core/world_model.py` snapshot отдавал только raw `track_id` и `transponder_id`, без явного разделения runtime identity и наблюдаемой signature.
В `src/qiki/services/q_core_agent/qiki_orion_intents_service.py` helper `_find_target_track(...)` искал target по mixed labels, включая `track_id`, то есть runtime identity могла участвовать в visible-target matching.
Там же `_track_display_label()` и resumed helpers работали с human-visible label, но без явного разведения между object continuity и visible signature layer.

2. Как они теперь разведены

В world-model snapshot для каждого radar track теперь явно публикуются:
- `object_identity`: truth/runtime identity объекта, привязанная к continuity `track_id`
- `visible_signature`: наблюдаемая visible signature, derived из transponder layer

В intents service:
- runtime identity ищется только через `_find_track_by_runtime_id(...)` по `object_identity`/`track_id`
- visible target selection (`_find_target_track(...)`) больше не использует runtime `track_id` как label surrogate
- visible label helper теперь опирается на `visible_signature`/transponder fields, а не подменяет object identity
- resumed contour snapshot читает identity и visible signature раздельно

3. Какие файлы изменены

- `src/qiki/services/q_core_agent/core/world_model.py`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/q_core_agent/tests/test_radar_guards.py`
- `tests/unit/test_qiki_orion_intents_service.py`

4. Какие тесты подтверждают новую семантику

`src/qiki/services/q_core_agent/tests/test_radar_guards.py`
- `test_world_model_keeps_frame_track_identity_across_transponder_and_sensor_mutation`

`tests/unit/test_qiki_orion_intents_service.py`
- `test_find_target_track_matches_visible_signature_not_runtime_identity`
- `test_build_observation_objective_event_splits_identity_from_visible_signature`
- `test_build_safe_observation_response_reuses_resumable_track_identity_for_signature_change`
- `test_select_target_track_for_resume_prefers_runtime_track_id_over_mutated_label`
- `test_select_target_track_for_resume_does_not_fallback_when_contour_identity_exists`

`tests/unit/test_orion_v_qiki_loop.py`
- `test_resumed_safe_observation_records_signature_changed_result_on_same_objective`

5. Как это помогает `signature_changed`

Теперь `signature_changed` может честно означать:
- тот же runtime object (`object_identity`/same contour binding)
- при этом изменился только visible signature layer (`visible_signature` / `track_label`)

Из-за этого mutation transponder/label больше не трактуется как implicit object replacement внутри q-core resumed path.

6. Что не менялось сознательно

- Не менялись `q-sim` telemetry/radar contracts
- Не менялись ORION decision rules
- Не менялся bridge
- Не делался model-wide рефактор вне узких мест resumed observation / signature semantics
