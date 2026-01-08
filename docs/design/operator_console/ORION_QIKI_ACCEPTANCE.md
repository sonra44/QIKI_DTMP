# ORION↔QIKI Acceptance (PR5/PR6)

**Goal:** verify that ORION intent I/O and QCore proposals remain **proposals-only** and that UI/data quality improvements (PR6) remove “tables of N/A” without inventing data.

**Invariant:** no approve/execute; `proposed_actions` is always empty.

**Run everything Docker-first.**

---

## Setup

1) Start Phase1 stack:

```bash
cd QIKI_DTMP
docker compose -f docker-compose.phase1.yml up -d --build
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
docker compose -f docker-compose.phase1.yml ps
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps
```

2) (Optional) attach ORION:

```bash
docker attach qiki-operator-console
# detach: Ctrl+P then Ctrl+Q
```

---

## 6 manual scenarios (record results)

Use ✅/❌ and a short note (what you saw + how to reproduce).

### 6.1 ORION without NATS

- [ ] ✅/❌ ORION does not crash if NATS is unavailable.
- [ ] ✅/❌ Header shows offline link state.
- [ ] ✅/❌ Shell commands still work (e.g. `help`).

How:
- Stop NATS: `docker compose -f docker-compose.phase1.yml stop nats`
- Restart operator console: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`

Notes:

---

### 6.2 ORION + NATS: `q:` sends intent, proposals arrive, UI does not freeze

Prereq: PR3+PR4 merged (QCore intent bridge publishes proposals on `qiki.proposals.v1`).

- [ ] ✅/❌ Typing `q: scan 360` (or `// scan 360`) does not block ORION.
- [ ] ✅/❌ Calm strip shows “Intent sent”.
- [ ] ✅/❌ Calm strip shows incoming proposals (“QIKI: …”) and they are not mixed with incidents.

Notes:

---

### 6.3 QCore without `OPENAI_API_KEY`: stub proposals, no exceptions

- [ ] ✅/❌ With `OPENAI_API_KEY` unset, QCore stays up and produces stub proposals.
- [ ] ✅/❌ No stack traces / crash loops.

How:
- Ensure env is not set in container:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev env | rg OPENAI_ || true`

Notes:

---

### 6.4 QCore with wrong key / timeout: fallback proposal + clean logs

- [ ] ✅/❌ Wrong key results in fallback “LLM unavailable …” proposal.
- [ ] ✅/❌ Logs do not contain request payloads or Authorization headers.

How:
- Set in environment for the `qiki-dev` container / service runner as appropriate:
  - `OPENAI_API_KEY=invalid`
  - `OPENAI_TIMEOUT_S=1`

Notes:

---

### 6.5 Invariant: proposals always have no actions

- [ ] ✅/❌ Raw data / inspector shows `proposed_actions` is empty (or absent) everywhere.
- [ ] ✅/❌ Unit tests enforce it (see `tests/unit/test_orion_qiki_protocol_v1.py::test_proposal_v1_actions_must_be_empty_in_stage_a`).

Notes:

---

### 6.6 Factory/Mission gating

Prereq: PR7 merged (environment mode snapshot + proposals gating).

- [ ] ✅/❌ Mode is visible in ORION header.
- [ ] ✅/❌ Switching mode changes verbosity/count of proposals.

Notes:

---

## Evidence

Attach:
- `docker compose ... ps` output (health)
- (optional) `docker logs qiki-operator-console --tail=200`
- (optional) `docker logs qiki-dev-phase1 --tail=200`

