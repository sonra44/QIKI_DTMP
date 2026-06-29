# QIKI Runtime Slices — Attach Lifecycle Evidence Status

## 0. Назначение

Этот документ фиксирует фактический статус узкого runtime-контура `body_structure / module attach lifecycle` в текущем repo snapshot.

Он не расширяет QIKI Body v0.2.2 и не объявляет полную runtime-совместимость. Его задача — закрыть status drift между документационным пакетом, папкой `docs/runtime_slices/` и фактическим кодом.

Главная формула:

`QIKI Body documentation package: present.`

`Attach lifecycle runtime seed: implemented / unit-verified.`

`Full QIKI Body runtime compliance: not claimed.`

---

## 1. Status summary

Scope:

`body_structure / module attach lifecycle / ORION evidence projection`

Status:

`implemented / unit-verified narrow runtime seed`

Runtime conformance:

`partial; attach lifecycle only`

Full QIKI Body v0.2.2 conformance:

`not claimed`

Targeted test status in this environment:

`84 selected test items passing`

Full pytest status in this environment:

`not established`

Reason:

full-suite collection in the current sandbox is blocked by environment dependencies outside this patch scope, including packages / modules such as `nats`, `textual`, `generated`, `interfaces` and `ship_core`.

---

## 2. Runtime source files

Runtime / policy owner:

`src/qiki/services/q_core_agent/core/body_structure.py`

ORION evidence projection files:

`src/qiki/services/operator_console/orion_v/body_structure_evidence.py`

`src/qiki/services/operator_console/orion_v/evidence_card.py`

`src/qiki/services/operator_console/orion_v/evidence_card_mapping.py`

Related ORION evidence tests also exercise:

`src/qiki/services/operator_console/orion_v/evidence_card_vm.py`

---

## 3. Implemented attach lifecycle seed

The current runtime seed covers the following outcomes:

| Slice | Runtime status | Core outcome | Stable reason / status |
|---|---|---|---|
| 0001 | implemented / unit-verified | passport missing / shape missing rejection | `MODULE_PASSPORT_MISSING` |
| 0002 | implemented / unit-verified | audit-backed rejection surfaced as read-only Evidence Card | `BODY_MODULE_ATTACH_REJECTION` |
| 0003 | implemented / unit-verified | valid minimal passport registers module occupancy | `attached`, `passport_status=validated` |
| 0004 | implemented / unit-verified | duplicate attach to occupied mount rejected | `MOUNT_POINT_OCCUPIED` |
| 0005 | implemented / unit-verified | forbidden class on mount rejected | `MODULE_MOUNT_CLASS_FORBIDDEN` |
| 0006 | implemented / unit-verified | present but structurally invalid passport rejected | `MODULE_PASSPORT_INVALID` |
| 0007 | implemented / unit-verified | valid passport with unknown mount rejected | `MOUNT_POINT_UNKNOWN` |
| 0008 | implemented / unit-verified | ordered attach validation pipeline | `AttachDecision` / audit / evidence |

---

## 4. Validation order

The canonical runtime order for the current attach lifecycle seed is:

```text
1. passport missing / shape missing
   -> MODULE_PASSPORT_MISSING

2. passport present but structurally invalid
   -> MODULE_PASSPORT_INVALID

3. passport valid but mount unknown
   -> MOUNT_POINT_UNKNOWN

4. mount known but occupied
   -> MOUNT_POINT_OCCUPIED

5. mount known and free but module class forbidden
   -> MODULE_MOUNT_CLASS_FORBIDDEN

6. mount known, free, compatible, valid passport
   -> attached / registered
```

Later checks must not overwrite earlier reason codes.

Example:

`passport invalid + occupied mount -> MODULE_PASSPORT_INVALID`, not `MOUNT_POINT_OCCUPIED`.

---

## 5. Entry points

### 5.1. Legacy entrypoint

`attach_module()` is a legacy Slice 0001 helper.

It owns only the original negative path:

`passport missing / shape missing -> MODULE_PASSPORT_MISSING -> audit`.

For a shaped passport it can still return `MODULE_ATTACH_NOT_IMPLEMENTED`.

Do not use `attach_module()` as the public full attach lifecycle entrypoint unless a later ADR explicitly makes that decision.

### 5.2. Current lifecycle entrypoint

`run_attach_pipeline()` is the current attach lifecycle seed entrypoint.

It owns the ordered validation path for 0001-0008 and returns an `AttachDecision` with audit and evidence identity.

`register_module()` is the lower-level registration / guard path used by that lifecycle.

---

## 6. Hard invariants

### 6.1. No mutation on rejection

All rejection paths must keep `body_config_updated == false` and must not alter occupancy or module registry.

