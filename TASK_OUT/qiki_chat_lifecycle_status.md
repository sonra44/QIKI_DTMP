# qiki_chat lifecycle status

## 1. Runtime role

`qiki_chat` is a standalone NATS request/reply ingress built around `qiki.chat.v1`. In the current project state it is not the supported canonical QIKI ingress; it survives as an alternate standalone surface with legacy/transitional residue around the old lightweight intent/proposal loop.

- Actual entrypoint: `src/qiki/services/qiki_chat/main.py` subscribes to `qiki.chat.v1`, validates `QikiChatRequestV1`, calls `qiki_chat.handler.handle_chat_request()`, and answers through `msg.respond(...)` (`src/qiki/services/qiki_chat/main.py:19-45`).
- It assumes direct NATS access and nothing else: no HTTP server, no gRPC, no compose-owned container, no dedicated Dockerfile found in current runtime contour.
- It is still runnable as a manual tool path because `src/qiki/tools/qiki_ask.py` sends `QikiChatRequestV1` to `qiki.chat.v1` over plain NATS request/reply (`src/qiki/tools/qiki_ask.py:14-31`).
- Existing project audit already classifies it as standalone legacy/non-canonical ingress absent from supported compose stack (`TASK_OUT/runtime_registry.md:12`, `QIKI_CODEX_AUDIT_FOR_TASKING.md:734-748`).

## 2. Inputs / outputs

### Inputs

- NATS subject: `qiki.chat.v1`
  - hardcoded in `src/qiki/services/qiki_chat/main.py:19`
  - request payload type: `QikiChatRequestV1`
  - mode source: env `QIKI_MODE`, default `FACTORY` (`src/qiki/services/qiki_chat/main.py:35`)
- Runtime assumptions:
  - reachable NATS server via `NATS_URL`
  - request JSON matches `QikiChatRequestV1`
  - no dependency on `q-sim-service`, `q-bios-service`, JetStream, or ORION-specific bus subscriptions is present in this service code

### Outputs

- Transport output is reply-only:
  - service answers via `msg.respond(...)`, not via canonical `qiki.responses.qiki` (`src/qiki/services/qiki_chat/main.py:39-42`)
- Semantic output is a `QikiChatResponseV1` built by `handle_chat_request()`
- Proposal payloads may contain suggested `COMMANDS_CONTROL` actions inside response proposals, but `qiki_chat` itself does not publish to `qiki.commands.control`; it only returns those actions in the reply payload (`src/qiki/services/qiki_chat/handler.py:76-123`, `src/qiki/services/qiki_chat/handler.py:125-164`)

### Actual supported intent surface inside handler

- The handler is narrow and deterministic:
  - acknowledges proposal decisions textually only (`src/qiki/services/qiki_chat/handler.py:30-64`)
  - recognizes only dock/power-style inputs:
    - `dock.on`
    - `power.dock.on`
    - `dock.off`
    - `power.dock.off`
    - `dock.engage [port]`
    - `dock.release`
  - otherwise returns “No proposals” (`src/qiki/services/qiki_chat/handler.py:66-164`)

## 3. Place in canonical contour

`qiki_chat` is not a supported ingress in the canonical contour.

- Canonical default contour is explicitly:
  - `q-core-intents` owns `qiki.intents -> qiki.responses.qiki`
  - `faststream-bridge` is pushed off live intents in default stack
  (`docs/ORION_V_QUICKSTART.md:13-16`, `docker-compose.phase1.yml:193-197`, `docker-compose.phase1.yml:231-239`)
- `q-core-intents` is the compose-backed live listener on `qiki.intents` and publishes to `qiki.responses.qiki` (`src/qiki/services/q_core_agent/qiki_orion_intents_service.py:3445-3459`, `src/qiki/services/q_core_agent/qiki_orion_intents_service.py:3724`)
- `qiki_chat` does not participate in `docker-compose.phase1.yml`, `docker-compose.qcore-intents.yml`, or the supported ORION runtime overlays. No current compose service references it.
- Canonical ORION artifacts and acceptance dossiers consistently describe the live path as `ORION V -> qiki.intents -> q-core-intents -> qiki.responses.qiki`, not `qiki.chat.v1` (`TASK_OUT/orion_execution_dossier.md`, `TASK_OUT/runtime_contour_canon.md:166-167`)

Conclusion:

- `qiki_chat` is not supported canonical ingress.
- Tasks that assume it is the live production QIKI entrypoint are mis-scoped.

