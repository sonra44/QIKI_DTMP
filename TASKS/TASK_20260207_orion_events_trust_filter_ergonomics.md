# TASK: ORION Events trust filter ergonomics

**ID:** TASK_20260207_orion_events_trust_filter_ergonomics
**Status:** done
**Owner:** Codex
**Date created:** 2026-02-07

## Goal

Сделать операторский trust-фильтр в Events детерминированным и удобным для использования без изменения протоколов.

## Scope / Non-goals

- In scope:
  - Исправить фильтрацию `trusted/untrusted` без коллизии подстрок.
  - Добавить alias-команду `trust trusted|untrusted|off`.
  - Добавить unit tests и доказать Docker-проверками.
  - Обновить help/документацию команд.
- Out of scope:
  - Любые изменения NATS subject contract.
  - Любые изменения incident schema/потока событий.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `src/qiki/services/operator_console/main_orion.py`
  - `tests/unit/test_orion_control_provenance.py`
  - `docs/design/operator_console/ORION_OS_SYSTEM.md`

## Plan (steps)

1) Подтвердить pain point и текущую реализацию фильтров в `OrionApp._events_filtered_sorted`.
2) Исправить trust-матчинг на точное сравнение для `trusted/untrusted`.
3) Добавить alias-команду `trust ...` в `_run_command`.
4) Добавить default routing для `trust` без `S:` в `_should_route_to_system_by_default`.
5) Добавить unit tests на фильтрацию, parsing path и routing без префикса.
6) Прогнать Docker-проверки и quality gate.
7) Синхронизировать help и docs.

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (behavior changed)
- [ ] Repo clean (`git status --porcelain` is expected)

## Evidence (commands -> output)

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_control_provenance.py`
  - `....... [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_control_provenance.py tests/unit/test_orion_summary_events_filters_off.py src/qiki/services/operator_console/tests/test_command_routing.py`
  - `.............. [100%]`
- `bash scripts/quality_gate_docker.sh`
  - `[quality-gate] OK`
- `QUALITY_GATE_PROFILE=full QUALITY_GATE_RUFF_FORMAT_CHECK=0 bash scripts/quality_gate_docker.sh`
  - `[quality-gate] OK` (integration: `15 passed, 7 skipped`; mypy remained disabled by env in this run)
- `QUALITY_GATE_RUN_MYPY=1 QUALITY_GATE_RUN_INTEGRATION=0 QUALITY_GATE_RUFF_FORMAT_CHECK=0 bash scripts/quality_gate_docker.sh`
  - `mypy: Found 198 errors in 19 files (baseline project debt; outside this trust-filter slice)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY' ...` (headless trust-filter smoke via `_run_command` + summary/diagnostics capture)
  - `SMOKE_EN_SUMMARY_TRUST= untrusted`
  - `SMOKE_EN_DIAG_TRUST= untrusted`
  - `SMOKE_RU_SUMMARY_TRUST= trusted`
  - `SMOKE_RU_DIAG_TRUST= trusted`
  - `OK`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY' ...` (runtime smoke for status aliases)
  - `SMOKE_TRUST_STATUS_EN= Events trust filter/Фильтр событий по доверию: untrusted`
  - `SMOKE_TRUST_STATUS_RU= Events trust filter/Фильтр событий по доверию: trusted`
  - `SMOKE_SUMMARY_TRUST= trusted`
  - `OK`

## Notes / Risks

- Риск ложноположительного матчинга устранен: `trusted` больше не захватывает `untrusted`.
- Реализация `trust ...` намеренно переиспользует существующий events text filter (без дублирования состояния).
- Routing риск устранен: `trust ...` теперь обрабатывается как system-команда и без `S:`.
- Discoverability улучшена: `trust <trusted|untrusted|off>` добавлен в placeholder-подсказки для `narrow/normal/wide`.
- Отдельный command provider/palette provider в ORION не найден; канон discoverability сейчас = routing + help + placeholder + unit tests.
- Добавлен русскоязычный алиас `доверие` (routing + handler + help/placeholder + tests).
- Добавлены русские значения trust-токенов: `доверенный/недоверенный/выкл` (с нормализацией в trust-маркер).
- Добавлен явный normalized trust-state в snapshot/summary/diagnostics: `events_filter_trust` (`trusted|untrusted|off`).
- Добавлены read-only команды статуса trust-фильтра: `trust status` / `доверие статус` (`info/инфо`), выводящие каноническое состояние `trusted|untrusted|off` без мутации фильтра.

## Next

1) Если в будущем появится отдельный command provider, добавить туда `trust` и отдельный unit-тест provider-вывода.
