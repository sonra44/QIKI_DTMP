# TASK-0023 — Radar Policy v3 (YAML profiles + adaptive load)

## Зачем
- Убрать разброс policy-настроек только по ENV.
- Ввести воспроизводимые профили (`navigation|docking|combat`) с единым YAML-источником.
- Сохранить backward-compatible ENV override и fail-fast/no-silent режим для битого YAML.
- Добавить аккуратную адаптацию по нагрузке (EMA + hysteresis + cooldown) без флаппинга.

## Что сделано
- Добавлен ресурс: `src/qiki/resources/radar/policy_v3.yaml`
  - `schema_version: 1`
  - `defaults`
  - `profiles.navigation|docking|combat`
  - `adaptive`
- Добавлен loader/validator: `src/qiki/services/q_core_agent/core/radar_policy_loader.py`
  - `load_policy_yaml(path)`
  - `validate_policy_schema(doc)`
  - `build_effective_policy(profile, env, yaml_doc)`
  - `load_effective_render_policy(...)`
- Интеграция в pipeline:
  - `RadarPipeline` теперь загружает policy через `load_effective_render_policy()`.
  - Порядок резолвинга: `YAML defaults < YAML profile < ENV overrides`.
  - Добавлено adaptive-состояние (EMA frame_ms/targets, confirm/cooldown, уровень адаптации).
  - В `RADAR_RENDER_TICK` добавлено поле `adaptive_level` (контракт не ломается).

## ENV knobs
- `RADAR_POLICY_PROFILE` (`navigation|docking|combat`, default `navigation`)
- `RADAR_POLICY_YAML` (путь к yaml; если не задан — встроенный ресурс)
- `RADAR_POLICY_STRICT` (`1/0`):
  - `1` → битый/невалидный YAML = fail-fast
  - `0` → warning + deterministic fallback на `RadarRenderPolicy.from_env()`

## Профили (кратко)
- `navigation`: выше anti-clutter, умеренный бюджет.
- `docking`: выше budget, длиннее trails, более детальный режим.
- `combat`: быстрый отклик, ранняя деградация при перегрузе, более консервативное восстановление.

## Адаптация по нагрузке (v1)
- Входы: `EMA(frame_ms)` и `EMA(targets_count)`.
- Рост уровня адаптации: при устойчивом превышении budget/overload.
- Восстановление: при устойчивой недогрузке.
- Против флаппинга: `confirm_frames` + `cooldown_ms`.
- Эффект уровня: уменьшение `effective clutter_targets_max`, ужесточение `lod_label_zoom/lod_detail_zoom`.

## Как проверить (Docker-first)
```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev pytest -q \
  src/qiki/services/q_core_agent/tests/test_radar_policy_loader.py \
  src/qiki/services/q_core_agent/tests/test_radar_semantics_lod_clutter.py \
  src/qiki/services/q_core_agent/tests/test_radar_pipeline.py
```

Пример выбора профиля:
```bash
RADAR_POLICY_PROFILE=combat docker compose -f docker-compose.phase1.yml run --rm qiki-dev pytest -q \
  src/qiki/services/q_core_agent/tests/test_radar_pipeline.py -k profile
```
