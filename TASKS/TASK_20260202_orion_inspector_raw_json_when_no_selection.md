# TASK: ORION Inspector — показывать Raw JSON телеметрии при отсутствии выбора

Date: 2026-02-02
Status: done

## Goal

Убрать **вводящее в заблуждение** `N/A/—` в Inspector → `Raw data (JSON)/Сырые данные (JSON)` в ситуации, когда:

- ORION уже получает `qiki.telemetry` (есть “последний снапшот”), но
- у оператора **нет активного selection** на текущем экране.

Политика no-mocks соблюдается: показываем только реально полученную телеметрию. Если телеметрии ещё нет — остаётся честное `N/A/—`.

## Non-goals / Invariants

- No mocks / no demo values.
- No new subjects / no `v2` протоколов: меняем только UI-рендеринг и тесты.
- Docker-first: доказательства через docker pytest / quality gate.

## Changes

1) ORION Inspector:
   - Когда `ctx is None`, `Raw data (JSON)` берётся из последнего telemetry snapshot (`_snapshots.get_last("telemetry")`).
   - Иначе — как раньше (preview выбранного объекта).

2) Unit test:
   - Новый unit тест доказывает, что при отсутствии selection Inspector рендерит `schema_version` и `source` из telemetry payload.
   - Тест использует fake-inspector + `rich.Console(record=True)` (без необходимости реального Textual UI).

3) Test robustness:
   - `tests/unit/test_orion_hydrate_system_mode_from_jetstream.py` теперь `importorskip("textual")`, чтобы локальный прогон без Textual был fail-soft.

## Evidence (Docker)

Unit:
- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml exec -T qiki-dev pytest -q tests/unit/test_orion_inspector_raw_preview.py`

Quality gate:
- `QUALITY_GATE_PROFILE=full bash scripts/quality_gate_docker.sh`

## Done when

- В default Phase1+ORION стекe Inspector больше не показывает `N/A/—` в `Raw data (JSON)` просто потому что “не выбрано” — при наличии telemetry он показывает реальный JSON preview.
- Docker quality gate зелёный.
- Изменения закоммичены и запушены так, чтобы `origin/main == origin/master`.

## Result

- Commit: `a0e61e9` (pushed to `main` and `master`)
