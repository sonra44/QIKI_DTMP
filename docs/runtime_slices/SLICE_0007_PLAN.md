# RUNTIME_SLICE_0007 — Mount Point Existence Guard / Unknown Mount Rejection — STATUS

## 0. Current status

Status:

`implemented / unit-verified in current repo snapshot`

Scope:

`valid passport with unknown mount is rejected without mutating body_config`

Proof marker:

`MOUNT_POINT_UNKNOWN`

This document is a status-alignment record. It does not introduce new runtime scope and does not claim full QIKI Body v0.2.2 runtime compliance.

Detailed evidence lives in:

`docs/runtime_slices/ATTACH_LIFECYCLE_EVIDENCE.md`

---

## 1. Runtime owner

Runtime / policy file:

`src/qiki/services/q_core_agent/core/body_structure.py`

Current attach lifecycle entrypoint:

`run_attach_pipeline()`

Legacy Slice 0001 helper:

`attach_module()`

ORION read-only evidence projection:

`src/qiki/services/operator_console/orion_v/body_structure_evidence.py`

`src/qiki/services/operator_console/orion_v/evidence_card.py`

`src/qiki/services/operator_console/orion_v/evidence_card_mapping.py`

---

## 2. Guardrails

This slice status does not prove:

PDU load permission;

thermal clearance;

real module catalog;

capability activation;

bayonet bridge;

full ORION UI or MFD;

proto / NATS / gRPC / telemetry integration;

RCS physics;

Thrust Map or Torque Map;

NBL / RTG / reactor / field-drive runtime;

full QIKI Body runtime compliance.

---

## 3. Targeted regression rule

If a future patch touches this slice area, run the attach lifecycle targeted tests listed in:

`ATTACH_LIFECYCLE_EVIDENCE.md`

Expected status for this narrow contour:

`84 selected test items passing`
