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
  - `RadarPipeline` теперь загружает policy через `load_effective_render_policy_result()`.
  - Порядок резолвинга: `YAML defaults < YAML profile < ENV overrides`.
  - Добавлено adaptive-состояние (EMA frame_ms/targets, confirm/cooldown, уровень адаптации).
  - В `RADAR_RENDER_TICK` добавлены поля наблюдаемости policy:
    - `policy_profile`
    - `policy_source` (`yaml|env|default`)
    - `adaptive_level`
    - `effective_frame_budget_ms`
    - `effective_clutter_max`
  - Добавлены policy events в `EventStore`:
    - `POLICY_FALLBACK`
    - `POLICY_PROFILE_CHANGED`
  - Добавлено runtime переключение профиля без рестарта:
    - `policy cycle`
    - `policy set <navigation|docking|combat>`

## ENV knobs
- `RADAR_POLICY_PROFILE` (`navigation|docking|combat`, default `navigation`)
- `RADAR_POLICY_YAML` (путь к yaml; если не задан — встроенный ресурс)
- `RADAR_POLICY_STRICT` (`1/0`):
  - `1` → битый/невалидный YAML = fail-fast
  - `0` → warning + deterministic fallback на `RadarRenderPolicy.from_env()` + событие `POLICY_FALLBACK`

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

## Таблица knobs (контракт)
| Key | Смысл | Default | Profile override | ENV override | Диапазон | Влияние |
|---|---|---:|---|---|---|---|
| `lod_vector_zoom` | Порог включения векторов | `1.2` | да | `RADAR_LOD_VECTOR_ZOOM` | `>=0` | читабельность/деталь |
| `lod_label_zoom` | Порог включения labels | `1.5` | да | `RADAR_LOD_LABEL_ZOOM` | `>=0` | шум/плотность |
| `lod_detail_zoom` | Порог detail режима | `2.0` | да | `RADAR_LOD_DETAIL_ZOOM` | `>=0` | детализация |
| `clutter_targets_max` | Лимит целей до anti-clutter | `30` | да | `RADAR_CLUTTER_TARGETS_MAX` | `>=1` | производительность |
| `frame_budget_ms` | Бюджет кадра | `80.0` | да | `RADAR_FRAME_BUDGET_MS` | `>0` | latency/fps |
| `trail_len` | Длина хвоста | `20` | да | `RADAR_TRAIL_LEN` | `>=1` | контекст движения |
| `bitmap_scales` | Ступени bitmap деградации | `1.0,0.75,0.5,0.35` | да | `RADAR_BITMAP_SCALES` | список `>0` | стабильность рендера |
| `degrade_cooldown_ms` | Cooldown на деградацию | `800` | да | `RADAR_DEGRADE_COOLDOWN_MS` | `>=0` | anti-flapping |
| `recovery_confirm_frames` | Подтверждение восстановления | `6` | да | `RADAR_RECOVERY_CONFIRM_FRAMES` | `>=1` | anti-flapping |
| `degrade_confirm_frames` | Подтверждение деградации | `2` | да | `RADAR_DEGRADE_CONFIRM_FRAMES` | `>=1` | anti-flapping |
| `manual_clutter_lock` | Ручной lock clutter | `false` | да | `RADAR_MANUAL_CLUTTER_LOCK` | bool | операторский контроль |
| `adaptive.ema_alpha_frame_ms` | EMA для frame_ms | `0.35` | нет | нет | `>=0` | адаптация |
| `adaptive.ema_alpha_targets` | EMA для targets | `0.25` | нет | нет | `>=0` | адаптация |
| `adaptive.high_frame_ratio` | Триггер перегруза по frame | `1.2` | нет | нет | `>0` | адаптация |
| `adaptive.low_frame_ratio` | Триггер восстановления по frame | `0.8` | нет | нет | `>=0` | адаптация |
| `adaptive.overload_target_ratio` | Триггер перегруза по целям | `1.15` | нет | нет | `>0` | адаптация |
| `adaptive.underload_target_ratio` | Триггер восстановления по целям | `0.75` | нет | нет | `>=0` | адаптация |
| `adaptive.degrade_confirm_frames` | Confirm на рост adaptive level | `3` | нет | нет | `>=1` | anti-flapping |
| `adaptive.recovery_confirm_frames` | Confirm на снижение adaptive level | `5` | нет | нет | `>=1` | anti-flapping |
| `adaptive.cooldown_ms` | Cooldown adaptive changes | `1200` | нет | нет | `>=0` | anti-flapping |
| `adaptive.max_level` | Максимальный adaptive level | `2` | нет | нет | `>=0` | предел деградации |
| `adaptive.clutter_reduction_per_level` | Уменьшение clutter max на уровень | `0.2` | нет | нет | `>=0` | perf/readability |
| `adaptive.lod_label_zoom_delta_per_level` | Сдвиг label threshold на уровень | `0.2` | нет | нет | `>=0` | anti-clutter |
| `adaptive.lod_detail_zoom_delta_per_level` | Сдвиг detail threshold на уровень | `0.15` | нет | нет | `>=0` | anti-clutter |

Примечание: `SITUATION_*` knobs (confirm/cooldown/lost window/ack) остаются в слое situational awareness и не входят в policy_v3.

## Как проверить (Docker-first)
```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev pytest -q \
  src/qiki/services/q_core_agent/tests/test_radar_policy_loader.py \
  src/qiki/services/q_core_agent/tests/test_radar_semantics_lod_clutter.py \
  src/qiki/services/q_core_agent/tests/test_radar_pipeline.py \
  src/qiki/services/q_core_agent/tests/test_mission_control_terminal_live_real_input.py
```

Пример выбора профиля:
```bash
RADAR_POLICY_PROFILE=combat docker compose -f docker-compose.phase1.yml run --rm qiki-dev pytest -q \
  src/qiki/services/q_core_agent/tests/test_radar_pipeline.py -k profile
```
