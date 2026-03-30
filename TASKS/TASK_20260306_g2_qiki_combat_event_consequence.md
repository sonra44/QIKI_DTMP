# TASK: G2 — боевое событие и последствие после hostile-решения

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G2_QIKI_TACTICAL_STATE_SHIFT_CANON.md`

Уже доказано:
- hostile loop меняет tactical state и next step.

Пока не доказано:
- что hostile/combat consequence существует как отдельный наблюдаемый боевой факт.

## Цель

Реализовать первый боевой event/consequence contour, где:
- после hostile шага возникает отдельный сигнал последствия;
- ORION V показывает его как факт мира;
- QIKI reply и event не расходятся.

## Следующее действие

1. Зафиксировать acceptance этого этапа в отдельном артефакте.
2. Синхронизировать внешний canonical board и bootstrap.
3. Сделать replan следующего G2-этапа после visible combat consequence.

## Журнал доказательств

### Петля 1: отдельный combat consequence event после hostile combat-entry

Изменённые файлы:
- `src/qiki/shared/nats_subjects.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `tools/orion_v_qiki_combat_entry_smoke.py`

Результат:
- после подтверждения `hostile_rcs_intercept_burst` ORION V публикует отдельный event `qiki.events.v1.operator.combat`;
- event несёт `event_type=COMBAT_ENTRY_CONFIRMED` и `reason_code=COMBAT_EVENT_INTERCEPT_BURST_CONFIRMED`;
- `F3` показывает его как отдельный факт через общий event-store;
- hostile consequence больше не живёт только как текст в блоке `QIKI`.

Доказательства:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/shared/nats_subjects.py src/qiki/services/operator_console/orion_v/app.py tests/unit/test_orion_v_qiki_loop.py tools/orion_v_qiki_combat_entry_smoke.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_qiki_loop.py`
- `bash scripts/prove_orion_v_qiki_combat_entry.sh`
