# qcore identity derivation fix

## 1. Что было причиной discontinuity

Причина discontinuity была в q-core-local derivation seam, а не в ORION rule и не в q-sim contract.

Фактическая проблема:

- `src/qiki/services/q_core_agent/core/world_model.py` на `radar_frame` ingest path строил локальный `track_id` из mutation-sensitive полей;
- derivation включал `transponder_id`, а при его отсутствии ещё и `sensor_id:index`;
- при signature/transponder mutation тот же observed object мог получить новый q-core-local `track_id`;
- resumed contour затем не находил прежний contour `track_id` в `world_snapshot` и был вынужден fallback’иться по `target_designator`.

Итоговая форма бага:

- truth-facing label/signature менялся;
- q-core трактовал это как смену runtime identity;
- continuity ломалась до ORION comparison stage.

## 2. Какие файлы изменены

- `src/qiki/services/q_core_agent/core/world_model.py`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/q_core_agent/tests/test_radar_guards.py`
- `tests/unit/test_qiki_orion_intents_service.py`

## 3. Как изменена identity derivation logic

### A. В `world_model` разделены derived runtime identity и human-visible label

Для frame-derived tracks q-core больше не генерирует `track_id` из:

- `transponder_id`
- `sensor_id`
- fallback key вида `sensor_id:index`

Теперь логика такая:

- при первом появлении frame-derived object q-core выдаёт ему локальный runtime `track_id`;
- на следующих frame ingests q-core пытается продолжить тот же runtime object по kinematic continuity;
- matching делается по самой наблюдаемой цели:
  `range / bearing / elevation / radial velocity`;
- `transponder_id` и `transponder_mode` обновляются как truth-facing / human-visible поля, но не перевыпускают identity сами по себе.

### B. Добавлен stable continuity match для frame-derived tracks

В `WorldModel` введён локальный continuity helper:

- `_match_existing_frame_track_id(...)`

Он:

- ищет лучший existing frame-derived track по proximity в measurement space;
- сохраняет прежний `track_id`, если объект остался тем же;
- не зависит от mutation-sensitive label/signature;
- не зависит от смены `sensor_id` между ingest events.

### C. Resumed path теперь сначала идёт по runtime identity, а не по designator matching

В `qiki_orion_intents_service.py` добавлен явный runtime-id lookup:

- `_find_track_by_runtime_id(...)`

И `_select_target_track_for_resume(...)` теперь делает:

1. direct lookup по stored contour `track_id`
2. только потом fallback по `target_designator`

Это важно:

- resumed contour при наличии ранее известной identity больше не зависит от mutation label/signature;
- designator fallback остался как запасной путь, а не как первичный resumed selector.

### D. Human-visible label выделен отдельно

Добавлен helper:

- `_track_display_label(...)`

Он используется там, где нужен именно label/signature для человека:

- objective seed payload
- resume identity logging
- observation track snapshot

Тем самым разделение стало явным:

- `track_id` = derived runtime identity
- `transponder_id/id/callsign` = human-visible label/signature fields

## 4. Почему это не ломает canonical contour

Изменение не затрагивает canonical contour ownership.

Не менялось:

- q-sim contracts;
- внешние public subjects;
- bridge ownership;
- ORION decision rule;
- `signature_changed` semantics как outcome;
- operator-side comparison logic.

Что именно осталось неизменным:

- ORION по-прежнему может увидеть `signature_changed`, если live label действительно сменился;
- resumed contour по-прежнему использует stored contour identity;
- fallback по `target_designator` не удалён, а только понижен до secondary path.

То есть fix закрывает именно q-core seam:

- continuity объекта сохраняется;
- human-visible mutation остаётся наблюдаемой;
- canonical operator contour не переписан.

## 5. Какие тесты добавлены/обновлены

Добавлены/обновлены точечные тесты:

### `src/qiki/services/q_core_agent/tests/test_radar_guards.py`

- `test_world_model_keeps_frame_track_identity_across_transponder_and_sensor_mutation`

Проверяет сценарий:

- один и тот же observed object;
- меняются `transponder_id` и `transponder_mode`;
- меняется `sensor_id`;
- q-core сохраняет тот же `track_id`;
- label/signature обновляется, но новый target не порождается.

### `tests/unit/test_qiki_orion_intents_service.py`

- `test_select_target_track_for_resume_prefers_runtime_track_id_over_mutated_label`

Проверяет сценарий:

- resumed contour хранит предыдущий `track_id`;
- target label уже mutated и старый designator больше не совпадает;
- resumed selection всё равно берёт тот же runtime object по `track_id`;
- source остаётся `direct_by_contour_id`, а не `fallback_by_designator`.

Также остаётся валидным уже существующий resumed-observation test:

- `_build_safe_observation_response(...)` продолжает использовать тот же `observation_track_id`, но с обновлённым `observation_track_label`.

## 6. Что теперь должно происходить на resumed contour

Теперь ожидаемая последовательность такая:

1. q-core однажды получил runtime object и выдал ему локальный stable `track_id`.
2. У объекта позже меняется transponder/signature.
3. На следующем ingest q-core сохраняет тот же runtime `track_id`, потому что continuity держится по observed object, а не по label.
4. Resumed contour находит объект по stored contour `track_id`.
5. ORION получает:
   - тот же `observation_track_id`
   - обновлённый human-visible label/signature
6. Если label реально изменился, `signature_changed` остаётся честным outcome, но уже без ложной смены identity объекта.

Критический эффект:

- mutation label/signature больше не является достаточным основанием для рождения нового q-core target.

## 7. Что ещё остаётся вне scope

Вне scope этого fix:

- выдача first-class stable downstream truth object id со стороны q-sim;
- изменение bridge tracking ownership;
- изменение ORION comparison/result rules;
- большой рефакторинг radar/world-model pipeline;
- hard guarantee continuity across полный process restart q-core без upstream stable truth id.

То есть задача закрывает именно локальную q-core seam:

- убрать dependence on mutation-sensitive derivation;
- сохранить resumed continuity внутри текущего canonical contour;
- не переносить проблему в UI.
