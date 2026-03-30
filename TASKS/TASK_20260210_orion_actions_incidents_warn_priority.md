# TASK: ORION Actions/Incidents WARN Priority

**ID:** TASK_20260210_ORION_ACTIONS_INCIDENTS_WARN_PRIORITY  
**Status:** done  
**Owner:** codex + user  
**Date created:** 2026-02-10  

## Goal

Убрать неоднозначный startup `Next=monitor`, когда в сводке уже есть WARN-причины в `threats` и/или `energy`.

## Operator Scenario (visible outcome)

- Кто выполняет: оператор ORION.
- Что должно стать визуально/поведенчески понятнее в ORION: в блоке `Actions/Incidents` при WARN сразу виден приоритетный шаг, а не нейтральный `monitor`.
- Ограничение: один цикл = один новый операционный сценарий.

## Reproduction Command

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q \
    tests/unit/test_orion_actions_incidents_priority.py \
    tests/unit/test_orion_summary_action_hints.py \
    tests/unit/test_orion_summary_semantic_causal.py
```

## Before / After

- Before: `Actions/Incidents` мог показывать `Next=monitor`, даже если в `threats/energy` уже есть WARN-causal подсказка.
- After: `Actions/Incidents` выбирает детерминированный WARN-`Next` по приоритету риска (`threats` > `energy`), при этом `crit/fault` пути сохраняют более высокий приоритет.

## Impact Metric

- Метрика: наличие детерминированного actionable `Next` при WARN на startup summary.
- Baseline: возможен `Next=monitor` при одновременных WARN.
- Target: `Next` всегда совпадает с highest-severity WARN cause.
- Actual (после внедрения): покрыто регресс-тестами, целевой срез `6 passed`.

## Scope / Non-goals

- In scope:
  - Логика выбора `Next` для `Actions/Incidents` только в startup summary.
  - Тестовое покрытие приоритетов WARN.
- Out of scope:
  - Переработка остальных блоков summary.
  - Изменения в `crit`/fault логике за пределами текущего правила приоритета.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `TASKS/TASK_20260210_orion_telemetry_semantic_panels_tierA.md`
  - `TASKS/ARTIFACT_20260210_orion_summary_weekly_before_after.md`
  - `src/qiki/services/operator_console/main_orion.py`

## Plan (steps)

1) Зафиксировать детерминированный приоритет WARN в `actions_incidents`: `threats` > `energy`.
2) Добавить регресс-тесты на одновременный WARN и energy-only WARN.
3) Прогнать docker-first pytest slice и приложить evidence.

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Операционный сценарий воспроизводится по команде из `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [x] Repo clean (`git status --porcelain` is expected)

## Evidence (commands -> output)

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_actions_incidents_priority.py tests/unit/test_orion_summary_action_hints.py tests/unit/test_orion_summary_semantic_causal.py`
  - Output: `6 passed`.
- `bash scripts/quality_gate_docker.sh`
  - Output: `[quality-gate] OK`.
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest tests/unit/test_orion_actions_incidents_priority.py tests/unit/test_orion_summary_action_hints.py tests/unit/test_orion_summary_semantic_causal.py tests/unit/test_orion_summary_compact_noise.py tests/unit/test_orion_summary_uses_canonical_soc.py tests/unit/test_orion_power_compact.py tests/unit/test_orion_system_panels_compact.py`
  - Output: `19 passed in 1.12s`.

## Notes / Risks

- Риск: чрезмерно агрессивный приоритет может скрыть энергетические подсказки при одновременных WARN.
- Митигатор: приоритет ограничен только `Actions/Incidents`; causal-поля в `energy` и `threats` сохраняются без изменения.

## Next

1) При необходимости расширять приоритет только в рамках startup summary, не перенося эту логику на остальные экраны без отдельного task-dossier.
