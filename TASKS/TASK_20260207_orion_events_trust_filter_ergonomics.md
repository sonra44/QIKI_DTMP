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
- `bash scripts/quality_gate_docker.sh`
  - `[quality-gate] OK`

## Notes / Risks

- Риск ложноположительного матчинга устранен: `trusted` больше не захватывает `untrusted`.
- Реализация `trust ...` намеренно переиспользует существующий events text filter (без дублирования состояния).
- Routing риск устранен: `trust ...` теперь обрабатывается как system-команда и без `S:`.
- Discoverability улучшена: `trust <trusted|untrusted|off>` добавлен в placeholder-подсказки для `narrow/normal/wide`.
- Отдельный command provider/palette provider в ORION не найден; канон discoverability сейчас = routing + help + placeholder + unit tests.
- Добавлен русскоязычный алиас `доверие` (routing + handler + help/placeholder + tests).
- Добавлены русские значения trust-токенов: `доверенный/недоверенный/выкл` (с нормализацией в trust-маркер).
- Добавлен явный normalized trust-state в snapshot/summary/diagnostics: `events_filter_trust` (`trusted|untrusted|off`).

## Next

1) Если в будущем появится отдельный command provider, добавить туда `trust` и отдельный unit-тест provider-вывода.
