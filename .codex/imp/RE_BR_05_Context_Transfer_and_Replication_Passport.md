---
id: BR-05
status: reassembled
owner: Макс
type: context-branch
priority: critical
canonical-layer: transfer-governance
reassembly-prefix: RE_
---

# RE_BR_05 — Context Transfer and Replication Passport

## Card

**Role:** fix not the code truth of the project, but the rules for safe transfer, restart and replication of project context across chats, agents, sessions and saved document packs.

**Main conclusion:** the repository and the current document pack do confirm the existence of a context-entry problem, mixed trust layers and competing starting points. They do **not** prove that the current transfer structure is already physically embedded in the repository as a finished standard. Therefore BR-05 must be treated as a **governance branch**: justified by observed fragmentation, but still remaining a policy layer above the code.

**When to read:** after BR-01, BR-02, BR-03 and BR-04.

**When not to read:** instead of code verification, runtime validation or product/architecture review.

**Status:** canonical governance branch for transfer discipline, with an explicit boundary between observed fact, analytical conclusion and adopted policy.

**Critical rule:** BR-05 must never present transfer policy as if it were identical to code truth.

---

# 1. Purpose

This branch exists to answer one practical question:

**how should the QIKI project context be transferred, restored and continued without collapsing again into archive noise, handover fragments, restart snapshots and mixed-confidence materials.**

BR-05 does not define the project architecture and does not prove product identity.
Its role is narrower and stricter:

- normalize entry into the project;
- define trust levels for materials;
- fix reading order;
- prevent accidental replacement of code truth by handover rhetoric;
- preserve continuity between iterations without copying the entire chat history as canon.

---

# 2. What is actually confirmed

## F1. The repository really has a context-entry problem

The project contains multiple candidate starting points, context files, restart instructions, handover notes and snapshot-like materials.

This means the question of **how to enter the project** has become a real operational problem, not an artificial documentation concern.

## F2. These entry points are heterogeneous in status

Not all entry artifacts have the same role.
Some are closer to code-oriented orientation, some are handover-oriented, some are temporary session snapshots, some are historical salvage material.

Therefore equal trust across all such files would be analytically wrong.

## F3. Fragmentation justifies a governance layer

The need for a transfer-governance layer is supported by the repository state and by the document pack history.
What is justified is the **problem statement** and the **need for discipline**.
What is not automatically proven by code is the exact final structure of that discipline.

---

# 3. What remains a policy decision

The following are not direct code facts. They are governance decisions introduced to stabilize work on the project:

- using ROOT as the recommended first entry point;
- using BR-01..BR-05 as the main normalized branch set;
- separating Canon / Working / Archive layers;
- treating runtime evidence as a controlled working layer rather than as free-floating notes;
- requiring explicit distinction between fact, conclusion and project decision.

These decisions are justified.
But they must still be marked as **decisions**, not disguised as repository-native truth.

---

# 4. Canonical definition of transfer

## Base formula

Context transfer is **not** raw copying of all conversation history and not blind replication of every memory or context file.

It is the transfer of a **normalized knowledge layer** with:

- a fixed reading route;
- explicit trust levels;
- separation between code truth and policy;
- preserved unresolved zones;
- preserved evidence boundaries.

## Practical meaning

A valid transfer package must allow a new reader or new agent to recover:

1. what is confirmed by code;
2. what is inferred;
3. what is an adopted project decision;
4. what is still unresolved;
5. how to continue without rebuilding the project from random fragments.

---

# 5. What transfer must include

The minimum stable transfer contour should include:

- ROOT / entry normalization;
- BR-01..BR-05;
- current pack index;
- current position document;
- analytical path map;
- maturity matrix;
- architecture note;
- canon map / ADR;
- product truth / gate plan;
- runtime evidence notes;
- risks and unresolved zones;
- completion criteria.

This does **not** mean all of these documents have the same weight.
It means transfer without them becomes lossy.

---

# 6. Trust layers for transfer

## Level A — Canon

Documents that define the active reading route and current controlled interpretation of the project.

Typical members:

- ROOT;
- BR-01..BR-05;
- pack index;
- current position;
- path map;
- maturity matrix.

## Level B — Working

Documents that support proof, clarification, revision or synchronization, but are not automatically the highest interpretive authority.

Typical members:

- runtime evidence notes;
- risks and unresolved zones;
- architecture verification note;
- product truth / gate plan;
- completion criteria;
- methodological support notes.

## Level C — Snapshot / Handover

Temporary session-state and restart-oriented materials.
They may be useful, but must not silently override Canon.

## Level D — Archive / Legacy

Historical, superseded or legacy materials.
Useful for salvage and comparison, but not a primary entry layer.

---

# 7. Conflict rule

If a Canon document conflicts with code verification, the priority goes to code truth.
If a Working document contradicts a Canon document, the contradiction must be resolved explicitly, not ignored.
If a Snapshot or Archive item sounds more confident than the verified pack, that confidence must not be trusted automatically.

The practical priority order is:

**code verification > normalized canon > working evidence > snapshot/handover > archive/legacy**

---

# 8. What BR-05 must not claim

BR-05 must not claim that:

- the repository already physically lives by the full transfer structure;
- all agents or all prior sessions already followed this governance;
- ROOT + BR system is a code-proven internal standard;
- archive and handover materials are now irrelevant.

That would overstate what is actually confirmed.

---

# 9. Current honest status of the transfer layer

The transfer layer is now strong enough to be kept as a canonical governance branch.
But its honest status is still:

- justified by fragmentation;
- operationally useful;
- partially normalized in documents;
- not yet equivalent to a repository-native enforced standard.

So BR-05 should be preserved as an active governance layer, but with explicit policy labeling.

---

# 10. Update rules

1. Any transfer rule must be updated only with an explicit reason.
2. If the reason comes from code reality, mark it as a code-driven correction.
3. If the reason comes from documentation governance, mark it as a policy-driven correction.
4. Snapshot or handover files must never silently redefine the transfer standard.
5. Any change in trust levels or reading order should be reflected in ROOT and pack index.
6. If the pack grows, BR-05 should be updated only where transfer logic changes, not every time a document text is rewritten.

---

# 11. Practical conclusion

BR-05 remains necessary.
Its necessity is confirmed not because code directly proves a transfer protocol, but because the repository and documentation history show recurring context fragmentation.

Therefore the correct final formula is:

**BR-05 is a justified governance branch for normalized project transfer, grounded in observed fragmentation but still clearly separated from code truth.**
