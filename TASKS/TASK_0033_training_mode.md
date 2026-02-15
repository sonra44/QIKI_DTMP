# TASK-0033 — Training Mode v1 (Operator Training on Real Pipeline)

## Что было
- Терминал и радар работали в production/live/replay режимах, но не было встроенного учебного режима с детерминированными сценариями и оценкой действий оператора.
- Не было единого контракта событий `TRAINING_*` для сценария, действий и итогового результата.

## Что сделано
- Добавлен детерминированный сценарный модуль: `src/qiki/services/q_core_agent/core/training_scenarios.py`.
- Добавлен scoring/evaluation модуль: `src/qiki/services/q_core_agent/core/training_evaluator.py`.
- Добавлен runtime training session:
  - `TrainingActionRecorder`
  - `TrainingSessionRunner`
  - `evaluate_training_trace`
  в `src/qiki/services/q_core_agent/core/training_mode.py`.
- Добавлен профиль плагинов `training` в `src/qiki/resources/plugins.yaml`.
- Добавлена интеграция в MissionControlTerminal:
  - `QIKI_MODE=training` включает training defaults (`QIKI_PLUGINS_PROFILE=training`, sqlite EventStore default, raw observation RX off).
  - Новые команды: `training list`, `training run <scenario>`.
  - CLI: `--training-scenario`, `--training-seed`.
  - Action tracking для hotkeys/mouse/policy через `TRAINING_ACTION`.
- HUD расширен training-слоем (scenario/objective/timer/status/score) в `src/qiki/services/q_core_agent/core/terminal_radar_renderer.py`.

## Сценарии v1
- `cpa_warning`
- `sensor_dropout`
- `fusion_conflict`
- `policy_degradation`

## Контракт событий training
- `TRAINING_STATUS`
- `TRAINING_CHECKPOINT`
- `TRAINING_ACTION`
- `TRAINING_RESULT`

Все события пишутся в EventStore и участвуют в replay/forensics.

## Determinism
- Сценарии фиксированы по `seed` и кадрам.
- `TrainingSessionRunner` работает без `sleep`.
- Golden-подход: повторная оценка из trace (replay path) даёт тот же score/verdict.

## ENV / запуск
- `QIKI_MODE=training`
- `QIKI_PLUGINS_PROFILE=training` (выставляется автоматически в training mode, если не задан)
- `python -m qiki.services.q_core_agent.core.mission_control_terminal --training-scenario cpa_warning --training-seed 7`

## Ограничения v1
- Оценка действий построена на action checkpoints и базовой метрике reaction-time (без ML/доктрины).
- Multi-console в training по умолчанию не используется.