### 6.2. Success-only mutation

Only valid registration may update body configuration:

`face occupancy -> occupied`

`module registry -> module entry added`

### 6.3. Registration is not activation

`attached` and `passport_validated` do not mean:

`powered`

`thermally cleared`

`capability_active`

`mission_ready`

`runtime_ready`

The current seed intentionally keeps:

`runtime_ready == false`

`capability_status == inactive` or `not_evaluated`

### 6.4. Evidence card is not source of truth

Evidence Card is a read-only projection of audit-backed source data.

It must not validate passports, create runtime state, activate modules, execute commands or invent facts.

### 6.5. Face Map is skeleton / fixture only

The current `F00-F11` map and allowed / forbidden mount-class rules are runtime skeleton / test fixture material.

They are not final geometry, not final face normals, not final adjacency, not a calculated Face Map, not Thrust Map and not Torque Map.

### 6.6. Public API boundary

`run_attach_pipeline()` is the current full attach lifecycle seed entrypoint.

`attach_module()` is retained as the legacy Slice 0001 negative-path helper. A `MODULE_ATTACH_NOT_IMPLEMENTED` result from `attach_module()` for a shaped passport must not be read as evidence that the current lifecycle is missing; positive attach registration is owned by `run_attach_pipeline()` / `register_module()`.

Machine-checkable marker:

`CURRENT_ATTACH_LIFECYCLE_ENTRYPOINT == "run_attach_pipeline"`

### 6.7. Evidence status wording

`EvidenceCard.status == "implemented"` means the ORION evidence projection for the audit-backed fact is implemented / evidence-complete.

It does not mean:

`module runtime implemented`

`module runtime_ready`

`capabilities active`

`full QIKI Body runtime compliance`

Use the following vocabulary split:

| Field | Meaning | Current attach-seed value |
|---|---|---|
| `EvidenceCard.source_type` | source class for projection | `audit` |
| `EvidenceCard.status` | evidence-card conformance | `implemented` or `missing` |
| `EvidenceCard.subject_status` | domain outcome | `rejected` or `attached` |
| `AttachDecision.runtime_ready` | module runtime readiness | always `false` in this seed |
| `AttachDecision.capability_status` | capability activation state | `inactive` / `not_evaluated` |

### 6.8. Mount compatibility is fail-closed

`MODULE_MOUNT_CLASS_FORBIDDEN` covers both explicitly forbidden classes and classes that are not explicitly allowed by the current skeleton mount rules.

This preserves fail-closed attach behavior. It does not make the fixture `allowed_mount_classes` final canon.

---

## 7. Out of scope / not proven

The current seed does not prove:

PDU load permission;

thermal clearance;

real module catalog;

capability activation;

command unlocks;

bayonet power/data bridge;

bayonet hard-lock physics;

full ORION UI;

MFD rendering;

proto contracts;

NATS subjects;

gRPC contracts;

telemetry paths;

RCS physics;

Thrust Map;

Torque Map;

NBL runtime;

RTG runtime;

reactor runtime;

field-drive runtime;

full QIKI Body v0.2.2 runtime compliance.

---

## 8. Targeted test set

The current targeted evidence check uses:

```text
tests/unit/test_body_structure_attach_rejection.py
tests/unit/test_orion_evidence_card_surfaces_module_attach_rejection.py
tests/unit/test_body_structure_valid_passport_attach.py
tests/unit/test_body_structure_mount_occupancy_rejection.py
tests/unit/test_body_structure_mount_compatibility_rejection.py
tests/unit/test_body_structure_invalid_passport_rejection.py
tests/unit/test_body_structure_unknown_mount_rejection.py
tests/unit/test_body_structure_attach_validation_pipeline.py
tests/unit/test_orion_evidence_card_mapping.py
tests/unit/test_orion_evidence_card_source_owner.py
tests/unit/test_orion_evidence_card_trust_gate.py
tests/unit/test_body_structure_command_lifecycle.py
tests/unit/test_body_structure_passport_integrity.py
tests/unit/test_body_structure_snapshot_immutability.py
tests/unit/test_body_structure_if_audit_aliases.py
tests/unit/test_orion_evidence_card_if_orion_fields.py
tests/unit/test_evidence_card_view.py
```

Expected targeted result in a suitable local environment:

`79 passed`

---

## 9. Patch discipline

Future patches touching this contour must preserve:

`run_attach_pipeline()` ordered validation;

stable reason codes;

audit event identity returned by the producing event;

read-only evidence projection;

copy-on-write / immutability discipline for snapshots;

no runtime-ready claim after registration alone;

no full QIKI Body runtime claim.
