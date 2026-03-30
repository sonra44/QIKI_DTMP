# Промежуточный критический аудит (QIKI_DTMP)

Дата: 2026-03-01
Формат: intermediate gate (критический взгляд)
Статус: FAIL (есть блокирующее несоответствие quality gate)

## Scope
- Протокол "ПРОЧТИ ЭТО" + operative core: выполнены.
- Память: загружена (`load_context`) + recall по `STATUS/TODO_NEXT/DECISIONS/TASKS/DEV_METHODS`.
- Drift guard: `scripts/check_no_second_task_board.sh`.
- Runtime smoke (Docker): ORION V safe-mode + ORION operator-console smoke.
- Тестовый слайс ORION V (unit).
- Full quality gate (Docker).

## Findings (по критичности)

1. `BLOCKER` — Quality gate красный (Ruff E501)
- Where: `src/qiki/services/operator_console/orion_v/app.py:1018`
- Evidence: `bash scripts/quality_gate_docker.sh` -> `exit code 1`, `E501 Line too long (123 > 120)`.
- Risk: нельзя считать срез "готовым к пушу"; дальнейшая работа поверх красного гейта накапливает техдолг и маскирует реальные регрессии.
- Fix: разбить длинную строку в `_parse_safe_mode_event` и повторить `bash scripts/quality_gate_docker.sh`.

2. `HIGH` — Семантический drift по `N/A` в runtime-UI
- Where:
  - `src/qiki/services/operator_console/orion_v/modules/power.py:42,63,64`
  - `src/qiki/services/operator_console/orion_v/modules/thermal.py:33,51,52,53`
  - `src/qiki/services/operator_console/orion_v/modules/docking.py:35,51,52,53,54,55`
- Evidence: код модулей рендерит `N/A` как обычное отсутствие поля.
- Canon conflict: lock фиксирует `N/A` только для dev/contract error; штатный runtime должен быть `healthy|degraded|failed|off` + reason.
- Risk: оператор получает неоднозначный статус (неясно: это ошибка контракта или штатная недоступность в игровой логике).
- Fix: унифицировать вывод через семантические состояния + reason, оставить `N/A` только в ветках явной contract/dev ошибки.

3. `MEDIUM` — Канон-путь `docs/Архив/**` указан, но каталог отсутствует физически
- Where: `docs/design/canon/INDEX.md` (раздел non-canon/reference)
- Evidence: `find docs -maxdepth 2 -type d` не содержит `docs/Архив`.
- Risk: путаница в онбординге (правило есть, директории нет).
- Fix: либо создать marker-dir/README, либо скорректировать формулировку в каноне на фактическую структуру (`analysis/`, `task_plans/`, historical markers).

## Что уже подтверждено как рабочее (PASS)
- Drift guard: `OK: all suspect task-board-like files are marked as reference-only`.
- ORION container health: `operator-console ... healthy`.
- Safe-mode smoke: `OK: orion_v_safe_mode_smoke`.
- ORION operator smoke: `OK: orion operator-console smoke`.
- ORION V unit slice: `............................ [100%]`.
- Silent exception debt check: `rg "except Exception:\s*pass" src tests` -> нет совпадений.

## Gate decision
- Сейчас: `FAIL` (из-за блокера quality gate).
- Рекомендуемый следующий шаг: сначала быстрый фикс Ruff в `app.py`, затем повтор quality gate. После green — либо продолжаем feature-loop, либо закрываем drift из пункта 2 как отдельный task.

## Continuation delta (same date)

1. `BLOCKER` from finding #1 resolved
- Fix applied in [app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py:1018) by wrapping long expression.
- Re-check: `bash scripts/quality_gate_docker.sh` -> `exit 0`, `Ruff: All checks passed`, final `[quality-gate] OK`.

2. `HIGH` semantic drift from finding #2 remediated in ORION V modules
- Updated runtime fallback from `N/A` to semantic `degraded: нет данных` in:
  - `src/qiki/services/operator_console/orion_v/modules/power.py`
  - `src/qiki/services/operator_console/orion_v/modules/thermal.py`
  - `src/qiki/services/operator_console/orion_v/modules/docking.py`
- Updated unit expectation in `tests/unit/test_orion_v_subsystem_modules.py`.
- Target slice check:
  - `pytest -q tests/unit/test_orion_v_subsystem_modules.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_systems_uses_hardware_model.py` -> `[100%]`.

Gate after remediation: `PASS`.

3. `MEDIUM` doc mismatch from finding #3 resolved
- Updated canon wording in `docs/design/canon/INDEX.md`:
  - now treats historical/archive docs as reference-only *when present*.
  - avoids hard dependency on physical `docs/Архив/` directory.
