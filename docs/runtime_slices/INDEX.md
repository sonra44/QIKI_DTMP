# QIKI Runtime Slices — Index

## 0. Назначение

Этот индекс фиксирует статус runtime-slice документов QIKI после обнаружения фактического `body_structure / module attach lifecycle` runtime seed в репозитории.

Он закрывает status drift: в `docs/runtime_slices/` исторически был только `SLICE_0001_PLAN.md`, но фактический код и тесты уже покрывают narrow attach lifecycle 0001-0008.

Главная формула:

`Documentation package != full runtime implementation.`

`Attach lifecycle seed 0001-0008 == implemented / unit-verified narrow runtime contour.`

`Full QIKI Body runtime compliance == not claimed.`

---

## 1. Status map

| Slice | Document | Current status | Scope |
|---|---|---|---|
| 0001 | `SLICE_0001_PLAN.md` | historical plan; implemented / unit-verified in current code | missing passport rejection |
| 0002 | `SLICE_0002_PLAN.md` | implemented / unit-verified | ORION Evidence Card for attach rejection |
| 0003 | `SLICE_0003_PLAN.md` | implemented / unit-verified | valid passport registration / occupancy |
| 0004 | `SLICE_0004_PLAN.md` | implemented / unit-verified | occupied mount rejection |
| 0005 | `SLICE_0005_PLAN.md` | implemented / unit-verified | forbidden mount-class rejection |
| 0006 | `SLICE_0006_PLAN.md` | implemented / unit-verified | invalid passport rejection |
| 0007 | `SLICE_0007_PLAN.md` | implemented / unit-verified | unknown mount rejection |
| 0008 | `SLICE_0008_PLAN.md` | implemented / unit-verified | ordered attach validation pipeline |

Detailed evidence:

`ATTACH_LIFECYCLE_EVIDENCE.md`

---

## 2. Runtime owner

Runtime owner:

`src/qiki/services/q_core_agent/core/body_structure.py`

Current lifecycle entrypoint:

`run_attach_pipeline()`

Legacy Slice 0001 helper:

`attach_module()`

Operator evidence projection:

`src/qiki/services/operator_console/orion_v/body_structure_evidence.py`

`src/qiki/services/operator_console/orion_v/evidence_card.py`

`src/qiki/services/operator_console/orion_v/evidence_card_mapping.py`

---

## 3. Guardrails

Do not infer full QIKI Body runtime compliance from these slices.

Do not infer final Face Map geometry from test fixtures.

Do not infer module capability activation from successful registration.

Do not use `attach_module()` as the current full lifecycle API without an explicit later decision. The machine-checkable current entrypoint is `CURRENT_ATTACH_LIFECYCLE_ENTRYPOINT == "run_attach_pipeline"`.

Do not read `EvidenceCard.status == "implemented"` as module runtime readiness. It only means the audit-backed evidence projection is implemented / complete.

Do not let ORION Evidence Card become a source of physical truth.
