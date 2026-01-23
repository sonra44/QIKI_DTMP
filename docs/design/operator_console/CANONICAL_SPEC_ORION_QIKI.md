# ORION ↔ QIKI — Canonical Spec (MVP → Safe Growth)

**Goal:** a deterministic Operator Shell OS (ORION) that can talk to a headless “brain” (QIKI) over NATS using a strict request/reply contract, with bilingual UI (`EN/RU`) everywhere and **no auto-actions** in the MVP.

**Non-goals (now):** Radar UX work, autonomous actuation, proactive chatter, “infinite log tail” as a primary UI.

---

## 0) Vocabulary

- **ORION**: Textual TUI “Shell OS” for the operator (UI only).
- **QIKI**: headless service/daemon that interprets intent, produces proposals, later (optionally) executes approved actions.
- **Intent**: operator free-text + UI context.
- **Proposal**: structured, bilingual recommendation set produced by QIKI.
- **Action**: typed command request (MVP: always empty).

---

## 1) UX invariants (must never regress)

- **Bilingual everywhere:** every user-facing label/value is represented as `EN/RU` (no spaces around `/`).
- **No UI abbreviations:** never shorten words in UI strings.
- **No-mocks:** missing data must render as `N/A/НД`.
- **Stable chrome:** switching screens changes content, not layout.
- **Two channels:** `Events/События` is high-frequency; `Console/Консоль` is calm operator dialogue.

References:
- System logic and screen model: `docs/design/operator_console/ORION_OS_SYSTEM.md`
- Integration overview: `docs/design/operator_console/QIKI_INTEGRATION_PLAN.md`

---

## 2) System truth: modes (not “prompt roles”)

QIKI owns the truth of the current system mode and publishes it outward; ORION only displays it.

Canonical modes (MVP):
- `FACTORY/ЗАВОД`: development, diagnostics, explanations allowed; **no auto-actions**.
- `MISSION/МИССИЯ`: strictness, minimal noise, allowlists; still **no auto-actions** until explicitly enabled.

Mode is part of QIKI state and must be included in every response.

### 2.1 Mode changes (MVP)

- Mode can be changed only by an explicit operator intent (no hidden auto-toggles).
- Canonical commands (intent text): `mode factory` / `mode mission` (also accepted: `режим завод` / `режим миссия`).
- ORION does not change the mode itself; it only sends intents and displays QIKI state.

---

## 3) Transport: NATS pub/sub (correlated “chat” loop)

### 3.1 Subject

Canonical MVP subjects:
- Requests (intents): `qiki.intents`
- Responses (replies/proposals): `qiki.responses.qiki`

Correlation: `request_id` is the join key between request and response.

### 3.2 Timeouts and resilience

- ORION must use a strict timeout (e.g. `2–5s` in FACTORY; shorter in MISSION).
- If no reply: ORION writes a calm console line and continues.
- Default timeout knob: `QIKI_RESPONSE_TIMEOUT_SEC` (seconds).
- Because responses are on a shared subject, ORION must ignore responses with unknown `request_id` by default.
  - Debug knob: `QIKI_LOG_FOREIGN_RESPONSES=1` to log “foreign” responses.
- QIKI must always return a valid JSON response (even on errors).

### 3.3 Security boundary (MVP)

- QIKI has full **read** access to telemetry/state.
- **Write** access is represented only as *typed actions*, and in MVP actions are **always empty**.
- Any future execution must be behind policy + explicit operator approval (outside this MVP spec).

---

## 4) Data contract (JSON) — strict, validated

Formal JSON Schemas (canonical, docs-as-code):
- `schemas/asyncapi/qiki.intents/v1/payload.schema.json`
- `schemas/asyncapi/qiki.responses.qiki/v1/payload.schema.json`

### 4.1 Common type: bilingual text

All human-facing strings are bilingual objects; ORION formats them as `en/ru`.

```json
{ "en": "System", "ru": "Система" }
```

### 4.2 Request: `QikiChatRequest.v1`

