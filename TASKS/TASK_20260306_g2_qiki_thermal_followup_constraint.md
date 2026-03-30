# TASK: G2 — тепловое follow-up ограничение после боевого шага

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G2_QIKI_THERMAL_OR_POWER_CONSTRAINT_CANON.md`

Уже доказано:
- hostile burst оставляет propulsion-cost;
- hostile burst оставляет power-cost;
- hostile follow-up меняется по RCS resource и power `pdu_overcurrent`.

Пока не доказано:
- отдельное thermal follow-up ограничение на том же hostile loop.

## Цель

Реализовать первый законченный hostile-контур, где:
- hostile/combat action оставляет thermal след;
- ORION V показывает его через `F2/Thermal`;
- QIKI меняет hostile follow-up по этому thermal состоянию.

## Выполнено

1. Выбран minimal thermal truth-source: `thermal.nodes[*].warned/tripped`.
2. В hostile builder добавлен thermal-gate с `COMBAT_ENTRY_THERMAL_WARN` и `COMBAT_ENTRY_THERMAL_TRIP`.
3. Собраны unit и runtime proof через `F2/Thermal`.

## Evidence

- builder: `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- unit: `tests/unit/test_qiki_orion_intents_service.py`
- runtime proof:
  - `tools/orion_v_qiki_thermal_followup_constraint_smoke.py`
  - `scripts/prove_orion_v_qiki_thermal_followup_constraint.sh`
