# TASK-0024B — Multi-sensor fusion v1 (association + majority vote)

## Что сделано
- Добавлен модуль `src/qiki/services/q_core_agent/core/radar_fusion.py`.
- Введены контракты:
  - `FusionConfig` (ENV knobs),
  - `Contributor`,
  - `FusionCluster`,
  - `FusedTrack`,
  - `FusedTrackSet`,
  - `FusionStateStore` (anti-flapping state).
- Реализован детерминированный greedy association:
  - сортировка кандидатов по `trust desc`, затем `source_id`, `source_track_id`,
  - gating по `dist(pos)<=gate_dist` и `dist(vel)<=gate_vel` (если vel есть у обоих),
  - максимум один трек на источник в кластере.
- Реализован majority/fusion:
  - `support_ok` при `contributors >= RADAR_FUSION_MIN_SUPPORT`,
  - weighted-average по pos/vel,
  - trust бонус за support и штраф за конфликт (`CONFLICT`),
  - `LOW_SUPPORT` + cap `trust<=0.49` при недоборе поддержки.
- Реализован anti-flapping:
  - confirm frames для новых ассоциаций,
  - cooldown на повторное создание после распада,
  - попытка удержания `fused_id` при похожих кластерах (overlap/dist).
- Интеграция в `RadarPipeline.render_observations()`:
  - `RADAR_FUSION_ENABLED=1` включает путь fusion,
  - при `0` сохраняется старый путь `source_tracks_to_scene`.
- EventStore интеграция:
  - `FUSION_CLUSTER_BUILT`,
  - `FUSED_TRACK_UPDATED`,
  - дедуп по сигнатурам (без спама каждый кадр).

## ENV knobs
- `RADAR_FUSION_ENABLED` (default `0`)
- `RADAR_FUSION_GATE_DIST_M` (default `50.0`)
- `RADAR_FUSION_GATE_VEL_MPS` (default `20.0`)
- `RADAR_FUSION_MIN_SUPPORT` (default `2`)
- `RADAR_FUSION_MAX_AGE_S` (default `2.0`)
- `RADAR_FUSION_CONFLICT_DIST_M` (default `2 * gate_dist`)
- `RADAR_FUSION_CONFIRM_FRAMES` (default `3`)
- `RADAR_FUSION_COOLDOWN_S` (default `2.0`)

## Алгоритм v1 (ограничения)
- Association greedy и локальный (без глобального оптимума).
- Конфликты решаются флагом/штрафом trust, а не сложным multi-hypothesis.
- v1 ориентирован на детерминизм replay и anti-flapping, а не на максимальную точность fusion.

## Как включить/выключить
- Выключено по умолчанию: `RADAR_FUSION_ENABLED=0`.
- Включение:
  - `RADAR_FUSION_ENABLED=1`
  - при необходимости задать gating/confirm/cooldown через ENV.
