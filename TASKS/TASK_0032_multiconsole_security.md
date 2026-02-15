# TASK-0032 — Secure Multi-Console v1 (Auth + Roles + Control Policy + Audit)

## Scope
- Added token auth for session handshake (`QIKI_SESSION_AUTH`, `QIKI_SESSION_TOKEN`, `QIKI_SESSION_TOKEN_FILE`).
- Added role model (`viewer`, `controller`, `admin`) with allowlist/default role handling.
- Added strict mode integration via `QIKI_STRICT_MODE`/`QIKI_SESSION_STRICT`.
- Added control policies: `first_come`, `admin_grants`, `queue`.
- Added rate limits for messages/input/bytes and strict disconnect behavior.
- Added audit/control events to EventStore for security lifecycle.

## Behavior
- `AUTH=1` and invalid/missing token: server replies `ERROR auth_failed` and disconnects.
- Role not in allowlist:
  - non-strict: downgrade to default role + `SESSION_ROLE_DOWNGRADED`.
  - strict: reject with `role_forbidden`.
- Control events emitted: `CONTROL_REQUESTED`, `CONTROL_GRANTED`, `CONTROL_DENIED`, `CONTROL_RELEASED`, `CONTROL_EXPIRED`, `CONTROL_REVOKED`.
- Audit events emitted: `SESSION_CLIENT_CONNECTED`, `SESSION_CLIENT_AUTH_FAILED`, `SESSION_CLIENT_DISCONNECTED`, `SESSION_ROLE_DOWNGRADED`, `SESSION_RATE_LIMITED`.
- Client-side disconnect/auth failure keeps truth honest (`NO_DATA` + `SESSION LOST` snapshot path retained from TASK-0031.D1).

## ENV knobs
- `QIKI_SESSION_AUTH=0|1`
- `QIKI_SESSION_TOKEN`
- `QIKI_SESSION_TOKEN_FILE`
- `QIKI_SESSION_ALLOWED_ROLES=viewer,controller,admin`
- `QIKI_SESSION_DEFAULT_ROLE=viewer`
- `QIKI_CONTROL_POLICY=first_come|admin_grants|queue`
- `QIKI_SESSION_STRICT=0|1` (alias of global strict)
- `QIKI_SESSION_MAX_MSGS_PER_SEC` (default `200`)
- `QIKI_SESSION_MAX_INPUTS_PER_SEC` (default `50`)
- `QIKI_SESSION_MAX_BYTES_PER_SEC` (default `1048576`)
- `QIKI_SESSION_MAX_INPUT_VIOLATIONS` (default `3`)
- `QIKI_SESSION_ROLE` (client request role)

## Validation
- Updated `test_session_multiconsole.py` with auth/roles/rate-limit/control policy scenarios.
- Existing distributed session tests (snapshot sync, control flow, replay streaming) remain covered.
