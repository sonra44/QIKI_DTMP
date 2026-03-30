# TASK: G2 — тактический сдвиг после combat-entry и новые опции

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G2_QIKI_COMBAT_RESOURCE_GATE_CANON.md`

Уже доказано:
- hostile loop проходит через protocol -> context -> prepared entry -> resource gate.

Пока не доказано:
- что подтверждённый combat-entry меняет тактическое состояние и дальнейшие опции.

## Цель

Реализовать первый законченный hostile follow-up scenario, где:
- combat-entry уже подтверждён;
- ORION V показывает новый тактический контекст;
- QIKI меняет следующий допустимый шаг детерминированно.

## Следующее действие

1. Зафиксировать acceptance этого этапа в отдельном артефакте.
2. Синхронизировать внешний canonical board и bootstrap.
3. Сделать replan следующего G2-этапа после tactical-state shift.

## Журнал доказательств

### Петля 1: tactical state shift через активный intercept pulse

Изменённые файлы:
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `tests/unit/test_qiki_orion_intents_service.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tools/orion_v_qiki_tactical_state_shift_smoke.py`
- `scripts/prove_orion_v_qiki_tactical_state_shift.sh`

Результат:
- после первого combat-entry hostile follow-up больше не подготавливает тот же burst повторно;
- если `propulsion.rcs` уже показывает активный intercept pulse, тот же hostile запрос уходит в `TACTICAL_STATE_INTERCEPT_ACTIVE`;
- ORION V показывает новый next step: удерживать трек и переоценить ситуацию после завершения текущего импульса.

Доказательства:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/q_core_agent/qiki_orion_intents_service.py tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_cockpit.py tools/orion_v_qiki_tactical_state_shift_smoke.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_cockpit.py`
- `bash scripts/prove_orion_v_qiki_tactical_state_shift.sh`
