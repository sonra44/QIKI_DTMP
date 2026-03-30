# ACCEPTANCE: G2-QIKI-006 — Combat Event + Consequence Visibility

Статус: PASS
Дата: 2026-03-06
Ответственные: user + codex

## Что доказывали

После hostile/combat шага последствие должно существовать не только как текст QIKI, но и как отдельный боевой event/fact, который ORION V показывает через обычный event-store.

## Что изменено

- `src/qiki/shared/nats_subjects.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `tools/orion_v_qiki_combat_entry_smoke.py`

## Truth-source

- подтверждённый hostile combat-entry через `hostile_rcs_intercept_burst`;
- телеметрическое подтверждение через `propulsion.rcs.command_pct/time_left_s`;
- отдельный event публикуется только после подтверждённого эффекта.

## Проверки

1. Ruff:
   - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/shared/nats_subjects.py src/qiki/services/operator_console/orion_v/app.py tests/unit/test_orion_v_qiki_loop.py tools/orion_v_qiki_combat_entry_smoke.py`
2. Unit:
   - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_qiki_loop.py`
3. Runtime:
   - `bash scripts/prove_orion_v_qiki_combat_entry.sh`

## Фактический результат

- отдельный event-subject: `qiki.events.v1.operator.combat`
- `event_type=COMBAT_ENTRY_CONFIRMED`
- `reason_code=COMBAT_EVENT_INTERCEPT_BURST_CONFIRMED`
- `F3` показывает этот event как отдельный факт мира

## Вывод

Этап `G2-QIKI-006` закрыт честно:
- event есть как отдельный факт;
- ORION V показывает его отдельно от текстового ответа QIKI;
- Docker-proof и runtime-proof зелёные.
