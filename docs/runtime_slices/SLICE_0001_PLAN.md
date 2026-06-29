# RUNTIME_SLICE_0001 — Body Structure Evidence Seed — PLAN

> Current repo snapshot status: **implemented / unit-verified as part of the narrow attach-lifecycle seed**.
>
> This file is preserved as the historical Slice 0001 plan. The current evidence map is maintained in `docs/runtime_slices/ATTACH_LIFECYCLE_EVIDENCE.md`; later slices 0002-0008 are also represented as status-alignment documents in this directory.
>
> Full QIKI Body v0.2.2 runtime compliance remains **not claimed**.
>
> Historical status: **plan only** (first commit of branch `runtime/body-structure-evidence-seed-0001`).
> No runtime code in this commit. Code starts only after this plan is reviewed (operator + Codex).
> Tracks GitHub Issue #2. Follows merged QIKI Body v0.2.2 documentation package (`main` @ `68e2c03`).

This slice is **not** a full implementation of QIKI Body v0.2.2. It is the first provable seed of **one negative causal loop**:

```
module attach request WITHOUT passport
  -> rejected (runtime/policy owner)
  -> reason_code MODULE_PASSPORT_MISSING
  -> audit event
  -> read-only ORION evidence stub surfaces the rejection as a fact
```

## Scope

- Face Map **skeleton** F00–F11 (structural placeholder only; status `skeleton`, not calculated).
- Module Passport **schema/template** (minimal contract; enough to tell "passport present + required fields" vs "missing").
- `body_config` **snapshot** (minimal, honestly marked `skeleton`/`TBD`).
- `bayonet_A` / `bayonet_B` **state represented** (interface state only; NOT "hard lock works").
- Module attach **rejection without passport** (the negative path).
- `reason_code: MODULE_PASSPORT_MISSING` (domain reason, runtime-owned).
- **Audit event** for the rejection (reuses existing event store format).
- **Read-only ORION evidence stub** that *displays* the already-produced rejection/audit fact.

## Out of scope

- #4908 full ORION Evidence Card surfacing — **only** a minimal read-only stub needed to surface the `MODULE_PASSPORT_MISSING` rejection. (4908 stays a separate downstream ticket.)
- Module Passport happy-path / valid-attach flow (this slice needs only the negative path).
- Face geometry, normals, adjacency, Thrust/Torque readiness, verified face positions.
- Bayonet hard-lock physics / bridge.
- Full MFD redesign, "pretty UI".
- RCS physics, Thrust Map / Torque Map calculation.
- NBL / reactor / RTG / field-drive runtime.
- Module economy. Expanding QIKI autonomy. Architecture rewrite.
- proto / NATS / gRPC / telemetry path changes.

## Canon sources (target canon, `docs/design/hardware_and_physics/qiki_body_v0_2_2/`)

- `01_BODY_CANON.md` §22 (module passport mandatory), §24 (command gating, rejection returns reason_codes), §27 (audit), §26 (ORION Evidence).
- `02_REQUIREMENTS.md` REQ-MODULE-001 (passport mandatory), REQ-CMD-005 (rejected → reason_codes), REQ-AUDIT-001, REQ-ORION-003.
- `04_CALCULATION_FRAME.md` §6 Face Map skeleton, §14 Module Passport Template, §16 Command Gating reason codes.
- `06_INTERFACE_CONTROL.md` `IF-MODULE-PASSPORT-001`, `IF-BAYONET-MECH-001`, `IF-AUDIT-001`, `IF-ORION-EVIDENCE-001`.
- `05_ENGINEERING_RATIONALE.md` §19 forbidden-wording table.
- `09_ACCEPTANCE_CHECKS.md`.
- **`Canon ≠ implemented`** — nothing here claims runtime conformance beyond what tests prove.

## Runtime owner path (who owns the rejection)

- The rejection is owned by the **runtime/policy layer** (`body_structure.attach_module`), NOT by ORION.
- **ORION does not validate the module passport; it displays the already-produced rejection/audit fact** (read-only consumer).
- Audit is owned by the existing event store; the slice appends an event, it does not invent a second audit format.

## Files expected

New, additive (no edits to existing runtime behaviour):

- `src/qiki/services/q_core_agent/core/body_structure.py` (NEW) — runtime/policy layer:
  - `FACE_IDS` = F00..F11 skeleton; `BodyConfigSnapshot` (minimal, marked skeleton/TBD);
  - `BayonetId` (A/B) + `BayonetState` (interface state represented, e.g. `free | occupied | unknown`);
  - `ModulePassport` minimal schema (required-field check only) + `passport_is_present_and_valid_shape(...)`;
  - `MODULE_PASSPORT_MISSING` reason constant;
  - `attach_module(request, passport=None, *, audit_sink) -> AttachResult` — negative path: missing/invalid-shape passport → `AttachRejected(reason_code=MODULE_PASSPORT_MISSING)`, and appends an audit event via the injected sink.
- `src/qiki/services/operator_console/orion_v/body_structure_evidence.py` (NEW) — read-only ORION stub:
  - `rejection_to_evidence(rejection, audit_event) -> RejectionEvidence` (source owner, command/rejection state, reason_code) — **display only, no validation**.

Reused (no schema change):

