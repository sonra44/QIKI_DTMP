# TASK-0024A — Multi-sensor Contract + Ingestion (No Fusion)

## Как было
- Радарный pipeline работал с уже собранным `RadarScene`, без отдельного ingestion-контракта для нескольких независимых источников.
- Не было унифицированного `Observation/SourceTrack` слоя с валидацией полей и явными ingestion-событиями в `EventStore`.

## Как стало
- Добавлен модуль `src/qiki/services/q_core_agent/core/radar_ingestion.py`.
- Введены контракты:
  - `Observation`:
    - `source_id: str`
    - `t: float`
    - `track_key: str`
    - `pos_xy: tuple[float, float]`
    - `vel_xy: tuple[float, float] | None`
    - `quality: float` (нормализация и clamp в `0..1`)
    - `err_radius/covariance` как опциональные поля
  - `SourceTrack`:
    - `source_id`
    - `source_track_id`
    - `last_update_t`
    - `state_pos_xy/state_vel_xy`
    - `quality`
    - `trust`
- Добавлена валидация `Observation`:
  - при отсутствии/битости обязательных полей запись дропается без краша;
  - фиксируется событие `SENSOR_OBSERVATION_DROPPED`.
- Добавлен ingestion API в `RadarPipeline`:
  - `ingest_observations(List[Observation]) -> Dict[source_id, List[SourceTrack]]`
  - `render_observations(...)` для рендера через ingestion-слой.
- Сохранена backward compatibility:
  - старый путь `render_scene(RadarScene)` не изменён и продолжает работать.

## EventStore события ingestion
- `SENSOR_OBSERVATION_RX`:
  - `source_id`, `source_track_id`, `t`, `pos`, `vel`, `quality`, `trust`
- `SOURCE_TRACK_UPDATED`:
  - `source_id`, `source_track_id`, `t`, `pos`, `vel`, `quality`, `trust`
- `SENSOR_OBSERVATION_DROPPED`:
  - `source_id`, `source_track_id`, `t`, `reason`

## Совместимость со старым single-source режимом
- `RadarPipeline.render_scene(RadarScene)` остаётся основным и полностью совместимым.
- Ingestion-слой добавлен как расширение для multi-source, без fusion в этой задаче.
