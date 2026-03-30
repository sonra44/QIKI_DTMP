# TASK: G2 — связь как ограничение hostile follow-up

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G2_QIKI_THERMAL_CONSTRAINT_FOLLOWUP_CANON.md`

Уже доказано:
- hostile burst оставляет propulsion-cost;
- hostile follow-up меняется по power;
- hostile follow-up меняется по thermal.

Пока не доказано:
- отдельное `comms`-ограничение в том же hostile/combat loop.

## Цель

Реализовать первый законченный hostile-контур, где:
- hostile follow-up зависит от `comms/target-link`;
- ORION V показывает это через `F2/Comms`;
- QIKI меняет hostile follow-up по этому ограничению.

## Следующее действие

1. Выбрать минимальный `comms` truth-source для hostile follow-up.
2. Закрепить `comms`-gate в hostile builder без нового store.
3. Довести до Docker-proof и runtime-proof.