- `src/qiki/services/q_core_agent/core/event_store.py` — `SystemEvent` / `EventStore.append_new(...)` as the audit sink. **Exact `SystemEvent` field shape to be confirmed at implementation start** so we map onto it (not a second format). If `SystemEvent` cannot carry the needed fields without a schema change, STOP and raise as a review item (no silent schema/proto change).

To confirm before code (no invented second format):
- exact `SystemEvent` constructor/fields (`event_store.py:36`);
- whether attach happens anywhere already (recon: no `passport`/`module_attach` in `src` → greenfield).

## Tests expected

`tests/unit/test_body_structure_attach_rejection.py` (NEW), pytest:

1. `attach_module(request, passport=None)` → result is rejected; `reason_code == "MODULE_PASSPORT_MISSING"`.
2. passport present but missing required fields → same rejection (shape-only check, no happy path).
3. rejection appends exactly one audit event carrying: request/command id, attempted mount id, `reason=MODULE_PASSPORT_MISSING`, source owner, timestamp.
4. `rejection_to_evidence(...)` (ORION stub) reads the rejection/audit as a fact (source owner, rejection state, reason_code) and **does not itself validate** (passing a pre-made rejection is enough; stub never calls attach policy).
5. **forbidden-wording guard**: any operator-facing string produced (evidence/messages) contains none of: `module installed`, `module active`, `bridge allowed`, `hard lock verified`, `runtime conforms`, `QIKI Body implemented`; rejection is phrased as `attach rejected: passport missing`.
6. Face Map skeleton exposes F00–F11 and is marked `skeleton` (no geometry/normals asserted).

## Acceptance evidence (Slice 0001 done criteria)

`pytest tests/unit/test_body_structure_attach_rejection.py` green proving: attach-without-passport is rejected, `MODULE_PASSPORT_MISSING` reason is stable, an audit event is created, and the read-only evidence stub can read it as a fact — **plus** forbidden-wording clean.
Schema-only (passport/face-map present but no rejection + audit + evidence) ⇒ **slice not closed**.

## No proto / NATS / gRPC / telemetry path changes

Pure Python module + read-only stub + unit test. No proto, no NATS subjects, no gRPC contracts, no telemetry paths, no ORION UI/MFD rendering changes, no generated files. Audit reuses the existing event store API only.

## Forbidden wording (banned in code, strings and tests)

`module installed` · `module active` · `bridge allowed` · `hard lock verified` · `runtime conforms` · `QIKI Body implemented` · `implemented`/`verified` as a claim without evidence.
Allowed status vocabulary: `skeleton` · `template` · `target-only` · `not-implemented` · `rejected`. Allowed rejection phrasing: `attach rejected: passport missing`.

## Division (Claude ↔ Codex)

- **Claude:** this plan + TDD test + the full vertical-loop implementation (single owner for loop coherence).
- **Codex:** canon review of each step (passport §14, `IF-MODULE-PASSPORT-001`, `IF-AUDIT-001`, `IF-ORION-EVIDENCE-001`), forbidden-wording + acceptance check, RAG cross-check.

## Not in this commit

Untracked `AGENTS.md*`, `CLAUDE.md*` backups and `artifacts/` are unrelated to Slice 0001 and are NOT included.

## Protocol corrections — agreed Claude + Codex (2026-06-21)

Adopted amendments to the operator's two-agent execution protocol (apply to this slice and as defaults for future runtime slices):

1. **Audit reuse (DoD).** The rejection MUST be recorded into the existing project audit layer (`event_store.SystemEvent` via `EventStore.append_new`). A slice-local sink is allowed only as a RED-step scaffold and must be adapted to the real store before DoD. No second audit format.
2. **Audit → evidence consistency (Core Invariant).** The read-only evidence stub MUST read from the audit event and guard `rejection ↔ audit` consistency (reason_code, source_owner, module_id); inconsistent evidence is not surfaced (raises).
3. **Passport shape.** A passport is "present" only if required fields are non-empty AFTER `strip()`. Whitespace-only == missing → `MODULE_PASSPORT_MISSING`.
4. **Forbidden-wording test scope.** The guard checks only operator-facing strings produced by runtime/evidence, NOT a repo-wide grep (docs/tests legitimately list banned phrases as a prohibition).
5. **Cycle granularity.** Small cycles may be merged when both agents approve, provided the per-(merged-)cycle Agent-A report + Agent-B verdict are preserved. `C0_FILE_MAP` lives inside this `SLICE_0001_PLAN.md` — no separate artifact.

**§16 data-contract reconcile (principle).** Align the implementation to the protocol's minimal contract ONLY for fields that strengthen the `rejection → audit → evidence` chain. Applied now: `module_id` in `AttachResult` + `RejectionAuditEvent` + `SystemEvent.payload` + `RejectionEvidence`; `claim_type="module_attach_rejection"`, `source_type="audit"`, `read_only=True` in evidence (aligns `IF-ORION-EVIDENCE-001`). Deferred as template-inflation-without-consumer: `body_id`, `modules` list, full face_map object, `status` string vs `rejected` bool.

**Branch-base principle (hard, learned).** A runtime/PR branch is ALWAYS created from fresh `origin/main`, never from an integration/overlay/codex branch or a dirty local branch.