## 4. Place in alternate paths

`qiki_chat` is still a real alternate ingress.

- It can be run standalone by direct Python entrypoint (`src/qiki/services/qiki_chat/main.py:63-69`).
- It has a matching manual client/tool path in `src/qiki/tools/qiki_ask.py` (`src/qiki/tools/qiki_ask.py:38-49`).
- It uses the same shared request/response models as canonical intent flow:
  - `QikiChatRequestV1`
  - `QikiChatResponseV1`
  (`src/qiki/shared/models/qiki_chat.py`)
- That makes it an alternate transport surface for the old/simple proposal contract, but not a default runtime contour component.

Lifecycle interpretation:

- `alternate`: yes, because it is runnable and has a client path
- `transitional`: partially, because the same handler logic is still reused inside `faststream_bridge`
- `legacy`: yes relative to canonical ingress ownership, because the project canon no longer routes operator/QIKI traffic through this subject

## 5. Conflicts with current q-core-intents canon

There is no current subject-ownership conflict in the default contour, but there is real semantic overlap and architecture drift.

### No direct default subject conflict

- `qiki_chat` listens on `qiki.chat.v1`
- canonical ingress listens on `qiki.intents`
- so default runtime does not have both services competing for the same live subject

### Real semantic conflict / overlap

- `qiki_chat.handler` still defines a mini intent/proposal system using the same shared request/response models as canonical QIKI flow (`src/qiki/services/qiki_chat/handler.py:27-164`, `src/qiki/shared/models/qiki_chat.py`)
- `faststream_bridge` still imports and reuses that handler for its latent intent path (`src/qiki/services/faststream_bridge/app.py:307-410`)
- current canonical `q-core-intents` has moved beyond this model and now owns richer intent consequences:
  - live `qiki.intents` listener
  - publishes `qiki.responses.qiki`
  - publishes objective events
  - publishes hidden audit events
  (`src/qiki/services/q_core_agent/qiki_orion_intents_service.py:3524`, `src/qiki/services/q_core_agent/qiki_orion_intents_service.py:3544`, `src/qiki/services/q_core_agent/qiki_orion_intents_service.py:3581-3585`, `src/qiki/services/q_core_agent/qiki_orion_intents_service.py:3636-3640`)

### Concrete drift points

- `qiki_chat/handler.py` comment says decision execution is handled upstream by `faststream_bridge` (`src/qiki/services/qiki_chat/handler.py:30-31`). In current canonical contour that is no longer the supported live owner path; `q-core-intents` is.
- The handler only understands a small dock/power command subset, while canonical `q-core-intents` now handles broader QIKI procedures and observation/combat flows.
- `qiki_chat` replies through request/reply, while canonical contour expects persistent bus semantics on `qiki.responses.qiki`.

Net effect:

- `qiki_chat` does not currently break canonical ownership by itself.
- It does remain a misleading alternate mental model for “how QIKI ingress works now”.

## 6. Recommended status label

Recommended status label: `alternate legacy ingress`

Why this label fits best:

- `supported`: no
  - not present in supported compose contour
  - not named as canonical ingress in current runbooks/canon
- `alternate`: yes
  - runnable standalone
  - has a real request client path (`qiki_ask.py`)
- `transitional`: secondary trait, not main label
  - because parts of its logic still survive as reused handler residue in `faststream_bridge`
- `legacy`: yes
  - because canonical ingress ownership has already moved to `q-core-intents`

Operational reading:

- `qiki_chat` can receive narrowly scoped maintenance or evidence tasks as a live alternate/support ingress.
- It should not receive tasks framed as if it were the supported canonical QIKI runtime path.

## 7. Minimal next task candidates

- Write a narrow drift note for `src/qiki/services/qiki_chat/handler.py` comment and related docs:
  - current comment still implies `faststream_bridge` is the upstream decision executor
  - canonical owner is now `q-core-intents`
- Build a tiny runtime proof dossier for alternate usage only:
  - run `src/qiki/tools/qiki_ask.py` against a manually started `qiki_chat` and prove request/reply behavior on `qiki.chat.v1`
- Record consumer reality:
  - identify whether any scripts, operators, or external tools still rely on `qiki.chat.v1` outside `qiki_ask.py`
- Add one canon-sync artifact:
  - mark `qiki_chat` explicitly as non-canonical alternate ingress wherever docs still imply “QIKI ingress” without distinguishing canonical `qiki.intents`

