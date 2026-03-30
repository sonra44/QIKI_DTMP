# TASK-0019 — Radar Readability v1

## Как было
- Рендер зависел в основном от backend-логики и глобального `overlays_enabled`.
- На high-density сценах не было единой детерминированной политики LOD/clutter.
- Детали цели смешивались со сценой; не было выделенного инспектора с режимом pin.
- Trails/labels/vectors не управлялись как единая семантика видимости.

## Как стало
- Добавлен backend-agnostic слой политики: `core/radar_render_policy.py`.
- Добавлен `RadarRenderPlan` + `RadarRenderStats`:
  - LOD0..LOD3 по zoom.
  - Anti-clutter по `targets_count` и `frame_time_ms`.
  - Детерминированное отключение overlays: labels -> trails -> vectors.
- Добавлен `RadarTrailStore` (`core/radar_trail_store.py`) с лимитом истории на track.
- Pipeline теперь: `scene -> render policy -> render plan -> backend`.
- HUD расширен:
  - `CLUTTER: ON/OFF` + reason.
  - `OVR: ...` + dropped overlays.
  - Inspector-блок (off/on/pinned).

## LOD (дефолт)
- `LOD0` (`zoom < 1.2`): только базовая геометрия (без labels/vectors/trails).
- `LOD1` (`1.2 <= zoom < 1.5`): vectors можно, labels скрыты.
- `LOD2` (`1.5 <= zoom < 2.0`): labels можно (если нет clutter).
- `LOD3` (`zoom >= 2.0`): максимум деталей в рамках v1.

## Anti-Clutter (дефолт)
- Trigger:
  - `RADAR_CLUTTER_TARGETS_MAX=30`
  - `RADAR_FRAME_BUDGET_MS=80`
- Action:
  - выключает labels/trails/vectors по приоритету,
  - для bitmap снижает `bitmap_scale`.

## Overlays/Hotkeys
- `g` grid
- `b` range rings
- `v` vectors
- `t` trails
- `l` labels
- `o` global overlays on/off
- `i` inspector cycle: `off -> on -> pinned -> off`
- `r` reset view + overlays + inspector

## Inspector behavior
- `off`: скрыт.
- `on`: показывает выбранную цель.
- `pinned`: удерживает закреплённый `target_id`, даже если текущий selection поменялся.

## Env knobs
- `RADAR_LOD_LABEL_ZOOM=1.5`
- `RADAR_LOD_VECTOR_ZOOM=1.2`
- `RADAR_LOD_DETAIL_ZOOM=2.0`
- `RADAR_CLUTTER_TARGETS_MAX=30`
- `RADAR_FRAME_BUDGET_MS=80`
- `RADAR_TRAIL_LEN=20`
- `RADAR_BITMAP_SCALE=1.0`

## UX example
- `zoom=1.0`: точки + базовая сетка/кольца, без подписи и векторов.
- `zoom=1.3`: появляются vectors (если overlay включён).
- `zoom=1.7`: labels на сцене (если нет clutter).
- `zoom=2.2`: максимум деталей, но при перегрузе auto-clutter возвращает читаемость.
