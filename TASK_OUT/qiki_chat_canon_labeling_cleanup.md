# qiki_chat canon labeling cleanup

Date: 2026-03-24 UTC

## Scope

Narrow labeling/docs cleanup around `qiki_chat` only:
- status wording
- comments/docstrings
- alternate vs canonical ingress labeling

No behavior change, no deactivation, no ownership transfer.

## Status statement

`qiki_chat` is:
- alternate ingress
- legacy-compatible
- non-canonical

It is not:
- the supported canonical QIKI ingress
- the owner path for current operator intents

Current canonical ingress remains:
- `q-core-intents`
- `qiki.intents -> qiki.responses.qiki`

## Evidence used

- Existing lifecycle dossier:
  - `TASK_OUT/qiki_chat_lifecycle_status.md`
- Existing project decision:
  - Sovereign memory decision `id=3182`
  - `qiki_chat` treated as alternate legacy ingress, not supported canonical contour service
- Runtime/compose evidence:
  - `qiki_chat` has standalone Python entrypoint on `qiki.chat.v1`
  - no current compose service in supported Phase1 contour references it
  - supported contour routes QIKI ingress through `q-core-intents`

## Drift found

1. `src/qiki/services/qiki_chat/main.py`
   - had no explicit module-level warning that this ingress is alternate/non-canonical
2. `src/qiki/services/qiki_chat/handler.py`
   - comment still implied the live upstream owner path was `faststream_bridge`
   - that is no longer the supported canonical ingress owner path
3. `src/qiki/tools/qiki_ask.py`
   - presented the path as generic “Ask QIKI” without clarifying that it targets the alternate `qiki.chat.v1` ingress

## Changes made

### Code / comments

- `src/qiki/services/qiki_chat/main.py`
  - added module docstring:
    - alternate legacy-compatible ingress
    - not canonical contour
    - canonical path is `q-core-intents` on `qiki.intents -> qiki.responses.qiki`

- `src/qiki/services/qiki_chat/handler.py`
  - updated decision-handling comment
  - clarified:
    - this service is alternate legacy-compatible ingress
    - canonical execution ownership now lives on `q-core-intents`
    - historical alternate paths may still reuse this handler

- `src/qiki/tools/qiki_ask.py`
  - added module docstring
  - updated CLI description to say it targets the alternate legacy-compatible `qiki.chat.v1` path

## Runtime behavior

No runtime behavior changed.

Unchanged:
- subject: `qiki.chat.v1`
- transport: plain NATS request/reply
- handler logic
- request/reply payload models

## Minimal verification

Existing `qiki_chat` tests were re-run after labeling-only edits:

- Green check:
  - `docker compose -f /home/sonra44/QIKI_DTMP/docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/qiki_chat/tests/test_models_aliases.py`
  - result: `. [100%]`

- Existing gap in full slice:
  - `docker compose -f /home/sonra44/QIKI_DTMP/docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/qiki_chat/tests`
  - current result: `F.`
  - failing test: `src/qiki/services/qiki_chat/tests/test_handler.py::test_handle_chat_request_returns_ok_response`
  - reason: the test expects proposals for input `"hello"`, while current handler deterministically returns no proposals for unsupported text
  - this mismatch appears pre-existing and unrelated to the labeling-only edits in this task

## Done check

- `qiki_chat` no longer reads as canonical ingress in touched code/comments
- docs/comments now match its real status: alternate, legacy-compatible, non-canonical
- runtime behavior remains unchanged
