# TASK: G2 — тепловое или энергетическое ограничение после боевого действия

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G2_QIKI_COMBAT_SYSTEM_CONSEQUENCE_CANON.md`

Уже доказано:
- hostile burst оставляет отдельный combat event;
- hostile burst оставляет отдельную propulsion-цену;
- hostile follow-up меняется по текущему RCS ресурсу.

Пока не доказано:
- что hostile/combat action оставляет вторую системную цену в `thermal` или `power`.

## Цель

Реализовать первый законченный контур второго системного ограничения, где:
- hostile/combat action уже имеет propulsion-cost;
- добавляется тепловой или энергетический след;
- QIKI учитывает его в следующем hostile follow-up.

## Выполнено

1. Выбран `power` как минимальный и честный truth-source второго системного ограничения.
2. В hostile path добавлен power-gate по `pdu_overcurrent`.
3. Собраны unit и runtime proof.

## Evidence

- builder: `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- unit: `tests/unit/test_qiki_orion_intents_service.py`
- runtime proof:
  - `tools/orion_v_qiki_hostile_power_gate_smoke.py`
  - `scripts/prove_orion_v_qiki_hostile_power_gate.sh`