```json
{
  "version": 1,
  "request_id": "uuid",
  "ts_epoch_ms": 0,
  "mode_hint": "FACTORY",
  "input": {
    "text": "free text from operator",
    "lang_hint": "auto"
  },
  "ui_context": {
    "screen": "System/Система",
    "selection": {
      "kind": "event|incident|track|snapshot|none",
      "id": "optional"
    }
  },
  "system_context": {
    "telemetry_freshness": "FRESH|STALE|DEAD|UNKNOWN",
    "summary": {
      "battery_pct": null,
      "online": null
    }
  }
}
```

Notes:
- `mode_hint` is a hint only; QIKI must reply with the authoritative mode.
- `system_context.summary` is intentionally tiny for MVP; QIKI can request more via `suggested_questions`.

### 4.3 Response: `QikiChatResponse.v1`

```json
{
  "version": 1,
  "request_id": "uuid",
  "ok": true,
  "mode": "FACTORY",
  "reply": {
    "title": { "en": "Next step", "ru": "Следующий шаг" },
    "body": { "en": "…", "ru": "…" }
  },
  "proposals": [
    {
      "proposal_id": "p-001",
      "title": { "en": "Calm console strip", "ru": "Спокойная зона вывода" },
      "justification": { "en": "…", "ru": "…" },
      "confidence": 0.0,
      "priority": 0,
      "suggested_questions": [
        { "en": "Show current screen set", "ru": "Покажи текущий набор экранов" }
      ],
      "proposed_actions": []
    }
  ],
  "warnings": [
    { "en": "Actions disabled in FACTORY", "ru": "Действия отключены в ЗАВОД" }
  ],
  "error": null
}
```

### 4.4 Error object

If `ok=false`, `error` must be present and `reply/proposals` can be empty but still valid.

```json
{
  "code": "TIMEOUT|INVALID_REQUEST|INTERNAL|UNAVAILABLE",
  "message": { "en": "…", "ru": "…" }
}
```

---

## 5) ORION UI behavior (input/output)

### 5.1 Input routing (MVP, no mode toggle)

- Default: `OPERATOR SHELL/ОБОЛОЧКА` — local UI commands (help/screen/filter/simulation.*).
- QIKI intents: **explicit prefix required** — `q:` or `//` (free text after the prefix is published to `qiki.intents`).

### 5.2 Output placement rules

- Every command (including QIKI replies) must write to a **calm console strip** visible on all screens.
- `Console/Консоль` screen is the scrollback/history view.
- `Events/События` must not be polluted by command dialogue.

### 5.3 Inspector contract (for QIKI replies)

When an operator selects a QIKI reply/proposal row, inspector must show:
1) `Summary/Сводка`
2) `Fields/Поля` (typed fields, bilingual formatted)
3) `Raw JSON/Сырой JSON` (safe preview)
4) `Actions/Действия` (future; empty in MVP)

---

## 6) QIKI implementation policy (MVP)

- QIKI may use LLMs, but **must produce strictly valid `QikiChatResponse.v1`**.
- If LLM output is invalid: respond with `ok=false` + `INVALID_REQUEST` or `INTERNAL` and a calm bilingual explanation.
- Secrets: OpenAI keys only via environment variables; never log secrets; never store in repo.
- Circuit breaker: after N consecutive LLM failures, temporarily disable LLM and return deterministic “LLM unavailable” responses.

---

## 7) Linear implementation order (no branching)

1) ORION: calm console strip + `Ctrl+E` focus + input routing **без mode toggle**:
   - shell commands by default (`help`, `screen events`, ...),
   - QIKI intents only via prefix `q:` or `//`.
2) QIKI: minimal handler: subscribe `qiki.intents` and publish deterministic stub responses to `qiki.responses.qiki` (no LLM).
3) ORION: render QIKI replies + proposal list + inspector view.
4) QIKI: add `NeuralEngine` (LLM) behind strict schema validation + fallback.
5) Later (separate spec): approvals + typed actions + sim pause/time control.
