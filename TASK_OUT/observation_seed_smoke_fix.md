# Observation Seed Smoke Fix

## 1. Почему падал текущий smoke

`tools/orion_v_qiki_observation_objective_seed_smoke.py` выбирал initial target через `_pick_live_target_designator()` только из `q_core` world snapshot. В live stack public-visible designator уже доказан в canonical ORION/public truth path, но не обязан появляться вовремя в `q_core` snapshot. Из-за этого smoke падал раньше с `timeout while waiting for live radar track with public designator in q_core world snapshot`, не доходя до observation seed и resumed comparison.

## 2. Чем seed path smoke отличался от успешного precomparison proof

Успешный `tools/orion_v_resume_precomparison_probe.py` брал initial target из `app._latest_radar_tracks`, то есть из ORION live radar cache / public truth space. Smoke брал initial target из другого truth source: `q_core` snapshot. Это и было рассогласование harness path относительно canonical public track flow.

## 3. Какие файлы изменены

- `tools/orion_v_qiki_observation_objective_seed_smoke.py`
- `tools/orion_v_resume_precomparison_probe.py`
- `tools/orion_v_target_seed_sources.py`
- `tests/unit/test_orion_v_target_seed_sources.py`

## 4. Как теперь выбирается initial target

Добавлен общий helper `pick_initial_target_designator(...)`.

Новый порядок:

1. Сначала берётся public-visible designator из ORION live radar cache.
2. `require_non_spoof=True` фильтрует именно public-visible label/designator (`transponder_id`/`id`/`callsign`) в этом ORION/public truth space.
3. Только если ORION/public truth не дал пригодной цели, используется fallback в `q_core` world snapshot.

Smoke теперь ещё и явно ждёт `ORION live radar cache` перед выбором initial target, чтобы seed phase не зависел только от `q_core`.

## 5. Какой truth source теперь primary

Primary source: ORION live radar cache (`app._latest_radar_tracks`), то есть canonical public track flow.

Именно этот source уже использовался успешным precomparison proof и именно он совпадает с resumed-comparison path в ORION app.

## 6. Какой fallback оставлен и почему

Оставлен `q_core` world snapshot fallback.

Причина: это безопасный резерв для smoke harness, если public cache временно пуст, но при этом основной сценарий теперь больше не зависит только от `q_core`. Fallback явно размечается как `q_core_world_snapshot_fallback`, чтобы источник выбора был виден в логике smoke.

Дополнительно аналогично выровнен spoof/signature-flip precondition watcher перед resumed safe observation: теперь он сначала смотрит на bound ORION public track, а `q_core` используется только как fallback. Это не меняет comparison rule, а только убирает harness-only зависимость от `q_core`.

## 7. Какие тесты/проверки добавлены

Добавлены узкие regression tests в `tests/unit/test_orion_v_target_seed_sources.py`:

- ORION public truth предпочитается вместо `q_core` fallback.
- `require_non_spoof=True` фильтрует spoof label в ORION/public truth и всё ещё не уходит в `q_core`, если в live public cache есть нормальная цель.

Проверки:

- `pytest -q tests/unit/test_orion_v_target_seed_sources.py`
- `python -m py_compile tools/orion_v_qiki_observation_objective_seed_smoke.py tools/orion_v_resume_precomparison_probe.py tools/orion_v_target_seed_sources.py`
- live smoke:
  `docker compose -f docker-compose.phase1.yml exec -T -e QIKI_OBSERVATION_STYLE=slow -e QIKI_RESUME_XPDR_MODE=SPOOF -e QIKI_INITIAL_XPDR_MODE=ON qiki-dev python tools/orion_v_qiki_observation_objective_seed_smoke.py`

## 8. Дошёл ли smoke до observation seed / resumed path после фикса

Да.

Подтверждено live run:

- `INITIAL_TARGET_SOURCE=orion_live_radar_cache`
- `OK: orion_v_qiki_observation_objective_seed_smoke`
- `OBJECTIVE_STATUS=confirmed`
- `OBJECTIVE_FOLLOW_UP_AFTER_RESUME=resume_observation`
- `CONTINUATION_RESULT=signature_changed`
- `FINAL_QIKI_STATUS=confirmed`

Это означает:

- canonical contour поднят;
- live target найден в seed phase без старого `q_core` timeout;
- smoke дошёл до observation objective seed;
- smoke прошёл дальше до уже исправленного resumed-comparison path;
- blocker `signature_changed` не переоткрыт.

## 9. Если всё ещё нет — точная локализация нового остаточного gap

Блокирующего gap по seed path больше нет.

Остался неблокирующий шум в live логах: в `src/qiki/services/operator_console/orion_v/app.py` есть logging-format mismatch внутри `Resume live snapshot` logger.info, из-за чего в proof run печатается `TypeError: not all arguments converted during string formatting`. Это не сломало smoke и не относится к seed-source alignment, но стоит отдельно подчистить как diagnostic noise.
